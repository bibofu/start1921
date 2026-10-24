"""Delivery-time citation checks.

The offline validator in :mod:`history_agent.answering.validation` keeps its frozen
evaluation semantics. Production only enforces facts about citation existence:

* a marker naming evidence that is not in this request's evidence bundle;
* a citation whose quoted passage does not occur in the cited chunk's full text;
* a prose page reference (``《文献》PDF 第 N 页``) that contradicts the evidence
  cited in the same line.

Dates, entailment and uncited claims stay in the offline validator. Nothing here
calls a model: the whole check is string matching over a bounded answer, so the
cost is milliseconds and a failure can never take a request down (fail open).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from history_agent.answering.models import Citation
from history_agent.log import log_event

if TYPE_CHECKING:
    from history_agent.answering.evidence import EvidenceRegistry

LOGGER = logging.getLogger(__name__)

CitationCheckMode = Literal["off", "s1"]

EVIDENCE_MARKER = re.compile(r"\[(E\d+)\]")
# Kept separate from validation.SOURCE_PAGE_REFERENCE on purpose: the offline
# validator's behaviour must not change when this module is tuned.
PAGE_REFERENCE = re.compile(
    r"(?:(?:《(?P<document>[^》\n]{1,80})》)[^\n。！？；]{0,24})?"
    r"PDF\s*第\s*(?P<page>\d+)\s*页",
    re.IGNORECASE,
)
DOCUMENT_NOISE = re.compile(r"[^\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9]")
EMPTY_BRACKETS = re.compile(r"[（(【]\s*[)）】]")
DUPLICATE_PUNCTUATION = re.compile(r"([，、；。])\1+")
SPACE_BEFORE_PUNCTUATION = re.compile(r"[ \t]+(?=[，。！？；：、）】」』\[])")
MULTIPLE_SPACES = re.compile(r"[ \t]{2,}")
WHITESPACE = re.compile(r"\s+")
ELLIPSIS = re.compile(r"[…]+")
MERGED_QUOTE = re.compile(r"\n[ \t]*…+[ \t]*\n")
MAX_ANSWER_CHARS = 50_000
MIN_VERIFIABLE_QUOTE = 8


@dataclass(frozen=True)
class CitationCheckResult:
    """The answer after removals plus what was removed, for logging and notes."""

    answer: str
    enabled: bool = True
    skipped_reason: str | None = None
    error_code: str | None = None
    removed_markers: tuple[str, ...] = ()
    dropped_citations: tuple[str, ...] = ()
    removed_page_references: tuple[str, ...] = ()
    rewritten_page_references: tuple[str, ...] = ()

    def limitations(self) -> list[str]:
        messages: list[str] = []
        if self.removed_markers:
            messages.append(
                f"已移除 {len(self.removed_markers)} 处无法核实的引用标记"
                "（编号不在本轮证据包内）。"
            )
        if self.dropped_citations:
            messages.append(
                f"已移除 {len(self.dropped_citations)} 条引用："
                "其引文片段在对应文献原文中未找到。"
            )
        if self.removed_page_references:
            messages.append(
                f"已移除 {len(self.removed_page_references)} 处与所引证据不一致的页码表述。"
            )
        if self.rewritten_page_references:
            messages.append(
                f"已修正 {len(self.rewritten_page_references)} 处页码表述，仅保留文献名。"
            )
        return messages


def _normalize_document(value: str) -> str:
    return DOCUMENT_NOISE.sub("", value).casefold()


def document_matches(claimed: str | None, actual: str) -> bool:
    """Compare a claimed document name without guessing on very short names."""

    if not claimed:
        return True
    claimed_normalized = _normalize_document(claimed)
    actual_normalized = _normalize_document(actual)
    if len(claimed_normalized) < 2 or not actual_normalized:
        # Too ambiguous to enforce; failing open beats flagging a correct citation.
        return True
    return claimed_normalized in actual_normalized or actual_normalized in claimed_normalized


def _covers_page(citation: Citation, page: int) -> bool:
    end = citation.pdf_page_end or citation.pdf_page
    return citation.pdf_page <= page <= end


def _containing_line(text: str, position: int) -> str:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return text[start:] if end < 0 else text[start:end]


def _tidy(answer: str) -> str:
    """Remove punctuation and spacing left behind by a deleted fragment."""

    answer = EMPTY_BRACKETS.sub("", answer)
    answer = SPACE_BEFORE_PUNCTUATION.sub("", answer)
    answer = DUPLICATE_PUNCTUATION.sub(r"\1", answer)
    answer = MULTIPLE_SPACES.sub(" ", answer)
    lines = [line.rstrip() for line in answer.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _compact(text: str) -> str:
    return WHITESPACE.sub("", ELLIPSIS.sub("", text))


def quote_exists(quote: str, source_text: str) -> bool:
    """Whether every verifiable segment of ``quote`` occurs in the source text.

    A quote may be truncated (leading/trailing ``……``) or merged from several
    excerpts of the same source (``\\n……\\n``). Segments shorter than eight
    characters cannot be checked meaningfully, so they fail open.
    """

    haystack = _compact(source_text)
    if not haystack:
        return True
    segments = [segment for segment in MERGED_QUOTE.split(quote) if segment.strip()]
    verifiable = [
        needle
        for needle in (_compact(segment) for segment in segments)
        if len(needle) >= MIN_VERIFIABLE_QUOTE
    ]
    if not verifiable:
        return True
    return all(needle in haystack for needle in verifiable)


def check_citations(
    answer: str,
    citations: list[Citation],
    *,
    registry: EvidenceRegistry | None = None,
    mode: CitationCheckMode = "s1",
    run_id: str | None = None,
) -> CitationCheckResult:
    """Remove citation artifacts that cannot be true, and report what changed.

    Everything unexpected returns the original answer unchanged.
    """

    if mode == "off":
        return CitationCheckResult(answer=answer, enabled=False, skipped_reason="disabled")
    if not answer.strip():
        return CitationCheckResult(answer=answer, skipped_reason="empty_answer")
    if len(answer) > MAX_ANSWER_CHARS:
        return CitationCheckResult(answer=answer, skipped_reason="answer_too_long")

    try:
        return _check(answer, citations, registry=registry, run_id=run_id)
    except Exception as exc:  # pragma: no cover - defensive, must never break delivery
        log_event(
            LOGGER,
            logging.WARNING,
            "citation check failed open",
            run_id=run_id,
            error=type(exc).__name__,
        )
        return CitationCheckResult(
            answer=answer,
            error_code="citation_check_failed",
            skipped_reason="error",
        )


def _verifiable_citations(
    citations: list[Citation], registry: EvidenceRegistry | None
) -> tuple[dict[str, Citation], list[str]]:
    """Drop citations whose quoted passage is absent from the source chunk."""

    if registry is None:
        return {citation.evidence_id: citation for citation in citations}, []
    available: dict[str, Citation] = {}
    dropped: list[str] = []
    for citation in citations:
        try:
            source = registry.raw_text(citation.evidence_id)
        except Exception:
            source = ""
        if source and not quote_exists(citation.quote, source):
            dropped.append(citation.evidence_id)
            continue
        available[citation.evidence_id] = citation
    return available, dropped


def _check(
    answer: str,
    citations: list[Citation],
    *,
    registry: EvidenceRegistry | None,
    run_id: str | None,
) -> CitationCheckResult:
    available, dropped = _verifiable_citations(citations, registry)
    dropped_ids = set(dropped)
    if dropped_ids:
        for evidence_id in dropped_ids:
            answer = answer.replace(f"[{evidence_id}]", "")

    removed_markers: list[str] = []
    for marker in dict.fromkeys(EVIDENCE_MARKER.findall(answer)):
        if marker not in available:
            removed_markers.append(marker)
            answer = answer.replace(f"[{marker}]", "")

    removed_pages: list[str] = []
    rewritten_pages: list[str] = []

    def replace_page(match: re.Match[str]) -> str:
        document = match.group("document")
        page = int(match.group("page"))
        line = _containing_line(answer, match.start())
        markers = EVIDENCE_MARKER.findall(line)
        cited = [available[item] for item in dict.fromkeys(markers) if item in available]
        if not cited:
            removed_pages.append(match.group(0))
            return ""
        if document is None:
            if any(_covers_page(citation, page) for citation in cited):
                return match.group(0)
            removed_pages.append(match.group(0))
            return ""
        matched = [
            citation for citation in cited if document_matches(document, citation.document)
        ]
        if not matched:
            removed_pages.append(match.group(0))
            return ""
        if any(_covers_page(citation, page) for citation in matched):
            return match.group(0)
        rewritten_pages.append(match.group(0))
        return f"《{document}》"

    checked = PAGE_REFERENCE.sub(replace_page, answer)
    changed = bool(dropped or removed_markers or removed_pages or rewritten_pages)
    answer = _tidy(checked) if changed else checked

    result = CitationCheckResult(
        answer=answer,
        removed_markers=tuple(removed_markers),
        dropped_citations=tuple(dropped),
        removed_page_references=tuple(removed_pages),
        rewritten_page_references=tuple(rewritten_pages),
    )
    log_event(
        LOGGER,
        logging.INFO,
        "citation_check",
        run_id=run_id,
        dropped_citations=list(result.dropped_citations),
        removed_markers=list(result.removed_markers),
        removed_page_references=list(result.removed_page_references),
        rewritten_page_references=list(result.rewritten_page_references),
        changed=changed,
    )
    return result
