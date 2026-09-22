from __future__ import annotations

import unittest

from server.nl_query import parse_course_query


class NaturalLanguageQueryTests(unittest.TestCase):
    def test_structured_chinese_query(self) -> None:
        parsed = parse_course_query(
            "周三下午张江校区、3学分以上的本科课程，最好和人工智能相关"
        )
        self.assertEqual(parsed.campus, "张江校区")
        self.assertEqual(parsed.biz_type, "本科")
        self.assertEqual(parsed.min_credits, 3.0)
        self.assertEqual(parsed.day, 3)
        self.assertEqual((parsed.period_start, parsed.period_end), (6, 10))
        self.assertEqual(parsed.keyword, "人工智能")

    def test_limit_and_evening(self) -> None:
        parsed = parse_course_query("找周四晚上江湾的研究生机器学习课，最多10门")
        self.assertEqual(parsed.campus, "江湾校区")
        self.assertEqual(parsed.biz_type, "研究生")
        self.assertEqual(parsed.day, 4)
        self.assertEqual((parsed.period_start, parsed.period_end), (11, 14))
        self.assertEqual(parsed.keyword, "机器学习")
        self.assertEqual(parsed.limit, 10)

    def test_week_period_availability_and_exact_credits(self) -> None:
        parsed = parse_course_query("第5周星期二第6到8节枫林有余量的2学分课")
        self.assertEqual(parsed.week, 5)
        self.assertEqual(parsed.day, 2)
        self.assertEqual((parsed.period_start, parsed.period_end), (6, 8))
        self.assertEqual(parsed.campus, "枫林校区")
        self.assertEqual(parsed.min_credits, 2.0)
        self.assertEqual(parsed.max_credits, 2.0)
        self.assertTrue(parsed.available_only)
        self.assertIsNone(parsed.keyword)

    def test_teacher(self) -> None:
        parsed = parse_course_query("张三老师周一上午邯郸校区课程")
        self.assertEqual(parsed.teacher, "张三")
        self.assertEqual(parsed.day, 1)
        self.assertEqual((parsed.period_start, parsed.period_end), (1, 5))
        self.assertEqual(parsed.campus, "邯郸校区")


if __name__ == "__main__":
    unittest.main()
