from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

CAMPUS_ALIASES = {
    "邯郸校区": "邯郸校区",
    "邯郸": "邯郸校区",
    "张江校区": "张江校区",
    "张江": "张江校区",
    "枫林校区": "枫林校区",
    "枫林": "枫林校区",
    "江湾校区": "江湾校区",
    "江湾": "江湾校区",
    "其他校区": "其他校区",
}

DAY_ALIASES = {
    "周一": 1,
    "星期一": 1,
    "礼拜一": 1,
    "周二": 2,
    "星期二": 2,
    "礼拜二": 2,
    "周三": 3,
    "星期三": 3,
    "礼拜三": 3,
    "周四": 4,
    "星期四": 4,
    "礼拜四": 4,
    "周五": 5,
    "星期五": 5,
    "礼拜五": 5,
    "周六": 6,
    "星期六": 6,
    "礼拜六": 6,
    "周日": 7,
    "周天": 7,
    "星期日": 7,
    "星期天": 7,
    "礼拜日": 7,
    "礼拜天": 7,
}

TIME_ALIASES = {
    "上午": (1, 5),
    "早上": (1, 5),
    "早晨": (1, 5),
    "下午": (6, 10),
    "晚上": (11, 14),
    "晚间": (11, 14),
}

STOP_PHRASES = (
    "帮我找一下",
    "帮我找",
    "帮我查一下",
    "帮我查",
    "查询一下",
    "查询",
    "找一下",
    "查一下",
    "我想看看",
    "我想看",
    "我想找",
    "我想上",
    "有没有",
    "有哪些",
    "有什么",
    "可以上的",
    "能上的",
    "开设的",
    "最好是",
    "最好和",
    "最好",
    "相关的",
    "相关",
    "课程",
    "教学班",
    "给我",
    "看看",
    "一下",
    "课",
)


@dataclass
class ParsedCourseQuery:
    keyword: str | None = None
    teacher: str | None = None
    department: str | None = None
    campus: str | None = None
    biz_type: str | None = None
    min_credits: float | None = None
    max_credits: float | None = None
    day: int | None = None
    period_start: int | None = None
    period_end: int | None = None
    week: int | None = None
    has_syllabus: bool | None = None
    available_only: bool = False
    limit: int = 20

    def filters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None and not (key == "available_only" and value is False)
        }


def _consume(text: str, pattern: str) -> tuple[str, re.Match[str] | None]:
    match = re.search(pattern, text)
    if not match:
        return text, None
    return text[: match.start()] + " " + text[match.end() :], match


def parse_course_query(text: str, *, default_limit: int = 20) -> ParsedCourseQuery:
    original = (text or "").strip()
    if not original:
        raise ValueError("query cannot be empty")

    work = original
    result = ParsedCourseQuery(limit=max(1, min(int(default_limit), 50)))

    for alias in sorted(CAMPUS_ALIASES, key=len, reverse=True):
        if alias in work:
            result.campus = CAMPUS_ALIASES[alias]
            work = work.replace(alias, " ", 1)
            break

    for alias in sorted(DAY_ALIASES, key=len, reverse=True):
        if alias in work:
            result.day = DAY_ALIASES[alias]
            work = work.replace(alias, " ", 1)
            break

    work, match = _consume(work, r"第\s*(\d{1,2})\s*周")
    if match:
        result.week = int(match.group(1))

    work, match = _consume(
        work,
        r"(?:第\s*)?(\d{1,2})\s*(?:-|—|–|~|～|到|至)\s*(\d{1,2})\s*节",
    )
    if match:
        result.period_start = int(match.group(1))
        result.period_end = int(match.group(2))
    else:
        work, match = _consume(work, r"第?\s*(\d{1,2})\s*节")
        if match:
            result.period_start = result.period_end = int(match.group(1))
        else:
            for alias, (start, end) in TIME_ALIASES.items():
                if alias in work:
                    result.period_start, result.period_end = start, end
                    work = work.replace(alias, " ", 1)
                    break

    biz_patterns = (
        (r"(?:本科生|本科)(?:能上|可选|课程)?", "本科"),
        (r"(?:研究生|硕士生?|博士生?)(?:能上|可选|课程)?", "研究生"),
        (r"本研融通", "本研融通"),
    )
    for pattern, value in biz_patterns:
        work2, match = _consume(work, pattern)
        if match:
            result.biz_type = value
            work = work2
            break

    credit_patterns = (
        (r"(?:至少|不少于|>=?|≥)\s*(\d+(?:\.\d+)?)\s*学分", "min"),
        (r"(\d+(?:\.\d+)?)\s*学分\s*(?:以上|起)", "min"),
        (r"(?:至多|不超过|<=?|≤)\s*(\d+(?:\.\d+)?)\s*学分", "max"),
        (r"(\d+(?:\.\d+)?)\s*学分\s*(?:以下|以内)", "max"),
        (r"(\d+(?:\.\d+)?)\s*学分", "exact"),
    )
    for pattern, kind in credit_patterns:
        work2, match = _consume(work, pattern)
        if not match:
            continue
        value = float(match.group(1))
        if kind == "min":
            result.min_credits = value
        elif kind == "max":
            result.max_credits = value
        else:
            result.min_credits = value
            result.max_credits = value
        work = work2
        break

    if re.search(r"(?:有|带|提供)(?:教学)?大纲", work):
        result.has_syllabus = True
        work = re.sub(r"(?:有|带|提供)(?:教学)?大纲", " ", work, count=1)

    if re.search(r"(?:有余量|有名额|没满|未满员|还能选|可以选)", work):
        result.available_only = True
        work = re.sub(
            r"(?:有余量|有名额|没满|未满员|还能选|可以选)",
            " ",
            work,
            count=1,
        )

    work2, match = _consume(work, r"([\u4e00-\u9fffA-Za-z·]{2,20})\s*老师")
    if match:
        result.teacher = match.group(1)
        work = work2
    else:
        work2, match = _consume(work, r"老师\s*([\u4e00-\u9fffA-Za-z·]{2,20})")
        if match:
            result.teacher = match.group(1)
            work = work2

    work2, match = _consume(work, r"(?:最多|前)\s*(\d{1,2})\s*(?:门|个)?")
    if match:
        result.limit = max(1, min(int(match.group(1)), 50))
        work = work2

    for phrase in STOP_PHRASES:
        work = work.replace(phrase, " ")
    work = re.sub(r"[，。！？、,!?;；:：()（）\[\]【】“”\"'‘’]", " ", work)
    work = re.sub(r"\s+", " ", work).strip(" -—–~～的和与及想要上")

    if work:
        result.keyword = work

    return result
