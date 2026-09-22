#!/usr/bin/env python3
"""抓取复旦全校开课查询数据,生成前端静态 JSON。

用法:
    python3 fetch/fetch.py [--semester 527] [--name "2026-2027学年1学期"]
                           [--start 2026-09-07] [--out docs/data/latest.json]

数据源(免登录):
    https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search/semester/{sid}/search/{sid}
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://fdjwgl.fudan.edu.cn"
SEARCH_URL = BASE + "/student/for-all/lesson-search/semester/{sid}/search/{sid}"
CAMPUS_NAMES = {1: "邯郸校区", 2: "张江校区", 3: "枫林校区", 4: "江湾校区", 5: "其他校区"}
PERIOD_TIMES = [
    "08:00", "08:55", "09:55", "10:50", "11:45", "13:30", "14:25", "15:25",
    "16:20", "17:15", "18:30", "19:25", "20:20", "21:15",
]
PERIOD_END_TIMES = [
    "08:45", "09:40", "10:40", "11:35", "12:30", "14:15", "15:10", "16:10",
    "17:05", "18:00", "19:15", "20:10", "21:05", "22:00",
]
DAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}

LINE_RE = re.compile(
    r"^(?:#\S+\s+)?"
    r"(?P<weeks>[\d,~\-()单双]+周)\s+"
    r"(?P<day>星期[一二三四五六日天])\s+"
    r"(?P<period>第?\s*[\d,~\-]+\s*节)\s*"
    r"(?P<rest>.*)$"
)


def http_get_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fdu-courses fetcher)"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1} after error: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))


def parse_weeks(text):
    """'1~2,4~6(双),7~11(单),12~13,15~16周' -> sorted set of week numbers"""
    weeks = set()
    body = text.rstrip("周")
    for seg in re.split(r"[,，]", body):
        m = re.fullmatch(r"(\d+)~(\d+)(?:\((单|双)\))?", seg)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            parity = m.group(3)
            for w in range(lo, hi + 1):
                if parity == "单" and w % 2 == 0:
                    continue
                if parity == "双" and w % 2 == 1:
                    continue
                weeks.add(w)
            continue
        m = re.fullmatch(r"(\d+)(?:\((单|双)\))?", seg)
        if m:
            w = int(m.group(1))
            parity = m.group(2)
            if parity == "单" and w % 2 == 0:
                continue
            if parity == "双" and w % 2 == 1:
                continue
            weeks.add(w)
            continue
        return None  # unknown segment -> give up on this line
    return sorted(weeks) if weeks else None


def parse_period(text):
    """'3~5节' -> (3, 5)"""
    t = text.replace("第", "").replace("节", "").strip()
    if "~" in t or "-" in t:
        parts = re.split(r"[~\-]", t)
        return int(parts[0]), int(parts[-1])
    p = int(t)
    return p, p


def parse_line(line):
    """Parse one schedule line -> session dict or None."""
    line = line.strip()
    if not line:
        return None
    m = LINE_RE.match(line)
    if not m:
        return None
    weeks = parse_weeks(m.group("weeks"))
    if not weeks:
        return None
    day = DAY_MAP.get(m.group("day")[2])
    if not day:
        return None
    p_start, p_end = parse_period(m.group("period"))
    rest = m.group("rest").strip()
    room, teachers_str = "", ""
    if rest:
        tokens = rest.split()
        if len(tokens) >= 2:
            room = tokens[0]
            teachers_str = " ".join(tokens[1:])
        else:
            teachers_str = tokens[0]
    teachers = [t for t in re.split(r"[,，、]", teachers_str) if t] if teachers_str else []
    return {
        "day": day,
        "p": [p_start, p_end],
        "weeks": weeks,
        "room": room,
    }


def clean(s):
    if not s:
        return ""
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


BJ = timezone(timedelta(hours=8))


def bj_now_str():
    return datetime.now(BJ).strftime("%Y-%m-%d %H:%M")


def course_record(row, campus_set, syllabus_ids, unparsed_lines):
    course = row.get("course") or {}
    raw = row.get("scheduleText", {}).get("dateTimePlacePersonText", {}).get("textZh", "") or ""

    sessions = []
    for line in re.split(r"[\n;；]+", raw):
        if not line.strip():
            continue
        s = parse_line(line)
        if s:
            sessions.append(s)
        else:
            unparsed_lines.append(f"[{row.get('code')}] {line.strip()}")

    teachers = []
    for ta in row.get("teacherAssignmentList") or []:
        person = ta.get("person") or {}
        if person.get("nameZh"):
            teachers.append(person["nameZh"])

    campuses = sorted(campus_set)
    return {
        "id": row["id"],
        "code": row.get("code") or "",
        "courseCode": course.get("code") or "",
        "name": course.get("nameZh") or row.get("nameZh") or "",
        "teachers": teachers,
        "credits": course.get("credits"),
        "department": (row.get("openDepartment") or {}).get("nameZh") or "",
        "bizType": row.get("lessonCrossBizTypeName") or "",
        "courseType": clean((row.get("courseType") or {}).get("nameZh", "")) if row.get("courseType") else "",
        "tableType": clean((course.get("courseTableType") or {}).get("nameZh", "")) if course.get("courseTableType") else "",
        "examMode": clean((row.get("examMode") or {}).get("nameZh", "")) if row.get("examMode") else "",
        "limit": row.get("limitCount"),
        "enrolled": row.get("stdCount"),
        "lang": (row.get("teachLang") or {}).get("nameZh") or "",
        "hasSyllabus": row["id"] in syllabus_ids,
        "selectionLimit": clean(row.get("selectionLimit") or ""),
        "remark": clean(row.get("remark") or "") or None,
        "rawSchedule": raw.strip(),
        "campuses": campuses,
        "sessions": sessions,
    }


def fetch_all(sid, extra_query=""):
    url = SEARCH_URL.format(sid=sid) + f"?queryPage__=1,20000{extra_query}"
    t0 = time.time()
    data = http_get_json(url)
    rows = data["data"]
    print(f"  fetched {len(rows)} rows ({data['_page_']['totalRows']} total) in {time.time() - t0:.1f}s")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semester", type=int, default=527)
    ap.add_argument("--name", default="2026-2027学年1学期")
    ap.add_argument("--start", default="2026-09-07", help="第1周周一日期 YYYY-MM-DD")
    ap.add_argument("--out", default="docs/data/latest.json")
    args = ap.parse_args()

    sid = args.semester
    print(f"semester {sid} ({args.name}), week1 Monday = {args.start}")

    print("[1/4] full course list ...")
    rows = fetch_all(sid)

    print("[2/4] campus attribution ...")
    campus_map = {}  # lesson id -> set of campus ids
    for cid, cname in CAMPUS_NAMES.items():
        crows = fetch_all(sid, f"&campusAssoc={cid}")
        for r in crows:
            campus_map.setdefault(r["id"], set()).add(cid)
        time.sleep(1)

    print("[3/4] syllabus ids ...")
    srows = fetch_all(sid, "&teachingSyllabus=1")
    syllabus_ids = {r["id"] for r in srows}

    print("[4/4] parse & merge ...")
    unparsed_lines = []
    courses = [course_record(r, campus_map.get(r["id"], set()), syllabus_ids, unparsed_lines) for r in rows]

    departments = sorted({c["department"] for c in courses if c["department"]})
    n_no_sessions = sum(1 for c in courses if not c["sessions"])
    parsed_lines = sum(len(c["sessions"]) for c in courses)
    total_lines = parsed_lines + len(unparsed_lines)

    out = {
        "semester": args.name,
        "semesterId": sid,
        "week1Monday": args.start,
        "generatedAt": bj_now_str(),
        "periodTimes": PERIOD_TIMES,
        "periodEndTimes": PERIOD_END_TIMES,
        "campusNames": [CAMPUS_NAMES[i] for i in sorted(CAMPUS_NAMES)],
        "departments": departments,
        "courses": courses,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print()
    print(f"courses        : {len(courses)}")
    print(f"with sessions  : {len(courses) - n_no_sessions}")
    print(f"with syllabus  : {len(syllabus_ids)}")
    print(f"lines parsed   : {parsed_lines}/{total_lines} ({len(unparsed_lines)} failed)")
    print(f"output         : {args.out}")
    if unparsed_lines:
        print("\nUNPARSED SAMPLE (first 20):")
        for l in unparsed_lines[:20]:
            print(" ", l)


if __name__ == "__main__":
    main()
