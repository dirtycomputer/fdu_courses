from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .db import PROJECT_ROOT, resolve_db_path

DEFAULT_SOURCE = PROJECT_ROOT / "docs" / "data" / "latest.json"

SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    course_code TEXT NOT NULL,
    name TEXT NOT NULL,
    credits REAL,
    department TEXT NOT NULL,
    biz_type TEXT NOT NULL,
    course_type TEXT NOT NULL,
    table_type TEXT NOT NULL,
    exam_mode TEXT NOT NULL,
    limit_count INTEGER,
    enrolled INTEGER,
    lang TEXT NOT NULL,
    has_syllabus INTEGER NOT NULL CHECK (has_syllabus IN (0, 1)),
    selection_limit TEXT NOT NULL,
    remark TEXT,
    raw_schedule TEXT NOT NULL
);

CREATE TABLE teachers (
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    PRIMARY KEY (course_id, name)
);

CREATE TABLE course_campuses (
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    campus TEXT NOT NULL,
    PRIMARY KEY (course_id, campus)
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    day INTEGER NOT NULL CHECK (day BETWEEN 1 AND 7),
    period_start INTEGER NOT NULL CHECK (period_start BETWEEN 1 AND 14),
    period_end INTEGER NOT NULL CHECK (period_end BETWEEN 1 AND 14),
    room TEXT NOT NULL,
    CHECK (period_start <= period_end)
);

CREATE TABLE session_weeks (
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    week INTEGER NOT NULL CHECK (week BETWEEN 1 AND 30),
    PRIMARY KEY (session_id, week)
);

CREATE INDEX idx_courses_name ON courses(name);
CREATE INDEX idx_courses_code ON courses(code);
CREATE INDEX idx_courses_course_code ON courses(course_code);
CREATE INDEX idx_courses_department ON courses(department);
CREATE INDEX idx_courses_biz_type ON courses(biz_type);
CREATE INDEX idx_courses_credits ON courses(credits);
CREATE INDEX idx_teachers_name ON teachers(name);
CREATE INDEX idx_campuses_name ON course_campuses(campus);
CREATE INDEX idx_sessions_course_day_period ON sessions(course_id, day, period_start, period_end);
CREATE INDEX idx_session_weeks_week ON session_weeks(week, session_id);
"""


def _metadata(data: dict[str, Any]) -> dict[str, str]:
    keys = ("semester", "semesterId", "week1Monday", "generatedAt")
    return {key: str(data.get(key, "")) for key in keys}


def import_json(source: str | Path = DEFAULT_SOURCE, dest: str | Path | None = None) -> dict[str, int | str]:
    source_path = Path(source)
    dest_path = resolve_db_path(dest)
    if not source_path.exists():
        raise FileNotFoundError(f"Source JSON not found: {source_path}")

    with source_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    courses = data.get("courses") or []
    campus_names = data.get("campusNames") or []
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)

    conn = sqlite3.connect(tmp_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.executescript(SCHEMA)
        with conn:
            conn.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                _metadata(data).items(),
            )

            for course in courses:
                course_id = int(course["id"])
                conn.execute(
                    """
                    INSERT INTO courses(
                        id, code, course_code, name, credits, department, biz_type,
                        course_type, table_type, exam_mode, limit_count, enrolled,
                        lang, has_syllabus, selection_limit, remark, raw_schedule
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_id,
                        course.get("code") or "",
                        course.get("courseCode") or "",
                        course.get("name") or "",
                        course.get("credits"),
                        course.get("department") or "",
                        course.get("bizType") or "",
                        course.get("courseType") or "",
                        course.get("tableType") or "",
                        course.get("examMode") or "",
                        course.get("limit"),
                        course.get("enrolled"),
                        course.get("lang") or "",
                        1 if course.get("hasSyllabus") else 0,
                        course.get("selectionLimit") or "",
                        course.get("remark"),
                        course.get("rawSchedule") or "",
                    ),
                )

                teachers = sorted(set(course.get("teachers") or []))
                conn.executemany(
                    "INSERT INTO teachers(course_id, name) VALUES (?, ?)",
                    ((course_id, name) for name in teachers if name),
                )

                campuses = []
                for campus_id in course.get("campuses") or []:
                    try:
                        campus = campus_names[int(campus_id) - 1]
                    except (IndexError, TypeError, ValueError):
                        campus = "其他校区"
                    campuses.append(campus)
                conn.executemany(
                    "INSERT OR IGNORE INTO course_campuses(course_id, campus) VALUES (?, ?)",
                    ((course_id, campus) for campus in campuses if campus),
                )

                for session in course.get("sessions") or []:
                    periods = session.get("p") or []
                    if len(periods) != 2:
                        continue
                    cur = conn.execute(
                        """
                        INSERT INTO sessions(course_id, day, period_start, period_end, room)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            course_id,
                            int(session["day"]),
                            int(periods[0]),
                            int(periods[1]),
                            session.get("room") or "",
                        ),
                    )
                    session_id = int(cur.lastrowid)
                    weeks = sorted({int(w) for w in (session.get("weeks") or [])})
                    conn.executemany(
                        "INSERT INTO session_weeks(session_id, week) VALUES (?, ?)",
                        ((session_id, week) for week in weeks),
                    )

        conn.execute("PRAGMA optimize")
    except Exception:
        conn.close()
        tmp_path.unlink(missing_ok=True)
        raise
    else:
        conn.close()

    os.replace(tmp_path, dest_path)
    return {
        "database": str(dest_path),
        "courses": len(courses),
        "semester": str(data.get("semester") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import docs/data/latest.json into SQLite")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--out", default=None, help="SQLite output path; defaults to data/courses.db")
    args = parser.parse_args()
    result = import_json(args.source, args.out)
    print(f"imported {result['courses']} teaching classes -> {result['database']}")
    if result["semester"]:
        print(f"semester: {result['semester']}")


if __name__ == "__main__":
    main()
