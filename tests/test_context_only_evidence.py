from __future__ import annotations

import asyncio
from typing import Any

import pytest
from history_agent.answering import synthesis as synthesis_module
from history_agent.answering.models import Citation, QuestionRequest
from history_agent.answering.synthesis import (
    HierarchicalPreparation,
    HistoryResponseSynthesizer,
    LLMResult,
    _primary_evidence_count,
)
from history_agent.config import Settings


def _citation(index: int) -> Citation:
    return Citation(
        evidence_id=f"E{index}",
        document_id="zhou",
        document="周恩来年谱（1949—1976）",
        pdf_page=600 + index,
        section=["1956年"],
        quote="1956年1月2日，出席中央政治局会议。",
        source_type="chronology",
        verification_status="verified",
        extraction_methods=["pymupdf"],
    )


def test_context_only_evidence_is_not_counted_for_grouping() -> None:
    citations = [_citation(index) for index in range(1, 17)]
    context_only = {f"E{index}" for index in range(13, 17)}

    assert _primary_evidence_count(citations, context_only) == 12
    assert _primary_evidence_count(citations, set()) == 16


@pytest.mark.parametrize(
    ("count", "context", "expect_grouping"),
    [(13, 0, True), (12, 4, False), (8, 4, False), (17, 4, True)],
)
def test_grouping_decision_uses_primary_evidence_only(
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    context: int,
    expect_grouping: bool,
) -> None:
    calls = {"map": 0}

    async def fake_map(**kwargs: Any) -> HierarchicalPreparation:
        calls["map"] += 1
        return HierarchicalPreparation(
            request_payload={"messages": [{"role": "user", "content": "x"}]},
            usage={"total_tokens": 1},
            map_failed=False,
        )

    async def fake_generation(*args: Any, **kwargs: Any) -> Any:
        yield LLMResult(answer="ok")

    monkeypatch.setattr(synthesis_module, "_prepare_hierarchical_answer", fake_map)
    monkeypatch.setattr(synthesis_module, "_generation_events", fake_generation)
    settings = Settings(_env_file=None, llm_api_key="sk-test")
    synthesizer = HistoryResponseSynthesizer(settings)
    citations = [_citation(index) for index in range(1, count + 1)]
    context_only = {f"E{index}" for index in range(count - context + 1, count + 1)}

    async def collect() -> list[Any]:
        return [
            item
            async for item in synthesizer.synthesize_events(
                QuestionRequest(question="周恩来1956年有哪些经历"),
                citations,
                context_only=context_only,
            )
        ]

    asyncio.run(collect())

    assert calls["map"] == (1 if expect_grouping else 0)
