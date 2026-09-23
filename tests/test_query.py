from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from server.import_data import import_json
from server.queries import get_course, search_courses


class QueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "latest.json"
        self.db = root / "courses.db"
        data = {
            "semester": "测试学期",
            "semesterId": 999,
            "week1Monday": "2026-09-07",
            "generatedAt": "2026-09-22 12:00",
            "campusNames": ["邯郸校区", "张江校区", "枫林校区", "江湾校区", "其他校区"],
            "courses": [
                {
                    "id": 1,
                    "code": "COMP130001.01",
                    "courseCode": "COMP130001",
                    "name": "机器学习",
                    "teachers": ["张三"],
                    "credits": 3,
                    "department": "计算机科学技术学院",
                    "bizType": "本科",
                    "courseType": "专业课",
                    "tableType": "专业教育课程",
                    "examMode": "考试",
                    "limit": 60,
                    "enrolled": 40,
                    "lang": "中文",
                    "hasSyllabus": True,
                    "selectionLimit": "",
                    "remark": None,
                    "rawSchedule": "",
                    "campuses": [2],
                    "sessions": [{"day": 3, "p": [6, 8], "weeks": [1, 3, 5], "room": "Z2204"}],
                },
                {
                    "id": 2,
                    "code": "DATA120001.01",
                    "courseCode": "DATA120001",
                    "name": "数据库",
                    "teachers": ["李四"],
                    "credits": 2,
                    "department": "计算机科学技术学院",
                    "bizType": "本科",
                    "courseType": "专业课",
                    "tableType": "专业教育课程",
                    "examMode": "考试",
                    "limit": 30,
                    "enrolled": 30,
                    "lang": "中文",
                    "hasSyllabus": False,
                    "selectionLimit": "",
                    "remark": None,
                    "rawSchedule": "",
                    "campuses": [1],
                    "sessions": [{"day": 3, "p": [1, 2], "weeks": list(range(1, 19)), "room": "H3101"}],
                },
            ],
        }
        self.source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        import_json(self.source, self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_structured_time_filters_apply_to_same_session(self) -> None:
        result = search_courses(
            campus="张江校区",
            biz_type="本科",
            day=3,
            period_start=6,
            period_end=8,
            week=3,
            min_credits=3,
            db_path=self.db,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["courses"][0]["name"], "机器学习")

        no_match = search_courses(day=3, period_start=6, period_end=8, week=2, db_path=self.db)
        self.assertEqual(no_match["total"], 0)

    def test_keyword_can_match_teacher(self) -> None:
        result = search_courses(keyword="张三", db_path=self.db)
        self.assertEqual([c["id"] for c in result["courses"]], [1])

    def test_keyword_teacher_matching_can_be_disabled(self) -> None:
        teacher_only = search_courses(
            keyword="张三", keyword_includes_teacher=False, db_path=self.db
        )
        self.assertEqual(teacher_only["total"], 0)

        course_name = search_courses(
            keyword="机器学习", keyword_includes_teacher=False, db_path=self.db
        )
        self.assertEqual([c["id"] for c in course_name["courses"]], [1])

    def test_available_only(self) -> None:
        result = search_courses(available_only=True, db_path=self.db)
        self.assertEqual([c["id"] for c in result["courses"]], [1])

    def test_live_enrollment_overrides_availability(self) -> None:
        live = {
            1: {"limit": 60, "enrolled": 60},
            2: {"limit": 30, "enrolled": 29},
        }
        result = search_courses(
            available_only=True,
            enrollment_overrides=live,
            db_path=self.db,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual([c["id"] for c in result["courses"]], [2])
        self.assertEqual(result["courses"][0]["enrolled"], 29)

    def test_get_course_by_course_code(self) -> None:
        result = get_course("COMP130001", db_path=self.db)
        self.assertEqual(result["found"], 1)
        course = result["courses"][0]
        self.assertTrue(course["has_syllabus"])
        self.assertEqual(course["sessions"][0]["weeks_text"], "1,3,5")

    def test_get_course_uses_live_enrollment_override(self) -> None:
        result = get_course(
            "COMP130001",
            db_path=self.db,
            enrollment_overrides={1: {"limit": 61, "enrolled": 58}},
        )
        self.assertEqual(result["courses"][0]["limit"], 61)
        self.assertEqual(result["courses"][0]["enrolled"], 58)


if __name__ == "__main__":
    unittest.main()
