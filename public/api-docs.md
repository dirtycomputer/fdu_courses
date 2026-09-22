# FDU Courses API

Public read-only API for querying Fudan University teaching classes. No authentication is required.

Base URL: `https://fducourses.vercel.app`

## Natural-language query

Use this first when the user gives a Chinese free-form request.

`GET /api/ask?q=<query>&limit=<1-50>`

Example:

`GET /api/ask?q=张江研究生%20AI%203%20学分&limit=5`

The response contains:

- `query`: original request
- `parsed`: interpreted structured filters
- `semester`, `generated_at`: data version
- `total`, `returned`: match counts
- `courses`: matching teaching classes

Always inspect `parsed` before relying on the result. If it does not reflect the user's intent, call the structured endpoint directly.

## Structured search

`GET /api/courses`

Supported query parameters:

- `q` or `keyword`: course-name / code keyword; this structured endpoint also supports teacher-name matches for backward compatibility
- `teacher`
- `department`
- `campus`: `邯郸校区`, `张江校区`, `枫林校区`, `江湾校区`, `其他校区`
- `biz_type`: `本科`, `研究生`, `本研融通`
- `min_credits`, `max_credits`
- `day`: 1=Monday ... 7=Sunday
- `period_start`, `period_end`: 1-14
- `week`: teaching week
- `has_syllabus`: boolean
- `available_only`: boolean
- `limit`: 1-50

When day, period and week filters are combined, they are required to match the same session. A requested period range matches a session when the intervals overlap.

Example:

`GET /api/courses?campus=张江校区&biz_type=研究生&min_credits=3&day=5&period_start=3&period_end=5&limit=10`

## Course details

`GET /api/course/{identifier}`

`identifier` may be a teaching-class numeric ID, teaching-class code, or course code.

Example:

`GET /api/course/1052879`

## Data health

`GET /health`

Returns current semester, dataset generation time and total teaching-class count.

## Machine-readable schema

OpenAPI 3.1 schema: `https://fducourses.vercel.app/openapi.json`

## MCP

Streamable HTTP MCP endpoint: `https://fducourses.vercel.app/mcp`

Use MCP only when the client natively supports it. For generic web-capable agents, the REST API is simpler.
