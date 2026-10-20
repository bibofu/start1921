"""Storage-independent keyword tokenization and query-filter helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from history_agent.errors import IndexBuildError, RetrievalError
from history_agent.processing.models import ChunkRecord

CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
LATIN_OR_NUMBER = re.compile(r"[A-Za-z]+(?:[-_][A-Za-z0-9]+)*|\d+(?:\.\d+)?")
YEAR = re.compile(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)")
YEAR_RANGE = re.compile(
    r"(?<!\d)(?:18|19|20)\d{2}年?\s*(?:至|到|—|–|-|~|～)\s*"
    r"(?:18|19|20)\d{2}年?(?!\d)"
)
QUERY_STOP_TERMS = {
    "哪些",
    "什么",
    "怎么",
    "如何",
    "主要",
    "有哪",
    "都有",
    "请问",
    "一下",
    "这个",
    "那个",
    "是否",
    "可以",
    "人物",
    "经历",
    "观点",
    "情况",
    "交集",
    "期间",
}
QUERY_STOP_EDGE_CHARACTERS = set("的了在和与及是有为于把被从对")
PERIOD_RANGES = {
    "长征": (1934, 1936),
    "抗日战争": (1937, 1945),
    "全面抗战": (1937, 1945),
    "解放战争": (1945, 1949),
    "抗美援朝": (1950, 1953),
    "大跃进": (1958, 1960),
    "文化大革命": (1966, 1976),
    "文革": (1966, 1976),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def cjk_bigrams(value: str) -> list[str]:
    if len(value) <= 2:
        return [value]
    return [value[index : index + 2] for index in range(len(value) - 1)]


def tokenize_for_index(text: str) -> list[str]:
    tokens: list[str] = []
    for match in CJK_RUN.finditer(text):
        tokens.extend(cjk_bigrams(match.group()))
    tokens.extend(match.group().casefold() for match in LATIN_OR_NUMBER.finditer(text))
    for match in YEAR.finditer(text):
        tokens.extend([match.group(1), f"{match.group(1)}年"])
    return tokens


def tokenize_query(query: str) -> list[str]:
    tokens = tokenize_for_index(query)
    filtered: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if (
            token in QUERY_STOP_TERMS
            or token in seen
            or len(token.strip()) < 2
            or (
                CJK_RUN.fullmatch(token)
                and (
                    token[0] in QUERY_STOP_EDGE_CHARACTERS
                    or token[-1] in QUERY_STOP_EDGE_CHARACTERS
                )
            )
        ):
            continue
        seen.add(token)
        filtered.append(token)
    if not filtered:
        raise RetrievalError(
            "The query does not contain searchable Chinese, Latin, or numeric terms."
        )
    return filtered


def infer_query_intent(query: str) -> str:
    if any(term in query for term in ("交集", "共同", "一起", "关系")):
        return "intersection"
    if any(term in query for term in ("记述", "描述")):
        return "observation"
    if any(
        term in query
        for term in (
            "观点",
            "论述",
            "主张",
            "看法",
            "如何看",
            "怎样分析",
            "如何分析",
            "谋划",
            "战略",
            "方针",
            "策略",
        )
    ):
        return "viewpoint"
    if (YEAR.search(query) or any(period in query for period in PERIOD_RANGES)) and any(
        term in query for term in ("经历", "做了什么", "活动", "任职", "担任", "职务", "主要做")
    ):
        return "timeline"
    return "general"


def hard_filter_people(query_people: list[str], query_intent: str) -> list[str]:
    """Return people that must occur in a chunk for the current query intent."""

    # A person's own selected works often omit the author's name from the body.
    # Viewpoint queries therefore use creator/source ranking bonuses instead.
    if query_intent in {"viewpoint", "observation"}:
        return []
    return query_people


def infer_year_range(query: str, explicit_years: list[int]) -> list[int]:
    if explicit_years:
        return [min(explicit_years), max(explicit_years)]
    ranges = [year_range for name, year_range in PERIOD_RANGES.items() if name in query]
    if not ranges:
        return []
    return [min(item[0] for item in ranges), max(item[1] for item in ranges)]


def has_explicit_year_range(query: str) -> bool:
    return YEAR_RANGE.search(query) is not None


def load_chunks(chunks_dir: Path) -> list[ChunkRecord]:
    paths = sorted(chunks_dir.glob("*.jsonl"))
    if not paths:
        raise IndexBuildError(f"No chunk JSONL files found in {chunks_dir}")
    records: list[ChunkRecord] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ChunkRecord.model_validate_json(line))
                except Exception as exc:
                    raise IndexBuildError(
                        f"Invalid chunk record in {path} line {line_number}: {exc}"
                    ) from exc
    return records
