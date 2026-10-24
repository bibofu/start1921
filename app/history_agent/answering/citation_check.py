"""Delivery-time citation checks for the highest-confidence signals only.

The offline validator in :mod:`history_agent.answering.validation` keeps its frozen
evaluation semantics. This module enforces the subset of checks that are precise
enough to act on while an answer is being delivered:

* a marker naming evidence that is not in this request's evidence bundle;
* a prose page reference (``《文献》PDF 第 N 页``) that contradicts the evidence
  cited in the same line.

Dates and uncited claims stay in the offline validator. They are measured in a
later phase before any of them is allowed to change a delivered answer.

Nothing here calls a model. The whole check is regular expressions over a bounded
answer string, so the latency cost is milliseconds and a failure can never take a
request down (fail open).
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
QUOTED_PASSAGE = re.compile(r"[「“](?P<text>.{8,120}?)[」”]")
WHITESPACE = re.compile(r"\s+")
MAX_ANSWER_CHARS = 50_000
MAX_QUOTE_SAMPLES = 5


@dataclass(frozen=True)
class CitationCheckResult:
    """The answer after removals plus what was removed, for logging and notes."""

    answer: str
    enabled: bool = True
    skipped_reason: str | None = None
    error_code: str | None = None
    removed_markers: tuple[str, ...] = ()
    removed_page_references: tuple[str, ...] = ()
    rewritten_page_references: tuple[str, ...] = ()
    unverified_quotes: tuple[str, ...] = ()
    full_text_evidence: int = 0

    def limitations(self) -> list[str]:
        messages: list[str] = []
        if self.removed_markers:
            messages.append(
                f"已移除 {len(self.removed_markers)} 处无法核实的引用标记"
                "（编号不在本轮证据包内）。"
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
    return WHITESPACE.sub("", text)


def _unverified_quotes(
    answer: str,
    citations: list[Citation],
    registry: EvidenceRegistry | None,
) -> tuple[tuple[str, ...], int]:
    """Telemetry only: quoted passages that do not occur in any cited full text.

    This never rewrites the answer. It exists so the next phase can measure how
    often a model fabricates a verbatim quotation before that signal is enforced.
    """

    if registry is None:
        return (), 0
    passages = [match.group("text") for match in QUOTED_PASSAGE.finditer(answer)]
    if not passages:
        return (), 0
    haystacks: list[str] = []
    for citation in citations:
        try:
            raw = registry.raw_text(citation.evidence_id)
        except Exception:
            continue
        if raw:
            haystacks.append(_compact(raw))
    if not haystacks:
        return (), 0
    unverified = tuple(
        passage
        for passage in passages[:MAX_QUOTE_SAMPLES]
        if not any(_compact(passage) in haystack for haystack in haystacks)
    )
    return unverified, len(haystacks)


def check_citations(
    answer: str,
    citations: list[Citation],
    *,
    registry: EvidenceRegistry | None = None,
    mode: CitationCheckMode = "s1",
    run_id: str | None = None,
) -> CitationCheckResult:
    """Remove citation artifacts that cannot be true, and report what changed.

    Only two signals are enforced; both are cheap and high precision. Everything
    unexpected returns the original answer unchanged.
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


def _check(
    answer: str,
    citations: list[Citation],
    *,
    registry: EvidenceRegistry | None,
    run_id: str | None,
) -> CitationCheckResult:
    available = {citation.evidence_id: citation for citation in citations}
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
    changed = bool(removed_markers or removed_pages or rewritten_pages)
    answer = _tidy(checked) if changed else checked

    unverified_quotes, full_text_count = _unverified_quotes(answer, citations, registry)
    result = CitationCheckResult(
        answer=answer,
        removed_markers=tuple(removed_markers),
        removed_page_references=tuple(removed_pages),
        rewritten_page_references=tuple(rewritten_pages),
        unverified_quotes=unverified_quotes,
        full_text_evidence=full_text_count,
    )
    log_event(
        LOGGER,
        logging.INFO,
        "citation_check",
        run_id=run_id,
        removed_markers=list(result.removed_markers),
        removed_page_references=list(result.removed_page_references),
        rewritten_page_references=list(result.rewritten_page_references),
        unverified_quote_count=len(result.unverified_quotes),
        full_text_evidence=result.full_text_evidence,
        changed=changed,
    )
    return result
