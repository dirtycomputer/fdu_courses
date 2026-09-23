# FDU Courses API

Public read-only API for querying Fudan University teaching classes. No authentication is required.

Base URL: `https://fducourses.vercel.app`

## Enrollment freshness

Course structure (name, teacher, schedule, campus, credits, etc.) is read from the generated SQLite dataset. Enrollment and capacity are refreshed separately from Fudan's public course-search endpoint.

- `enrolled`: latest fetched enrolled count
- `limit`: latest fetched capacity
- `enrollment_updated_at`: time the latest enrollment snapshot was fetched
- `enrollment_source`: `live-cache`, `stale-cache`, or `snapshot`
- `enrollment_cache_ttl_seconds`: normally `300`

The live enrollment snapshot is cached for 5 minutes. If the upstream endpoint temporarily fails, the service falls back to the latest cached enrollment snapshot. If no live cache exists, snapshot values from `generated_at` are returned.

## Natural-language query

Use this first when the user gives a Chinese free-form request.

`GET /api/ask?q=<query>&limit=<1-50>`

Example:

`GET /api/ask?q=张江研究生%20AI%203%20学分&limit=5`

The response contains:

- `query`: original request
- `parsed`: interpreted structured filters
- `semester`, `generated_at`: course-structure data version
- `enrollment_updated_at`, `enrollment_source`, `enrollment_cache_ttl_seconds`: enrollment freshness
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
- `available_only`: boolean; evaluated after the latest enrollment snapshot is applied
- `limit`: 1-50

When day, period and week filters are combined, they are required to match the same session. A requested period range matches a session when the intervals overlap.

Example:

`GET /api/courses?campus=张江校区&biz_type=研究生&min_credits=3&day=5&period_start=3&period_end=5&limit=10`

## Course details

`GET /api/course/{identifier}`

`identifier` may be a teaching-class numeric ID, teaching-class code, or course code.

Example:

`GET /api/course/1052879`

Course-detail responses also include the enrollment freshness fields described above.

## Data health

`GET /health`

Returns current semester, dataset generation time and total teaching-class count. Health does not itself force an enrollment refresh.

## Machine-readable schema

OpenAPI 3.1 schema: `https://fducourses.vercel.app/openapi.json`

## MCP

Streamable HTTP MCP endpoint: `https://fducourses.vercel.app/mcp`

MCP tools use the same 5-minute enrollment cache as the REST API and return `enrollment_updated_at`.

Use MCP only when the client natively supports it. For generic web-capable agents, the REST API is simpler.
