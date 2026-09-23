from __future__ import annotations

import os
from typing import Literal

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .enrollment import get_enrollment_snapshot
from .queries import get_course as query_get_course
from .queries import search_courses as query_search_courses

Campus = Literal["邯郸校区", "张江校区", "枫林校区", "江湾校区", "其他校区"]
BizType = Literal["本科", "研究生", "本研融通"]

mcp = MCPServer(
    "FDU Courses",
    instructions=(
        "查询复旦大学当前学期开课信息。优先使用结构化筛选；"
        "day 使用 1=周一 ... 7=周日；节次为 1-14。"
        "下午通常对应第 6-10 节，晚上通常对应第 11-14 节。"
        "选课人数与容量会从复旦公开课程接口刷新，并缓存 5 分钟；"
        "响应中的 enrollment_updated_at 表示人数更新时间。"
    ),
)


def _with_enrollment_meta(result: dict, snapshot) -> dict:
    result["enrollment_updated_at"] = snapshot.updated_at or result.get("generated_at", "")
    if snapshot.values:
        result["enrollment_source"] = "live-cache" if snapshot.fresh else "stale-cache"
    else:
        result["enrollment_source"] = "snapshot"
    result["enrollment_cache_ttl_seconds"] = snapshot.ttl_seconds
    return result


@mcp.tool()
def search_courses(
    keyword: str | None = None,
    teacher: str | None = None,
    department: str | None = None,
    campus: Campus | None = None,
    biz_type: BizType | None = None,
    min_credits: float | None = None,
    max_credits: float | None = None,
    day: int | None = None,
    period_start: int | None = None,
    period_end: int | None = None,
    week: int | None = None,
    has_syllabus: bool | None = None,
    available_only: bool = False,
    limit: int = 20,
) -> dict:
    """查询复旦课程。

    keyword 可匹配课程名、教学班代码、课程代码和教师姓名。
    day: 1=周一 ... 7=周日。
    period_start/period_end: 1-14；同时提供时按时间段重叠查询。
    week: 教学周。
    available_only: 按最近 5 分钟内刷新的人数，仅返回尚未满员的教学班。
    单次最多返回 50 个教学班。
    """
    snapshot = get_enrollment_snapshot()
    result = query_search_courses(
        keyword=keyword,
        teacher=teacher,
        department=department,
        campus=campus,
        biz_type=biz_type,
        min_credits=min_credits,
        max_credits=max_credits,
        day=day,
        period_start=period_start,
        period_end=period_end,
        week=week,
        has_syllabus=has_syllabus,
        available_only=available_only,
        limit=limit,
        enrollment_overrides=snapshot.values,
    )
    return _with_enrollment_meta(result, snapshot)


@mcp.tool()
def get_course(identifier: str) -> dict:
    """按教学班 ID、教学班代码或课程代码获取课程详情、完整上课安排和最新人数。"""
    snapshot = get_enrollment_snapshot()
    result = query_get_course(identifier, enrollment_overrides=snapshot.values)
    return _with_enrollment_meta(result, snapshot)


def _transport_security() -> TransportSecuritySettings | None:
    raw_hosts = os.environ.get("FDU_MCP_ALLOWED_HOSTS", "").strip()
    raw_origins = os.environ.get("FDU_MCP_ALLOWED_ORIGINS", "").strip()
    if not raw_hosts and not raw_origins:
        return None
    return TransportSecuritySettings(
        allowed_hosts=[item.strip() for item in raw_hosts.split(",") if item.strip()],
        allowed_origins=[item.strip() for item in raw_origins.split(",") if item.strip()],
    )


def main() -> None:
    transport = os.environ.get("FDU_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport != "streamable-http":
        raise ValueError("FDU_MCP_TRANSPORT must be 'stdio' or 'streamable-http'")

    host = os.environ.get("FDU_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("FDU_MCP_PORT", "8000"))
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        json_response=True,
        stateless_http=True,
        transport_security=_transport_security(),
    )


if __name__ == "__main__":
    main()
