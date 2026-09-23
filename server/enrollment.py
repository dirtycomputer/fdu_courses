from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .db import connect

SEARCH_URL = (
    "https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search/semester/{sid}/search/{sid}"
)
DEFAULT_TTL_SECONDS = 300
DEFAULT_PAGE_SIZE = 2000
DEFAULT_PAGE_WORKERS = 4
DEFAULT_CACHE_FILE = Path(tempfile.gettempdir()) / "fdu-courses-enrollment-cache.json"
BJ = timezone(timedelta(hours=8))
_LOCK = threading.Lock()
_MEMORY: dict[str, Any] | None = None


@dataclass(frozen=True)
class EnrollmentSnapshot:
    values: dict[int, dict[str, int | None]]
    updated_at: str
    fresh: bool
    ttl_seconds: int
    error: str | None = None


def _ttl_seconds() -> int:
    raw = os.environ.get("FDU_ENROLLMENT_CACHE_TTL", str(DEFAULT_TTL_SECONDS))
    try:
        return max(30, int(raw))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _page_size() -> int:
    raw = os.environ.get("FDU_ENROLLMENT_PAGE_SIZE", str(DEFAULT_PAGE_SIZE))
    try:
        return max(200, min(5000, int(raw)))
    except ValueError:
        return DEFAULT_PAGE_SIZE


def _page_workers() -> int:
    raw = os.environ.get("FDU_ENROLLMENT_PAGE_WORKERS", str(DEFAULT_PAGE_WORKERS))
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return DEFAULT_PAGE_WORKERS


def _cache_file() -> Path:
    return Path(os.environ.get("FDU_ENROLLMENT_CACHE_FILE", str(DEFAULT_CACHE_FILE)))


def _semester_id(db_path: str | Path | None = None) -> str:
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key='semesterId'").fetchone()
    if not row or not str(row[0]).strip():
        raise RuntimeError("semesterId is missing from course metadata")
    return str(row[0]).strip()


def _is_fresh(payload: dict[str, Any], semester_id: str, ttl: int) -> bool:
    return (
        payload.get("semester_id") == semester_id
        and isinstance(payload.get("fetched_at"), (int, float))
        and time.time() - float(payload["fetched_at"]) < ttl
        and isinstance(payload.get("values"), dict)
    )


def _decode_values(raw: dict[str, Any]) -> dict[int, dict[str, int | None]]:
    out: dict[int, dict[str, int | None]] = {}
    for key, value in raw.items():
        try:
            course_id = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        enrolled = value.get("enrolled")
        limit_count = value.get("limit")
        out[course_id] = {
            "enrolled": int(enrolled) if enrolled is not None else None,
            "limit": int(limit_count) if limit_count is not None else None,
        }
    return out


def _snapshot_from_payload(
    payload: dict[str, Any], ttl: int, *, fresh: bool, error: str | None = None
) -> EnrollmentSnapshot:
    return EnrollmentSnapshot(
        values=_decode_values(payload.get("values") or {}),
        updated_at=str(payload.get("updated_at") or ""),
        fresh=fresh,
        ttl_seconds=ttl,
        error=error,
    )


def _load_disk() -> dict[str, Any] | None:
    path = _cache_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _save_disk(payload: dict[str, Any]) -> None:
    path = _cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def _fetch_page(semester_id: str, page: int, page_size: int) -> dict[str, Any]:
    url = SEARCH_URL.format(sid=semester_id) + f"?queryPage__={page},{page_size}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (fdu-courses live enrollment)",
            "Accept": "application/json",
        },
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.4)
    assert last_error is not None
    raise last_error


def _fetch(semester_id: str) -> dict[str, Any]:
    page_size = _page_size()
    first = _fetch_page(semester_id, 1, page_size)
    first_rows = first.get("data") or []
    page_meta = first.get("_page_") or {}
    total_rows = int(page_meta.get("totalRows") or len(first_rows))
    page_count = max(1, math.ceil(total_rows / page_size))

    rows = list(first_rows)
    if page_count > 1:
        workers = min(_page_workers(), page_count - 1)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pages = list(pool.map(
                lambda page: _fetch_page(semester_id, page, page_size),
                range(2, page_count + 1),
            ))
        for body in pages:
            rows.extend(body.get("data") or [])

    values: dict[str, dict[str, int | None]] = {}
    for row in rows:
        if row.get("id") is None:
            continue
        values[str(int(row["id"]))] = {
            "enrolled": int(row["stdCount"]) if row.get("stdCount") is not None else None,
            "limit": int(row["limitCount"]) if row.get("limitCount") is not None else None,
        }

    if total_rows and len(values) < min(total_rows, 1):
        raise RuntimeError("live enrollment endpoint returned no usable course rows")

    now = datetime.now(BJ)
    return {
        "semester_id": semester_id,
        "fetched_at": time.time(),
        "updated_at": now.isoformat(timespec="seconds"),
        "values": values,
    }


def get_enrollment_snapshot(
    *, db_path: str | Path | None = None, force: bool = False
) -> EnrollmentSnapshot:
    """Return enrollment/capacity data refreshed at most once per cache TTL.

    Cache is kept both in process memory and in /tmp so warm Vercel invocations can
    reuse the same upstream response. If Fudan's endpoint is temporarily
    unavailable, the latest stale cache is returned when possible; callers can
    inspect ``fresh`` and ``error`` to decide how to label the result.
    """
    global _MEMORY

    ttl = _ttl_seconds()
    semester_id = _semester_id(db_path)

    if not force and _MEMORY and _is_fresh(_MEMORY, semester_id, ttl):
        return _snapshot_from_payload(_MEMORY, ttl, fresh=True)

    disk = _load_disk()
    if not force and disk and _is_fresh(disk, semester_id, ttl):
        _MEMORY = disk
        return _snapshot_from_payload(disk, ttl, fresh=True)

    with _LOCK:
        if not force and _MEMORY and _is_fresh(_MEMORY, semester_id, ttl):
            return _snapshot_from_payload(_MEMORY, ttl, fresh=True)

        stale = _MEMORY if _MEMORY and _MEMORY.get("semester_id") == semester_id else None
        if stale is None and disk and disk.get("semester_id") == semester_id:
            stale = disk

        try:
            payload = _fetch(semester_id)
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"
            if stale:
                _MEMORY = stale
                return _snapshot_from_payload(stale, ttl, fresh=False, error=error)
            return EnrollmentSnapshot(
                values={},
                updated_at="",
                fresh=False,
                ttl_seconds=ttl,
                error=error,
            )

        _MEMORY = payload
        try:
            _save_disk(payload)
        except OSError:
            pass
        return _snapshot_from_payload(payload, ttl, fresh=True)
