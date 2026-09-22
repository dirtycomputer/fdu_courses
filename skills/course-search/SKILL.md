---
name: course-search
description: Search Fudan University teaching classes accurately using the FDU Courses service.
---

Use the FDU Courses MCP server or REST API to answer requests about currently published Fudan University teaching classes.

Prefer structured filters over broad text matching whenever the user specifies campus, degree type, weekday, period, teaching week, credits, teacher, department, syllabus availability, or seat availability.

For natural-language topic searches, preserve the user's literal topic words. If the user explicitly names a teacher, use the teacher filter instead of treating the name as a topic keyword.

Time conventions:
- day: 1=Monday through 7=Sunday.
- periods: 1 through 14.
- morning usually maps to periods 1-5.
- noon usually maps to periods 5-6.
- afternoon usually maps to periods 6-10.
- evening usually maps to periods 11-14.
- when weekday, period and week are all supplied, require them to match the same class session.

When reporting results, include at least the course name, teacher, credits, campus, and concrete schedule when available. If the query returns zero matches, say so and suggest which explicit filter could be relaxed; do not fabricate nearby courses.

Treat the service as public read-only course information. Do not infer that a user is eligible to enroll merely because a teaching class exists or has remaining capacity.
