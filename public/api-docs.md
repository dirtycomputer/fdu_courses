# FDU Courses Public API v2

Base URL: `https://fducourses.vercel.app`. Public, read-only, no authentication.

## LLM → JSON → query

The calling AI tool (ChatGPT, Claude, Gemini, 豆包, DeepSeek, etc.) uses its own LLM to interpret user intent and produce a filter JSON object. The backend only validates that object and queries SQLite. It contains no natural-language parser and requires no separate LLM API key.

- JSON Schema: `GET /api/query-schema`
- Static copy of the same schema: `https://dirtycomputer.github.io/fdu_courses/query-schema.json`
- AI instructions: `https://dirtycomputer.github.io/fdu_courses/?view=ai`
- Browser JSON executor: `https://fducourses.vercel.app/`

For “查询黄萱菁老师的所有课程”, the LLM should produce:

```json
{"teacher":"黄萱菁","limit":50}
```

For “周三下午张江校区至少3学分的本科人工智能课程，最多10门”:

```json
{"keyword":"人工智能","campus":"张江校区","biz_type":"本科","min_credits":3,"day":3,"period_start":6,"period_end":10,"limit":10}
```

These examples demonstrate intended LLM outputs; they are not hard-coded sentence mappings. Unspecified conditions must be omitted. “所有”, “本学期” and presentation instructions must not become keywords. Unsupported or ambiguous conditions require clarification or explicit additional processing, not silent removal.

## Execute structured JSON

```bash
curl 'https://fducourses.vercel.app/api/courses' \
  -H 'Content-Type: application/json' \
  -d '{"teacher":"黄萱菁","limit":50}'
```

For clients restricted to GET:

```bash
curl --get 'https://fducourses.vercel.app/api/courses' \
  --data-urlencode 'filters={"teacher":"黄萱菁","limit":50}'
```

POST accepts the filter object itself, not a wrapper. GET accepts a single URL-encoded `filters` JSON value. Never mix it with flat parameters. Unknown fields, invalid types/enums/ranges, duplicate JSON keys, non-finite numbers, nulls and conflicting bounds return HTTP 400 before any enrollment refresh or database query.

| Field | Meaning / constraints |
|---|---|
| `keyword` | Course name/code substrings; whitespace-separated tokens use AND |
| `teacher`, `department` | Explicit teacher / department substring |
| `campus` | 邯郸校区 / 张江校区 / 枫林校区 / 江湾校区 / 其他校区 |
| `biz_type` | 本科 / 研究生 / 本研融通 |
| `min_credits`, `max_credits` | Non-negative numbers; min ≤ max |
| `day` | Integer 1–7, Monday–Sunday |
| `period_start`, `period_end` | Integer 1–14; start ≤ end; overlap matching |
| `week` | Integer teaching week 1–30 |
| `has_syllabus`, `available_only` | JSON booleans |
| `limit` | Integer 1–50; default 20 |
| `offset` | Integer 0–2147483647; default 0 |

All fields combine with AND. Weekday, period and week must match the same session. For OR across campuses/days, the LLM must make separate requests and deduplicate by teaching-class id. Exact credits require identical min and max. Strict non-overlap and exclusions require explicit extra processing or clarification.

Responses include `filters` (validated filters with defaults), `semester`, `generated_at`, `total`, `returned`, `offset`, `has_more`, `courses`, and enrollment metadata. For “all” results, request limit=50, increment offset by returned until has_more=false, and report any incomplete retrieval. Concurrent dataset changes may affect page boundaries.

## Enrollment freshness

`enrolled` / `limit` are the latest available values, not guaranteed live values. Inspect:

- `enrollment_updated_at`: time of the data used.
- `enrollment_source`: `live-cache` (within TTL), `stale-cache` (refresh failed), or `snapshot` (dataset values).
- `enrollment_cache_ttl_seconds`: normally 300.
- `enrollment_error`: upstream refresh error, when present.

Never describe stale/static values as real-time seats. `available_only=true` is evaluated against the available values after overrides are applied; it does not guarantee current availability or enrollment eligibility.

## Migration

Natural-language `/api/ask?q=...` and `POST /api/ask {"query":"..."}` are no longer supported. `/api/ask` remains a deprecated URL alias for structured JSON POST or GET `?filters=...`. The response uses `filters`, not heuristic `parsed` output. Update callers before deployment.

Legacy flat `GET /api/courses?teacher=黄萱菁&limit=50` remains supported. In that legacy mode `q` aliases `keyword`, and keywords can still match teacher names. New JSON queries match keywords against course names/codes only; use `teacher` explicitly.

## Other endpoints

- `GET /api/course/{identifier}`: teaching-class ID/code or course code.
- `GET /health`: dataset version and count.
- `GET /openapi.json`: OpenAPI 3.1; includes the same JSON Schema.
- `/mcp`: native MCP tools `search_courses` and `get_course`. The calling LLM creates structured tool arguments directly. `search_courses` supports `offset` pagination and validates filters against the shared contract.
