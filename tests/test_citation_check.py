from __future__ import annotations

from typing import Any

import pytest
from history_agent.answering import citation_check as citation_check_module
from history_agent.answering.citation_check import check_citations
from history_agent.answering.delivery import deliver_answer
from history_agent.answering.models import (
    AnswerResponse,
    Citation,
    ExecutionSummary,
    QueryPlan,
    QuestionRequest,
    ResearchPlan,
    ResearchTask,
    TaskResult,
)
from history_agent.answering.query_understanding import QueryPlanningResult
from history_agent.answering.synthesis import LLMResult
from history_agent.config import Settings


class _FakeRegistry:
    def __init__(self, texts: dict[str, str]) -> None:
        self._texts = texts

    def raw_text(self, evidence_id: str) -> str:
        return self._texts[evidence_id]


def _citation(
    evidence_id: str = "E1",
    *,
    document: str = "周恩来年谱（1949—1976）",
    page: int = 688,
    page_end: int | None = None,
    quote: str = "1956年1月2日，出席中央政治局会议。",
) -> Citation:
    return Citation(
        evidence_id=evidence_id,
        document_id="zhou",
        document=document,
        pdf_page=page,
        pdf_page_end=page_end,
        section=["1956年"],
        quote=quote,
        source_type="chronology",
        verification_status="verified",
        extraction_methods=["pymupdf"],
    )


def test_unknown_marker_is_removed_and_reported() -> None:
    result = check_citations("他出席会议。[E1][E9]", [_citation()])

    assert "[E9]" not in result.answer
    assert "[E1]" in result.answer
    assert result.removed_markers == ("E9",)
    assert result.limitations()


def test_known_marker_is_untouched() -> None:
    result = check_citations("他出席会议。[E1]", [_citation()])

    assert result.answer == "他出席会议。[E1]"
    assert result.removed_markers == ()
    assert result.limitations() == []


def test_correct_page_reference_is_kept() -> None:
    answer = "他出席会议（《周恩来年谱》PDF 第 688 页）。[E1]"

    result = check_citations(answer, [_citation()])

    assert result.answer == answer
    assert result.removed_page_references == ()
    assert result.rewritten_page_references == ()


def test_wrong_page_keeps_document_name() -> None:
    answer = "《周恩来年谱》PDF 第 812 页记载他出席会议。[E1]"

    result = check_citations(answer, [_citation()])

    assert "812" not in result.answer
    assert "《周恩来年谱》" in result.answer
    assert result.rewritten_page_references == ("《周恩来年谱》PDF 第 812 页",)


def test_wrong_document_removes_the_whole_reference() -> None:
    answer = "《毛泽东年谱》PDF 第 688 页这样记载。[E1]"

    result = check_citations(answer, [_citation()])

    assert "PDF" not in result.answer
    assert result.removed_page_references


def test_cross_page_range_is_accepted() -> None:
    answer = "见《周恩来年谱》PDF 第 690 页。[E1]"

    result = check_citations(answer, [_citation(page=688, page_end=691)])

    assert result.answer == answer
    assert result.rewritten_page_references == ()


def test_orphan_page_reference_is_removed() -> None:
    answer = "另据 PDF 第 812 页，会议通过了决议。"

    result = check_citations(answer, [_citation()])

    assert "812" not in result.answer
    assert "会议通过了决议" in result.answer


def test_page_reference_is_scoped_to_its_own_line() -> None:
    answer = "第一段无引用。\n\n第二段见 PDF 第 688 页。[E1]"

    result = check_citations(answer, [_citation()])

    assert "688" in result.answer
    assert result.removed_page_references == ()


def test_disabled_mode_returns_the_original_answer() -> None:
    answer = "他出席会议。[E9]"

    result = check_citations(answer, [_citation()], mode="off")

    assert result.answer == answer
    assert result.enabled is False
    assert result.removed_markers == ()


def test_overlong_answer_is_skipped() -> None:
    answer = "长" * (citation_check_module.MAX_ANSWER_CHARS + 1)

    result = check_citations(answer, [_citation()])

    assert result.skipped_reason == "answer_too_long"
    assert result.answer == answer


def test_check_failure_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(citation_check_module, "_check", explode)
    answer = "他出席会议。[E9]"

    result = check_citations(answer, [_citation()])

    assert result.answer == answer
    assert result.error_code == "citation_check_failed"


def test_unverified_quote_is_reported_but_not_removed() -> None:
    answer = "他提出「调查研究是十月怀胎」。[E1]"
    registry = _FakeRegistry({"E1": "1956年1月2日，出席中央政治局会议。"})

    result = check_citations(answer, [_citation()], registry=registry)

    assert "调查研究是十月怀胎" in result.answer
    assert result.unverified_quotes == ("调查研究是十月怀胎",)


def test_verified_quote_is_not_reported() -> None:
    answer = "他提出「出席中央政治局会议」。[E1]"
    registry = _FakeRegistry({"E1": "1956年1月2日，出席中央政治局会议并发言。"})

    result = check_citations(answer, [_citation()], registry=registry)

    assert result.unverified_quotes == ()
    assert result.full_text_evidence == 1


def _summary(citations: list[Citation]) -> ExecutionSummary:
    question = "周恩来在1956年有哪些经历"
    plan = ResearchPlan(
        question=question,
        interpretation=QueryPlan(normalized_question=question),
        tasks=[ResearchTask(task_id="search", tool="search", objective=question, query=question)],
    )
    return ExecutionSummary(
        run_id="run-test",
        plan=plan,
        task_results=[
            TaskResult(
                task_id="search",
                tool="search",
                status="completed",
                evidence_ids=[citation.evidence_id for citation in citations],
            )
        ],
    )


def _deliver(answer: str, citations: list[Citation]) -> AnswerResponse:
    return deliver_answer(
        Settings(_env_file=None, llm_api_key="sk-test"),
        QuestionRequest(question="周恩来在1956年有哪些经历"),
        QueryPlanningResult(QueryPlan(normalized_question="周恩来在1956年有哪些经历"), "used"),
        _summary(citations),
        citations,
        LLMResult(answer),
        unresolved=[],
    )


def test_delivery_removes_unknown_marker_and_explains_why() -> None:
    citations = [_citation()]

    response = _deliver("1956年1月2日，他出席会议。[E1][E9]", citations)

    assert "[E9]" not in response.answer
    assert "[E1]" in response.answer
    assert any("无法核实的引用标记" in note for note in response.limitations)


def test_delivery_keeps_a_verified_answer_untouched() -> None:
    citations = [_citation()]
    answer = "1956年1月2日，他出席会议（《周恩来年谱》PDF 第 688 页）。[E1]"

    response = _deliver(answer, citations)

    assert response.answer == answer
    assert not any("无法核实" in note for note in response.limitations)


def test_delivery_does_not_touch_extractive_fallback() -> None:
    citations = [_citation()]
    response = _deliver("", citations)

    assert response.generator_mode == "extractive"
