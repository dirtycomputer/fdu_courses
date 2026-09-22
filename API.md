# FDU Courses Public API

Production base URL: `https://fducourses.vercel.app`

The API is public, read-only, and requires no authentication.

## Zero-install web search

Open:

```text
https://fducourses.vercel.app/
```

Enter a Chinese natural-language query such as:

```text
找周三下午张江校区、3 学分以上、本科生能上的人工智能相关课程，最多 10 门
```

The page shows the parsed filters before the results so the interpretation is inspectable.

## Natural-language API

### GET

```bash
curl --get 'https://fducourses.vercel.app/api/ask' \
  --data-urlencode 'q=找周三下午张江校区、3 学分以上、本科生能上的人工智能相关课程，最多 10 门'
```

### POST

```bash
curl 'https://fducourses.vercel.app/api/ask' \
  -H 'Content-Type: application/json' \
  -d '{"query":"找周三下午张江校区、3 学分以上、本科生能上的人工智能相关课程，最多 10 门"}'
```

The response contains both `parsed` and `courses`:

```json
{
  "query": "...",
  "parsed": {
    "campus": "张江校区",
    "biz_type": "本科",
    "day": 3,
    "period_start": 6,
    "period_end": 10,
    "min_credits": 3.0,
    "keyword": "人工智能",
    "limit": 10
  },
  "total": 12,
  "returned": 10,
  "courses": []
}
```

The parser currently handles common expressions for campus, undergraduate/graduate type, weekday, morning/afternoon/evening, explicit periods, teaching week, credit bounds, teacher, syllabus availability, seat availability, result limit, and free-text keywords.

## Structured search API

```bash
curl --get 'https://fducourses.vercel.app/api/courses' \
  --data-urlencode 'q=人工智能' \
  --data-urlencode 'campus=张江校区' \
  --data-urlencode 'biz_type=本科' \
  --data-urlencode 'day=3' \
  --data-urlencode 'period_start=6' \
  --data-urlencode 'period_end=10' \
  --data-urlencode 'min_credits=3' \
  --data-urlencode 'limit=10'
```

Supported query parameters:

- `q` / `keyword`
- `teacher`
- `department`
- `campus`: `邯郸校区`, `张江校区`, `枫林校区`, `江湾校区`, `其他校区`
- `biz_type`: `本科`, `研究生`, `本研融通`
- `min_credits`, `max_credits`
- `day`: 1 (Monday) through 7 (Sunday)
- `period_start`, `period_end`: 1 through 14
- `week`: teaching week
- `has_syllabus`: boolean
- `available_only`: boolean
- `limit`: 1 through 50

## Course detail

```bash
curl 'https://fducourses.vercel.app/api/course/<teaching-class-id-or-code>'
```

The identifier may be a teaching-class numeric ID, teaching-class code, or course code.

## OpenAPI

Machine-readable schema:

```text
https://fducourses.vercel.app/openapi.json
```

AI/agent platforms that accept an OpenAPI schema can import this URL and call the REST API without using MCP.

## MCP

The existing MCP endpoint remains available:

```text
https://fducourses.vercel.app/mcp
```

REST and MCP use the same SQLite query layer.
