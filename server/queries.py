from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .db import connect

DAY_NAMES = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
SYLLABUS_BASE = "https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search/teachingSyllabusInfo/"


def _validate_range(name: str, value: int | None, lo: int, hi: int) -> None:
    if value is not None and not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _compress_weeks(weeks: list[int]) -> str:
    if not weeks:
        return ""
    parts: list[str] = []
    start = prev = weeks[0]
    for week in weeks[1:] + [weeks[-1] + 2]:
        if week != prev + 1:
            parts.append(str(start) if start == prev else f"{start}-{prev}")
            start = week
        prev = week
    return ",".join(parts)


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM metadata")}


def _serialize_course(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    course_id = int(row["id"])
    teachers = [r[0] for r in conn.execute(
        "SELECT name FROM teachers WHERE course_id=? ORDER BY name", (course_id,)
    )]
    campuses = [r[0] for r in conn.execute(
        "SELECT campus FROM course_campuses WHERE course_id=? ORDER BY campus", (course_id,)
    )]

    sessions: list[dict[str, Any]] = []
    for s in conn.execute(
        """
        SELECT id, day, period_start, period_end, room
        FROM sessions WHERE course_id=?
        ORDER BY day, period_start, period_end, id
        """,
        (course_id,),
    ):
        weeks = [r[0] for r in conn.execute(
            "SELECT week FROM session_weeks WHERE session_id=? ORDER BY week", (s["id"],)
        )]
        sessions.append({
            "day": int(s["day"]),
            "day_name": DAY_NAMES[int(s["day"])],
            "period_start": int(s["period_start"]),
            "period_end": int(s["period_end"]),
            "weeks": weeks,
            "weeks_text": _compress_weeks(weeks),
            "room": s["room"],
        })

    return {
        "id": course_id,
        "code": row["code"],
        "course_code": row["course_code"],
        "name": row["name"],
        "teachers": teachers,
        "credits": row["credits"],
        "department": row["department"],
        "biz_type": row["biz_type"],
        "course_type": row["course_type"],
        "table_type": row["table_type"],
        "exam_mode": row["exam_mode"],
        "limit": row["limit_count"],
        "enrolled": row["enrolled"],
        "lang": row["lang"],
        "has_syllabus": bool(row["has_syllabus"]),
        "syllabus_url": f"{SYLLABUS_BASE}{course_id}" if row["has_syllabus"] else None,
        "selection_limit": row["selection_limit"],
        "remark": row["remark"],
        "campuses": campuses,
        "sessions": sessions,
    }


def _apply_enrollment(
    course: dict[str, Any],
    enrollment_overrides: dict[int, dict[str, int | None]] | None,
) -> dict[str, Any]:
    if not enrollment_overrides:
        return course
    live = enrollment_overrides.get(int(course["id"]))
    if not live:
        return course
    course["enrolled"] = live.get("enrolled")
    course["limit"] = live.get("limit")
    return course


def _has_availability(course: dict[str, Any]) -> bool:
    return (
        course.get("limit") is not None
        and course.get("enrolled") is not None
        and int(course["enrolled"]) < int(course["limit"])
    )


def search_courses(
    *,
    keyword: str | None = None,
    keyword_includes_teacher: bool = True,
    teacher: str | None = None,
    department: str | None = None,
    campus: str | None = None,
    biz_type: str | None = None,
    min_credits: float | None = None,
    max_credits: float | None = None,
    day: int | None = None,
    period_start: int | None = None,
    period_end: int | None = None,
    week: int | None = None,
    has_syllabus: bool | None = None,
    available_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    db_path: str | Path | None = None,
    enrollment_overrides: dict[int, dict[str, int | None]] | None = None,
) -> dict[str, Any]:
    """Search teaching classes using structured filters.

    Time filters are applied to the same session. If a period range is provided,
    a class matches when its session overlaps that range. Keyword matching can
    optionally include teacher names; dedicated teacher filtering is always
    available through the ``teacher`` argument.

    ``enrollment_overrides`` can provide fresher ``enrolled``/``limit`` values.
    When ``available_only`` is requested, availability is evaluated after these
    overrides are applied, so stale snapshot counts never exclude a newly-opened
    seat before live data has been considered.
    """
    _validate_range("day", day, 1, 7)
    _validate_range("period_start", period_start, 1, 14)
    _validate_range("period_end", period_end, 1, 14)
    _validate_range("week", week, 1, 30)
    if period_start is not None and period_end is not None and period_start > period_end:
        raise ValueError("period_start cannot be greater than period_end")
    if min_credits is not None and max_credits is not None and min_credits > max_credits:
        raise ValueError("min_credits cannot be greater than max_credits")
    limit = max(1, min(int(limit), 50))
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")

    clauses = ["1=1"]
    params: list[Any] = []

    for token in (keyword or "").split():
        pattern = _like(token)
        if keyword_includes_teacher:
            clauses.append(
                """(
                    c.name LIKE ? ESCAPE '\\' OR
                    c.code LIKE ? ESCAPE '\\' OR
                    c.course_code LIKE ? ESCAPE '\\' OR
                    EXISTS (
                        SELECT 1 FROM teachers kt
                        WHERE kt.course_id=c.id AND kt.name LIKE ? ESCAPE '\\'
                    )
                )"""
            )
            params.extend([pattern, pattern, pattern, pattern])
        else:
            clauses.append(
                """(
                    c.name LIKE ? ESCAPE '\\' OR
                    c.code LIKE ? ESCAPE '\\' OR
                    c.course_code LIKE ? ESCAPE '\\'
                )"""
            )
            params.extend([pattern, pattern, pattern])

    if teacher:
        clauses.append(
            "EXISTS (SELECT 1 FROM teachers t WHERE t.course_id=c.id AND t.name LIKE ? ESCAPE '\\')"
        )
        params.append(_like(teacher))
    if department:
        clauses.append("c.department LIKE ? ESCAPE '\\'")
        params.append(_like(department))
    if campus:
        clauses.append(
            "EXISTS (SELECT 1 FROM course_campuses cc WHERE cc.course_id=c.id AND cc.campus=?)"
        )
        params.append(campus)
    if biz_type:
        clauses.append("c.biz_type=?")
        params.append(biz_type)
    if min_credits is not None:
        clauses.append("c.credits>=?")
        params.append(min_credits)
    if max_credits is not None:
        clauses.append("c.credits<=?")
        params.append(max_credits)
    if has_syllabus is not None:
        clauses.append("c.has_syllabus=?")
        params.append(1 if has_syllabus else 0)

    if any(v is not None for v in (day, period_start, period_end, week)):
        session_clauses = ["s.course_id=c.id"]
        if day is not None:
            session_clauses.append("s.day=?")
            params.append(day)
        if period_start is not None and period_end is not None:
            session_clauses.extend(["s.period_start<=?", "s.period_end>=?"])
            params.extend([period_end, period_start])
        elif period_start is not None:
            session_clauses.append("s.period_end>=?")
            params.append(period_start)
        elif period_end is not None:
            session_clauses.append("s.period_start<=?")
            params.append(period_end)
        if week is not None:
            session_clauses.append(
                "EXISTS (SELECT 1 FROM session_weeks sw WHERE sw.session_id=s.id AND sw.week=?)"
            )
            params.append(week)
        clauses.append("EXISTS (SELECT 1 FROM sessions s WHERE " + " AND ".join(session_clauses) + ")")

    where_sql = " AND ".join(clauses)
    base_select_sql = f"SELECT c.* FROM courses c WHERE {where_sql} ORDER BY c.name, c.code"
    count_sql = f"SELECT COUNT(*) FROM courses c WHERE {where_sql}"

    with connect(db_path) as conn:
        meta = _metadata(conn)

        if available_only:
            rows = conn.execute(base_select_sql, params).fetchall()
            available = [
                course
                for course in (
                    _apply_enrollment(_serialize_course(conn, row), enrollment_overrides)
                    for row in rows
                )
                if _has_availability(course)
            ]
            total = len(available)
            courses = available[offset:offset + limit]
        else:
            total = int(conn.execute(count_sql, params).fetchone()[0])
            rows = conn.execute(base_select_sql + " LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
            courses = [
                _apply_enrollment(_serialize_course(conn, row), enrollment_overrides)
                for row in rows
            ]

        return {
            "semester": meta.get("semester", ""),
            "generated_at": meta.get("generatedAt", ""),
            "total": total,
            "returned": len(courses),
            "offset": offset,
            "has_more": offset + len(courses) < total,
            "courses": courses,
        }


def get_course(
    identifier: str | int,
    *,
    db_path: str | Path | None = None,
    enrollment_overrides: dict[int, dict[str, int | None]] | None = None,
) -> dict[str, Any]:
    """Get one teaching class by id/code, or all teaching classes for a course code."""
    text = str(identifier).strip()
    if not text:
        raise ValueError("identifier cannot be empty")

    clauses = ["lower(code)=lower(?)", "lower(course_code)=lower(?)"]
    params: list[Any] = [text, text]
    if text.isdigit():
        clauses.insert(0, "id=?")
        params.insert(0, int(text))

    sql = "SELECT * FROM courses WHERE " + " OR ".join(clauses) + " ORDER BY code LIMIT 50"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        meta = _metadata(conn)
        return {
            "semester": meta.get("semester", ""),
            "generated_at": meta.get("generatedAt", ""),
            "found": len(rows),
            "courses": [
                _apply_enrollment(_serialize_course(conn, row), enrollment_overrides)
                for row in rows
            ],
        }
