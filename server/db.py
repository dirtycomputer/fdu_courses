from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = Path(os.environ.get("FDU_COURSES_DB", PROJECT_ROOT / "data" / "courses.db"))


def resolve_db_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_DB_PATH


def connect(path: str | Path | None = None, *, readonly: bool = True) -> sqlite3.Connection:
    db_path = resolve_db_path(path)
    if readonly:
        if not db_path.exists():
            raise FileNotFoundError(
                f"Course database not found: {db_path}. "
                "Run `python -m server.import_data` first."
            )
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
