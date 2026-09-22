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
from server.import_data import DEFAULT_SOURCE, import_json  # noqa: E402
from server.mcp_server import mcp  # noqa: E402
from server.nl_query import parse_natural_query  # noqa: E402
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
    return {
        "keyword": q.get("q") or q.get("keyword") or None,
        "teacher": q.get("teacher") or None,
        "department": q.get("department") or None,
        "campus": q.get("campus") or None,
        "biz_type": q.get("biz_type") or None,
        "min_credits": _optional_float(q.get("min_credits"), "min_credits"),
        "max_credits": _optional_float(q.get("max_credits"), "max_credits"),
        "day": _optional_int(q.get("day"), "day"),
        "period_start": _optional_int(q.get("period_start"), "period_start"),
        "period_end": _optional_int(q.get("period_end"), "period_end"),
        "week": _optional_int(q.get("week"), "week"),
        "has_syllabus": _optional_bool(q.get("has_syllabus"), "has_syllabus"),
        "available_only": bool(_optional_bool(q.get("available_only"), "available_only") or False),
        "limit": _optional_int(q.get("limit"), "limit") or 20,
    }


@mcp.custom_route("/", methods=["GET"])
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
            "ask": "/api/ask",
            "openapi": "/openapi.json",
            "mcp": "/mcp",
        }
    )


@mcp.custom_route("/api/courses", methods=["GET", "OPTIONS"])
async def courses(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    try:
        filters = _course_filters(request)
        result = search_courses(**filters)
        result["filters"] = {k: v for k, v in filters.items() if v not in (None, False, "")}
        return _json(result)
    except (TypeError, ValueError) as exc:
        return _error(exc)


@mcp.custom_route("/api/course/{identifier}", methods=["GET", "OPTIONS"])
async def course_detail(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    try:
        result = get_course(request.path_params["identifier"])
        if result["found"] == 0:
            return _json(result, status_code=404)
        return _json(result)
    except (TypeError, ValueError) as exc:
        return _error(exc)


@mcp.custom_route("/api/ask", methods=["GET", "POST", "OPTIONS"])
async def ask(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    try:
        if request.method == "GET":
            query = request.query_params.get("q") or request.query_params.get("query") or ""
            default_limit = _optional_int(request.query_params.get("limit"), "limit") or 20
        else:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
            query = body.get("query") or body.get("q") or ""
            default_limit = int(body.get("limit") or 20)

        parsed = parse_natural_query(query, default_limit=default_limit)
        result = search_courses(**parsed)
        return _json({
            "query": query,
            "parsed": parsed,
            **result,
        })
    except (TypeError, ValueError) as exc:
        return _error(exc)
    except Exception as exc:
        if exc.__class__.__name__ == "JSONDecodeError":
            return _error(ValueError("request body must be valid JSON"))
        raise


OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "FDU Courses API",
        "version": "1.0.0",
        "description": "Public read-only API for querying Fudan University course data.",
    },
    "servers": [{"url": "https://fducourses.vercel.app"}],
    "paths": {
        "/api/ask": {
            "get": {
                "operationId": "askCourses",
                "summary": "Query courses with a natural-language Chinese prompt",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 50}},
                ],
                "responses": {"200": {"description": "Parsed filters and matching courses"}},
            },
            "post": {
                "operationId": "askCoursesPost",
                "summary": "Query courses with a natural-language Chinese prompt",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["query"],
                                "properties": {
                                    "query": {"type": "string", "maxLength": 500},
                                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                                },
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "Parsed filters and matching courses"}},
            },
        },
        "/api/courses": {
            "get": {
                "operationId": "searchCourses",
                "summary": "Search courses with structured filters",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}},
                    {"name": "teacher", "in": "query", "schema": {"type": "string"}},
                    {"name": "department", "in": "query", "schema": {"type": "string"}},
                    {"name": "campus", "in": "query", "schema": {"type": "string", "enum": ["邯郸校区", "张江校区", "枫林校区", "江湾校区", "其他校区"]}},
                    {"name": "biz_type", "in": "query", "schema": {"type": "string", "enum": ["本科", "研究生", "本研融通"]}},
                    {"name": "min_credits", "in": "query", "schema": {"type": "number"}},
                    {"name": "max_credits", "in": "query", "schema": {"type": "number"}},
                    {"name": "day", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 7}},
                    {"name": "period_start", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 14}},
                    {"name": "period_end", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 14}},
                    {"name": "week", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 30}},
                    {"name": "has_syllabus", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "available_only", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}},
                ],
                "responses": {"200": {"description": "Matching courses"}},
            }
        },
        "/api/course/{identifier}": {
            "get": {
                "operationId": "getCourse",
                "summary": "Get course details by teaching-class ID/code or course code",
                "parameters": [
                    {"name": "identifier", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "Course details"},
                    "404": {"description": "Course not found"},
                },
            }
        },
        "/health": {
            "get": {
                "operationId": "health",
                "summary": "Service and data health",
                "responses": {"200": {"description": "Health information"}},
            }
        },
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
