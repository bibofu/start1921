"""Storage-independent keyword tokenization and query-filter helpers."""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import jieba

from history_agent.errors import IndexBuildError, RetrievalError
from history_agent.processing.models import ChunkRecord

CJK_RUN = re.compile(r"[㐀-䶿一-鿿]+")
LATIN_OR_NUMBER = re.compile(r"[A-Za-z]+(?:[-_][A-Za-z0-9]+)*|\d+(?:\.\d+)?")
TOKEN_PIECE = re.compile(
    r"[A-Za-z]+(?:[-_][A-Za-z0-9]+)*|\d+(?:\.\d+)?|[㐀-䶿一-鿿]+"
)
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

# Keep jieba's prefix-dict cache out of the working tree and out of the
# read-only package directory. The environment may point data elsewhere.
_DATA_DIR = Path(os.environ.get("HISTORY_AGENT_DATA_DIR", "data"))
_JIEBA_CACHE_DIR = (_DATA_DIR / "models" / "jieba").resolve()
try:
    _JIEBA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    jieba.dt.tmp_dir = str(_JIEBA_CACHE_DIR)
    jieba.dt.cache_file = str(_JIEBA_CACHE_DIR / "jieba.cache")
except OSError:
    pass
jieba.setLogLevel(logging.WARNING)

_USER_DICT = Path(
    os.environ.get("HISTORY_AGENT_JIEBA_DICT", "config/jieba_userdict.txt")
)
if _USER_DICT.is_file():
    jieba.load_userdict(str(_USER_DICT))
    USER_DICTIONARY_TERMS: frozenset[str] = frozenset(
        line.split()[0]
        for line in _USER_DICT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
else:
    USER_DICTIONARY_TERMS = frozenset()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _segment(text: str, *, search: bool) -> list[str]:
    tokens: list[str] = []
    segmenter = jieba.lcut_for_search if search else jieba.lcut
    for raw in segmenter(text):
        if not raw.strip():
            continue
        for match in TOKEN_PIECE.finditer(raw):
            piece = match.group()
            tokens.append(piece if CJK_RUN.fullmatch(piece) else piece.casefold())
    for match in YEAR.finditer(text):
        tokens.extend([match.group(1), f"{match.group(1)}年"])
    return tokens


def tokenize_for_index(text: str) -> list[str]:
    """Segment with jieba and normalize Latin/numeric tokens for storage."""

    return _segment(text, search=True)


def _filter_query_tokens(tokens: list[str]) -> list[str]:
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
    return filtered


def tokenize_query(query: str) -> list[str]:
    filtered = _filter_query_tokens(tokenize_for_index(query))
    if not filtered:
        raise RetrievalError(
            "The query does not contain searchable Chinese, Latin, or numeric terms."
        )
    return filtered


def query_word_tokens(query: str) -> list[str]:
    """Precise (non-search-mode) query words, used for term weighting."""

    return _filter_query_tokens(_segment(query, search=False))


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
    # A generic query that names several people is a multi-constraint search,
    # not a claim that every chunk must mention all of them; requiring that
    # would exclude pages about one of the people. Only explicit intersection
    # queries keep the co-occurrence filter.
    if query_intent == "general" and len(query_people) > 1:
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
