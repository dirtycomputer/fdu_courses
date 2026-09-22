from __future__ import annotations

import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse

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


def _ensure_database() -> None:
    db_path = resolve_db_path()
    if db_path.exists() and db_path.stat().st_size > 0:
        return
    import_json(DEFAULT_SOURCE, db_path)


_ensure_database()


@mcp.custom_route("/api/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    with connect() as conn:
        metadata = {
            row["key"]: row["value"]
            for row in conn.execute("SELECT key, value FROM metadata")
        }
        course_count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]

    return JSONResponse(
        {
            "status": "ok",
            "service": "fdu-courses-mcp",
            "semester": metadata.get("semester", ""),
            "generatedAt": metadata.get("generatedAt", ""),
            "courses": course_count,
            "mcp": "/mcp",
        }
    )


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
