from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from server import enrollment


class EnrollmentCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.tmp.name) / "enrollment-cache.json"
        self.old_cache_file = os.environ.get("FDU_ENROLLMENT_CACHE_FILE")
        self.old_ttl = os.environ.get("FDU_ENROLLMENT_CACHE_TTL")
        os.environ["FDU_ENROLLMENT_CACHE_FILE"] = str(self.cache_file)
        os.environ["FDU_ENROLLMENT_CACHE_TTL"] = "300"
        enrollment._MEMORY = None

    def tearDown(self) -> None:
        enrollment._MEMORY = None
        if self.old_cache_file is None:
            os.environ.pop("FDU_ENROLLMENT_CACHE_FILE", None)
        else:
            os.environ["FDU_ENROLLMENT_CACHE_FILE"] = self.old_cache_file
        if self.old_ttl is None:
            os.environ.pop("FDU_ENROLLMENT_CACHE_TTL", None)
        else:
            os.environ["FDU_ENROLLMENT_CACHE_TTL"] = self.old_ttl
        self.tmp.cleanup()

    def test_reuses_snapshot_within_five_minutes(self) -> None:
        payload = {
            "semester_id": "999",
            "fetched_at": time.time(),
            "updated_at": "2026-09-23T12:00:00+08:00",
            "values": {"1": {"enrolled": 41, "limit": 60}},
        }
        with patch.object(enrollment, "_semester_id", return_value="999"), patch.object(
            enrollment, "_fetch", return_value=payload
        ) as fetch:
            first = enrollment.get_enrollment_snapshot()
            second = enrollment.get_enrollment_snapshot()

        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(first.values[1]["enrolled"], 41)
        self.assertEqual(second.updated_at, "2026-09-23T12:00:00+08:00")
        self.assertTrue(second.fresh)
        self.assertEqual(second.ttl_seconds, 300)

    def test_returns_stale_cache_when_upstream_fails(self) -> None:
        stale_payload = {
            "semester_id": "999",
            "fetched_at": time.time() - 600,
            "updated_at": "2026-09-23T11:50:00+08:00",
            "values": {"2": {"enrolled": 29, "limit": 30}},
        }
        enrollment._MEMORY = stale_payload
        with patch.object(enrollment, "_semester_id", return_value="999"), patch.object(
            enrollment, "_fetch", side_effect=OSError("upstream unavailable")
        ):
            snapshot = enrollment.get_enrollment_snapshot()

        self.assertFalse(snapshot.fresh)
        self.assertEqual(snapshot.values[2]["enrolled"], 29)
        self.assertEqual(snapshot.updated_at, "2026-09-23T11:50:00+08:00")


if __name__ == "__main__":
    unittest.main()
