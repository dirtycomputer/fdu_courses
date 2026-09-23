import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from server.query_contract import QUERY_SCHEMA, decode_filters, validate_filters


class QueryContractTests(unittest.TestCase):
    def test_schema_is_valid(self):
        Draft202012Validator.check_schema(QUERY_SCHEMA)
        static_path = Path(__file__).resolve().parents[1] / 'docs' / 'query-schema.json'
        self.assertEqual(json.loads(static_path.read_text(encoding='utf-8')), QUERY_SCHEMA)

    def test_llm_teacher_output_has_no_synthetic_keyword(self):
        # The calling LLM produces this object from “查询黄萱菁老师的所有课程”.
        result = decode_filters('{"teacher":"黄萱菁","limit":50}')
        self.assertEqual(result, {"teacher": "黄萱菁", "limit": 50, "offset": 0})

    def test_composite_filter_object_is_preserved(self):
        filters = {"campus": "张江校区", "biz_type": "本科", "day": 3,
                   "period_start": 6, "period_end": 10, "week": 5,
                   "min_credits": 3, "max_credits": 4, "keyword": "人工智能",
                   "available_only": True, "has_syllabus": False, "limit": 10, "offset": 0}
        self.assertEqual(decode_filters(json.dumps(filters)), filters)

    def test_invalid_objects_fail_instead_of_widening_query(self):
        cases = [
            "查询黄萱菁老师的所有课程", [], None, 5,
            {"query": "王老师的课"}, {"teacher": None}, {"teacher": "  "},
            {"campus": "张江"}, {"campus": ["张江校区", "邯郸校区"]},
            {"day": True}, {"day": "3"}, {"day": 0}, {"day": 8},
            {"period_start": 18}, {"week": 31}, {"min_credits": -1},
            {"available_only": "false"}, {"has_syllabus": 0},
            {"limit": 0}, {"limit": 51}, {"limit": 2.5},
            {"offset": -1}, {"offset": False}, {"offset": 2147483648},
            {"min_credits": 4, "max_credits": 3},
            {"period_start": 10, "period_end": 6},
            {"min_credits": float("nan")}, {"max_credits": float("inf")},
            {"keyword_includes_teacher": True}, {"sql": "SELECT * FROM courses"},
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_filters(value)

    def test_invalid_serialization_and_duplicate_fields(self):
        for raw in ['{"day":1,"day":2}', '{"min_credits":NaN}',
                    '{"max_credits":Infinity}', '{"min_credits":1e999}',
                    '```json\n{"teacher":"王"}\n```', '{', ' ' * 10001]:
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                decode_filters(raw)

    def test_json_schema_integral_float_is_normalized_for_sqlite(self):
        self.assertEqual(decode_filters('{"day":3.0,"offset":1.0}')['offset'], 1)
        self.assertIs(type(decode_filters('{"day":3.0}')['day']), int)


if __name__ == '__main__':
    unittest.main()
