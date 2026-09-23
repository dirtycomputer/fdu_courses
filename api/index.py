from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

# Vercel can bundle a deployment-time generated SQLite database. If it is
# missing (for example during `vercel dev` before the build command ran), fall
# back to creating one once in the writable /tmp directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_DB = PROJECT_ROOT / "data" / "courses.db"
if not BUNDLED_DB.exists():
    os.environ["FDU_COURSES_DB"] = "/tmp/fdu-courses.db"

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

from server.db import connect, resolve_db_path  # noqa: E402
from server.enrollment import get_enrollment_snapshot  # noqa: E402
from server.import_data import DEFAULT_SOURCE, import_json  # noqa: E402
from server.mcp_server import mcp  # noqa: E402
from server.query_contract import QUERY_SCHEMA, decode_filters, validate_filters  # noqa: E402
from server.queries import get_course, search_courses  # noqa: E402

WEB_INDEX = PROJECT_ROOT / "web" / "index.html"
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _ensure_database() -> None:
    db_path = resolve_db_path()
    if db_path.exists() and db_path.stat().st_size > 0:
        return
    import_json(DEFAULT_SOURCE, db_path)


_ensure_database()


def _json(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status_code, headers=CORS_HEADERS)


def _error(exc: Exception, status_code: int = 400) -> JSONResponse:
    return _json({"error": str(exc)}, status_code=status_code)


def _optional_int(value: str | None, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _optional_float(value: str | None, name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _optional_bool(value: str | None, name: str) -> bool | None:
    if value in (None, ""):
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _course_filters(request: Request) -> dict[str, Any]:
    q = request.query_params
    if len(q.multi_items()) != len(q):
        raise ValueError("Duplicate query parameters are not supported")
    if "q" in q and "keyword" in q:
        raise ValueError("Use keyword or q, not both")
    filters: dict[str, Any] = {}
    for raw_key, raw in q.items():
        key = "keyword" if raw_key == "q" else raw_key
        field = QUERY_SCHEMA["properties"].get(key)
        if field is None:
            raise ValueError(f"Unknown filter: {raw_key}")
        if not raw.strip():
            raise ValueError(f"{key} cannot be blank")
        converters = {"integer": _optional_int, "number": _optional_float, "boolean": _optional_bool}
        converter = converters.get(field["type"])
        filters[key] = converter(raw, key) if converter else raw
    return validate_filters(filters)


def _attach_enrollment_metadata(result: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    result["enrollment_updated_at"] = snapshot.updated_at or result.get("generated_at", "")
    if snapshot.values:
        result["enrollment_source"] = "live-cache" if snapshot.fresh else "stale-cache"
    else:
        result["enrollment_source"] = "snapshot"
    result["enrollment_cache_ttl_seconds"] = snapshot.ttl_seconds
    if snapshot.error:
        result["enrollment_error"] = snapshot.error
    return result


@mcp.custom_route("/api/home", methods=["GET"])
async def home(_: Request) -> HTMLResponse:
    if not WEB_INDEX.exists():
        return HTMLResponse("FDU Courses API", status_code=200)
    return HTMLResponse(WEB_INDEX.read_text(encoding="utf-8"))


@mcp.custom_route("/api/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    with connect() as conn:
        metadata = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM metadata")
        }
        course_count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]

    return _json(
        {
            "status": "ok",
            "service": "fdu-courses",
            "semester": metadata.get("semester", ""),
            "generatedAt": metadata.get("generatedAt", ""),
            "courses": course_count,
            "rest": "/api/courses",
            "query_schema": "/api/query-schema",
            "query_mode": "caller-llm-structured-json",
            "openapi": "/openapi.json",
            "mcp": "/mcp",
            "enrollment": "5-minute cache; stale/static fallback on upstream failure",
        }
    )


async def _structured_query(request: Request, *, legacy_params: bool = False) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    try:
        if request.method == "POST":
            if request.query_params:
                raise ValueError("Send filters in the JSON body only")
            filters = decode_filters((await request.body()).decode("utf-8"))
            includes_teacher = False
        elif "filters" in request.query_params:
            if len(request.query_params.multi_items()) != 1:
                raise ValueError("Send only the filters JSON parameter")
            filters = decode_filters(request.query_params["filters"])
            includes_teacher = False
        elif legacy_params:
            filters = _course_filters(request)
            includes_teacher = True  # Preserve the existing flat GET keyword semantics.
        else:
            raise ValueError("Natural-language parsing has been removed. Ask your AI tool's LLM to generate JSON using /api/query-schema, then POST that object or GET ?filters=<encoded JSON>.")
        snapshot = get_enrollment_snapshot()
        result = search_courses(**filters, keyword_includes_teacher=includes_teacher, enrollment_overrides=snapshot.values)
        result["filters"] = filters
        return _json(_attach_enrollment_metadata(result, snapshot))
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        return _error(exc)


@mcp.custom_route("/api/query-schema", methods=["GET", "OPTIONS"])
async def query_schema(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    return _json(QUERY_SCHEMA)


@mcp.custom_route("/api/courses", methods=["GET", "POST", "OPTIONS"])
async def courses(request: Request) -> Response:
    return await _structured_query(request, legacy_params=True)


@mcp.custom_route("/api/course/{identifier}", methods=["GET", "OPTIONS"])
async def course_detail(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    try:
        snapshot = get_enrollment_snapshot()
        result = get_course(
            request.path_params["identifier"],
            enrollment_overrides=snapshot.values,
        )
        _attach_enrollment_metadata(result, snapshot)
        if result["found"] == 0:
            return _json(result, status_code=404)
        return _json(result)
    except (TypeError, ValueError) as exc:
        return _error(exc)


@mcp.custom_route("/api/ask", methods=["GET", "POST", "OPTIONS"])
async def ask(request: Request) -> Response:
    """Compatibility URL for structured JSON only; no heuristic NLP fallback."""
    return await _structured_query(request)


QUERY_RESPONSES = {
    "200": {"description": "Validated filters, matching teaching classes, pagination and enrollment freshness"},
    "400": {"description": "Invalid JSON, unknown fields, unsupported values or conflicting bounds"},
}
JSON_QUERY_GET = {
    "operationId": "searchCoursesJsonGet",
    "summary": "Execute a filter object generated by the calling LLM; no natural-language parsing",
    "parameters": [{"name": "filters", "in": "query", "required": True,
                    "content": {"application/json": {"schema": QUERY_SCHEMA}}}],
    "responses": QUERY_RESPONSES,
}
JSON_QUERY_POST = {
    "operationId": "searchCoursesJson",
    "summary": "Validate and execute a filter object generated by the calling LLM",
    "requestBody": {"required": True, "content": {"application/json": {"schema": QUERY_SCHEMA}}},
    "responses": QUERY_RESPONSES,
}
OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "FDU Courses API", "version": "2.0.0",
             "description": "The calling AI tool's LLM interprets user intent and generates JSON. The service validates filters and queries SQLite. Enrollment may fall back to stale or static data; inspect enrollment_source."},
    "servers": [{"url": "https://fducourses.vercel.app"}],
    "paths": {
        "/api/query-schema": {"get": {
            "operationId": "getQuerySchema", "summary": "JSON Schema for LLM-generated course filters",
            "responses": {"200": {"description": "JSON Schema (draft 2020-12)"}},
        }},
        "/api/courses": {
            "get": {**JSON_QUERY_GET,
                    "description": "Supply filters as URL-encoded JSON. Legacy flat query parameters are supported separately; never mix them with filters.",
                    "parameters": [
                        {**JSON_QUERY_GET["parameters"][0], "required": False},
                        *[{"name": name, "in": "query", "schema": schema}
                          for name, schema in QUERY_SCHEMA["properties"].items()],
                        {"name": "q", "in": "query", "schema": {"type": "string"},
                         "description": "Legacy keyword alias; never pass a natural-language sentence."},
                    ]},
            "post": JSON_QUERY_POST,
        },
        "/api/ask": {
            "get": {**JSON_QUERY_GET, "operationId": "askStructuredGet", "deprecated": True},
            "post": {**JSON_QUERY_POST, "operationId": "askStructuredPost", "deprecated": True},
        },
        "/api/course/{identifier}": {"get": {
            "operationId": "getCourse", "summary": "Get course details by teaching-class ID/code or course code",
            "parameters": [{"name": "identifier", "in": "path", "required": True, "schema": {"type": "string"}}],
            "responses": {"200": {"description": "Course details and enrollment freshness"},
                          "404": {"description": "Course not found"}},
        }},
        "/health": {"get": {
            "operationId": "health", "summary": "Service and dataset version",
            "responses": {"200": {"description": "Health information"}},
        }},
    },
}


@mcp.custom_route("/api/openapi.json", methods=["GET"])
async def openapi(_: Request) -> JSONResponse:
    return _json(OPENAPI_SPEC)


# Vercel terminates TLS and controls the public reverse proxy. Disabling the
# SDK's localhost-oriented DNS-rebinding Host check avoids rejecting dynamic
# *.vercel.app preview hostnames. The MCP service is read-only and public.
app = mcp.streamable_http_app(
    streamable_http_path="/api/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)
