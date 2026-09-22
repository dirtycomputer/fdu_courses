from __future__ import annotations

import re
from typing import Any

DAY_ALIASES = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "日": 7,
    "天": 7,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
}

CAMPUS_ALIASES = {
    "邯郸": "邯郸校区",
    "张江": "张江校区",
    "枫林": "枫林校区",
    "江湾": "江湾校区",
    "其他校区": "其他校区",
}

BIZ_PATTERNS = (
    (re.compile(r"本研融通"), "本研融通"),
    (re.compile(r"本科(?:生)?"), "本科"),
    (re.compile(r"研究生|硕士|博士"), "研究生"),
)

GENERIC_WORDS = (
    "请帮我",
    "帮我",
    "我想看看",
    "我想找",
    "我要",
    "想找",
    "请",
    "查询",
    "查找",
    "搜索",
    "找找",
    "找",
    "看看",
    "看",
    "一下",
    "教学班",
    "课程",
    "能上的",
    "可以上的",
    "可上的",
    "相关的",
    "相关",
    "最好",
    "给我",
    "有哪些",
    "课",
)


def _strip_span(text: str, match: re.Match[str]) -> str:
    return text[: match.start()] + " " * (match.end() - match.start()) + text[match.end() :]


def _clean_keyword(text: str) -> str | None:
    cleaned = re.sub(r"[，。！？、,;；:：()（）\[\]{}<>《》]", " ", text)
    for word in GENERIC_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"最多\s*\d+\s*门?", " ", cleaned)
    cleaned = re.sub(r"前\s*\d+\s*门?", " ", cleaned)
    cleaned = re.sub(r"返回\s*\d+\s*门?", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" 的地得")
    if not cleaned:
        return None

    aliases = {
        "ai": "人工智能",
        "ml": "机器学习",
    }
    parts = []
    for token in cleaned.split():
        parts.append(aliases.get(token.lower(), token))
    return " ".join(parts) or None


def _teacher_name(raw: str) -> str | None:
    name = raw.strip()
    prefixes = (
        "请帮我找",
        "帮我找",
        "我想看看",
        "我想找",
        "我要",
        "想找",
        "请找",
        "查询",
        "查找",
        "找",
        "查",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :].strip()
                changed = True
                break
    if 1 <= len(name) <= 4:
        return name
    return None


def parse_natural_query(query: str, *, default_limit: int = 20) -> dict[str, Any]:
    """Parse common Chinese course-search expressions into search_courses kwargs.

    The parser deliberately extracts only high-confidence constraints. The
    remaining text becomes the keyword query and should be returned to the user
    so the interpretation is transparent.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query cannot be empty")
    if len(query) > 500:
        raise ValueError("query is too long; maximum is 500 characters")

    work = query.strip()
    filters: dict[str, Any] = {"limit": max(1, min(int(default_limit), 50))}

    limit_match = re.search(r"(?:最多|前|返回|给我)\s*(\d{1,2})\s*门?", work)
    if limit_match:
        filters["limit"] = max(1, min(int(limit_match.group(1)), 50))
        work = _strip_span(work, limit_match)

    for alias, canonical in CAMPUS_ALIASES.items():
        match = re.search(re.escape(alias) + r"(?:校区)?", work)
        if match:
            filters["campus"] = canonical
            work = _strip_span(work, match)
            break

    for pattern, value in BIZ_PATTERNS:
        match = pattern.search(work)
        if match:
            filters["biz_type"] = value
            work = _strip_span(work, match)
            break

    day_match = re.search(r"(?:周|星期|礼拜)\s*([一二三四五六日天1-7])", work)
    if day_match:
        filters["day"] = DAY_ALIASES[day_match.group(1)]
        work = _strip_span(work, day_match)

    period_match = re.search(
        r"第?\s*(\d{1,2})\s*(?:[-~—–至到]\s*(\d{1,2})\s*)?节",
        work,
    )
    if period_match:
        start = int(period_match.group(1))
        end = int(period_match.group(2) or start)
        filters["period_start"] = min(start, end)
        filters["period_end"] = max(start, end)
        work = _strip_span(work, period_match)
    else:
        dayparts = (
            (re.compile(r"早上|上午"), (1, 5)),
            (re.compile(r"中午"), (5, 6)),
            (re.compile(r"下午"), (6, 10)),
            (re.compile(r"晚上|晚间|夜间"), (11, 14)),
        )
        for pattern, periods in dayparts:
            match = pattern.search(work)
            if match:
                filters["period_start"], filters["period_end"] = periods
                work = _strip_span(work, match)
                break

    week_match = re.search(r"第?\s*(\d{1,2})\s*(?:教学)?周", work)
    if week_match:
        filters["week"] = int(week_match.group(1))
        work = _strip_span(work, week_match)

    credit_patterns = (
        (re.compile(r"(?:至少|不低于|不少于|>=|≥)\s*(\d+(?:\.\d+)?)\s*学分"), "min_credits"),
        (re.compile(r"(\d+(?:\.\d+)?)\s*学分\s*(?:以上|起)"), "min_credits"),
        (re.compile(r"(?:至多|最多|不高于|不超过|<=|≤)\s*(\d+(?:\.\d+)?)\s*学分"), "max_credits"),
        (re.compile(r"(\d+(?:\.\d+)?)\s*学分\s*(?:以下|以内)"), "max_credits"),
    )
    credit_matched = False
    for pattern, key in credit_patterns:
        match = pattern.search(work)
        if match:
            filters[key] = float(match.group(1))
            work = _strip_span(work, match)
            credit_matched = True
            break
    if not credit_matched:
        exact_credit = re.search(r"(\d+(?:\.\d+)?)\s*学分", work)
        if exact_credit:
            value = float(exact_credit.group(1))
            filters["min_credits"] = value
            filters["max_credits"] = value
            work = _strip_span(work, exact_credit)

    teacher_match = re.search(r"([\u4e00-\u9fff·]{1,12})\s*老师", work)
    if teacher_match:
        teacher = _teacher_name(teacher_match.group(1))
        if teacher:
            filters["teacher"] = teacher
            work = _strip_span(work, teacher_match)

    syllabus_match = re.search(r"(?:有|带|包含)(?:教学)?大纲|有syllabus", work, re.IGNORECASE)
    if syllabus_match:
        filters["has_syllabus"] = True
        work = _strip_span(work, syllabus_match)

    available_match = re.search(r"有余量|有名额|还有名额|未满|没满|可选", work)
    if available_match:
        filters["available_only"] = True
        work = _strip_span(work, available_match)

    keyword = _clean_keyword(work)
    if keyword:
        filters["keyword"] = keyword

    if "week" in filters and not 1 <= filters["week"] <= 30:
        raise ValueError("week must be between 1 and 30")
    if "period_start" in filters and not 1 <= filters["period_start"] <= 14:
        raise ValueError("period_start must be between 1 and 14")
    if "period_end" in filters and not 1 <= filters["period_end"] <= 14:
        raise ValueError("period_end must be between 1 and 14")

    return filters
