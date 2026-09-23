import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from starlette.testclient import TestClient

from api import index as api
from server.enrollment import EnrollmentSnapshot
from server.query_contract import QUERY_SCHEMA
import test_query as query_tests


class StructuredApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def setUp(self):
        self.fixture = query_tests.QueryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('server.db.DEFAULT_DB_PATH', self.fixture.db))
        self.snapshot = self.stack.enter_context(patch.object(api, 'get_enrollment_snapshot', return_value=EnrollmentSnapshot(
            values={}, updated_at='', fresh=False, ttl_seconds=300, error='test upstream unavailable')))

    def test_post_and_encoded_get_execute_identical_llm_json(self):
        filters = {"teacher": "张三", "campus": "张江校区", "day": 3,
                   "period_start": 6, "period_end": 10, "week": 3,
                   "min_credits": 3, "limit": 50}
        post = self.client.post('/api/courses', json=filters)
        get = self.client.get('/api/courses', params={'filters': json.dumps(filters, ensure_ascii=False)})
        self.assertEqual(post.status_code, 200, post.text)
        self.assertEqual(get.json(), post.json())
        data = post.json()
        self.assertEqual([c['id'] for c in data['courses']], [1])
        self.assertNotIn('keyword', data['filters'])
        self.assertEqual(data['enrollment_source'], 'snapshot')
        self.assertIn('enrollment_error', data)
        self.assertNotIn('parsed', data)

    def test_invalid_filters_fail_before_upstream_fetch(self):
        for payload in [{"query": "王老师的课"}, {"day": "3"}, {"day": True},
                        {"limit": 0}, {"max_credits": 1, "min_credits": 2},
                        {"campus": "不存在"}, [1, 2]]:
            with self.subTest(payload=payload):
                response = self.client.post('/api/courses', json=payload)
                self.assertEqual(response.status_code, 400, response.text)
        self.snapshot.assert_not_called()

    def test_old_natural_language_endpoint_has_actionable_error(self):
        result = self.client.get('/api/ask', params={'q': '查询黄萱菁老师的所有课程'})
        self.assertEqual(result.status_code, 400)
        self.assertIn('/api/query-schema', result.json()['error'])
        self.assertEqual(self.client.post('/api/ask', json={'query': '王老师的课'}).status_code, 400)
        self.snapshot.assert_not_called()

    def test_structured_ask_alias(self):
        result = self.client.post('/api/ask', json={'teacher': '张三'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['total'], 1)

    def test_json_topic_does_not_match_teacher_legacy_get_still_does(self):
        self.assertEqual(self.client.post('/api/courses', json={'keyword': '张三'}).json()['total'], 0)
        self.assertEqual(self.client.get('/api/courses', params={'q': '张三'}).json()['total'], 1)

    def test_pagination_does_not_omit_or_duplicate_results(self):
        first = self.client.post('/api/courses', json={'limit': 1}).json()
        second = self.client.post('/api/courses', json={'limit': 1, 'offset': 1}).json()
        empty = self.client.post('/api/courses', json={'limit': 1, 'offset': 2}).json()
        self.assertEqual(first['total'], 2)
        self.assertTrue(first['has_more'])
        self.assertFalse(second['has_more'])
        self.assertEqual({c['id'] for page in [first, second] for c in page['courses']}, {1, 2})
        self.assertEqual(empty['returned'], 0)
        self.assertFalse(empty['has_more'])

    def test_available_pagination_is_after_enrollment_overrides(self):
        self.snapshot.return_value = EnrollmentSnapshot(
            values={1: {'enrolled': 0, 'limit': 60}, 2: {'enrolled': 0, 'limit': 30}},
            updated_at='2026-09-23T12:00:00+08:00', fresh=True, ttl_seconds=300)
        result = self.client.post('/api/courses', json={'available_only': True, 'limit': 1, 'offset': 1}).json()
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['returned'], 1)
        self.assertFalse(result['has_more'])
        self.assertEqual(result['enrollment_source'], 'live-cache')

    def test_schema_openapi_and_cors(self):
        self.assertEqual(self.client.get('/api/query-schema').json(), QUERY_SCHEMA)
        spec = self.client.get('/api/openapi.json').json()
        self.assertEqual(spec['paths']['/api/courses']['post']['requestBody']['content']['application/json']['schema'], QUERY_SCHEMA)
        for url in ['/api/courses', '/api/ask', '/api/query-schema']:
            response = self.client.options(url)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')

    def test_ambiguous_or_malformed_requests_fail(self):
        for url in ['/api/courses?filters=%7B%7D&day=3', '/api/courses?day=3&day=4',
                    '/api/courses?filters=%7B%7D&filters=%7B%7D', '/api/courses?foo=x',
                    '/api/courses?day=', '/api/courses?min_credits=nan',
                    '/api/courses?q=AI&keyword=AI']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 400)
        for raw in ['{', '{"day":1,"day":2}', 'null', '{"limit":true}']:
            self.assertEqual(self.client.post('/api/courses', content=raw).status_code, 400)
        self.assertEqual(self.client.post('/api/courses?day=3', json={}).status_code, 400)
        self.snapshot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
