import unittest

from server.nl_query import parse_natural_query


class NaturalLanguageQueryTests(unittest.TestCase):
    def test_composite_query(self):
        parsed = parse_natural_query(
            "找周三下午张江校区、3 学分以上、本科生能上的人工智能相关课程，最多 10 门"
        )
        self.assertEqual(parsed["campus"], "张江校区")
        self.assertEqual(parsed["biz_type"], "本科")
        self.assertEqual(parsed["day"], 3)
        self.assertEqual(parsed["period_start"], 6)
        self.assertEqual(parsed["period_end"], 10)
        self.assertEqual(parsed["min_credits"], 3.0)
        self.assertEqual(parsed["keyword"], "人工智能")
        self.assertEqual(parsed["limit"], 10)

    def test_week_and_availability(self):
        parsed = parse_natural_query("第 5 周周二上午有余量的课程")
        self.assertEqual(parsed["week"], 5)
        self.assertEqual(parsed["day"], 2)
        self.assertEqual(parsed["period_start"], 1)
        self.assertEqual(parsed["period_end"], 5)
        self.assertTrue(parsed["available_only"])
        self.assertNotIn("keyword", parsed)

    def test_teacher_and_explicit_period(self):
        parsed = parse_natural_query("找张三老师周四第11-12节的课")
        self.assertEqual(parsed["teacher"], "张三")
        self.assertEqual(parsed["day"], 4)
        self.assertEqual(parsed["period_start"], 11)
        self.assertEqual(parsed["period_end"], 12)
        self.assertNotIn("keyword", parsed)

    def test_single_character_teacher(self):
        parsed = parse_natural_query("王老师周五晚上的课")
        self.assertEqual(parsed["teacher"], "王")
        self.assertEqual(parsed["day"], 5)
        self.assertEqual(parsed["period_start"], 11)
        self.assertEqual(parsed["period_end"], 14)

    def test_exact_credits_preserves_literal_keyword(self):
        parsed = parse_natural_query("张江本科 AI 3 学分")
        self.assertEqual(parsed["keyword"], "AI")
        self.assertEqual(parsed["min_credits"], 3.0)
        self.assertEqual(parsed["max_credits"], 3.0)

    def test_preserves_course_name_containing_course_word(self):
        parsed = parse_natural_query("找课程设计")
        self.assertEqual(parsed["keyword"], "课程设计")

    def test_rejects_invalid_period(self):
        with self.assertRaises(ValueError):
            parse_natural_query("周三第 18 节的课")


if __name__ == "__main__":
    unittest.main()
