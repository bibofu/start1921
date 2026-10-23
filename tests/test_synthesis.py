from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from time import monotonic
from typing import Any

import httpx
import pytest
from history_agent.answering import synthesis
from history_agent.answering.models import Citation, QuestionRequest
from history_agent.answering.runtime import RequestBudget
from history_agent.answering.synthesis import HistoryResponseSynthesizer, LLMResult
from history_agent.config import Settings
from llama_index.core.schema import NodeWithScore, TextNode


class Body(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False
        self.visited = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.visited += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def _chunk(content: str, *, finish: str | None = None, tokens: int = 0) -> bytes:
    payload = {
        "choices": [{"delta": {"content": content}, "finish_reason": finish}],
        "usage": {"total_tokens": tokens} if tokens else None,
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _body(answer: str, tokens: int = 7) -> Body:
    return Body([_chunk(answer, finish="stop", tokens=tokens), b"data: [DONE]\n\n"])


def _provider(monkeypatch: pytest.MonkeyPatch, bodies: list[Body]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, stream=bodies[len(calls) - 1])

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    return calls


def _citation(index: int = 1) -> Citation:
    return Citation(
        evidence_id=f"E{index}",
        document_id=f"doc-{index}",
        document="年谱",
        pdf_page=index,
        pdf_page_end=index,
        section=["1935年"],
        quote="1935年1月15日，参加会议并讨论有关工作。",
        source_type="chronology",
        verification_status="verified",
        extraction_methods=["text"],
        year_mentions=[1935],
    )


def _nodes(citations: list[Citation]) -> list[NodeWithScore]:
    return [
        NodeWithScore(node=TextNode(id_=item.evidence_id, text=item.quote)) for item in citations
    ]


def _settings() -> Settings:
    return Settings(_env_file=None, llm_api_key="test-only-key", llm_query_planning=False)


def test_framework_synthesis_returns_sources_and_raw_authoritative_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _provider(monkeypatch, [_body("1935年1月15日，参加会议。[E1]\n\n随后主持其他工作。")])
    citations = [_citation()]
    events: list[synthesis.AnswerStreamEvent] = []
    synthesizer = HistoryResponseSynthesizer(_settings())
    response = asyncio.run(
        synthesizer.asynthesize(
            "何时参加会议？",
            _nodes(citations),
            request=QuestionRequest(question="何时参加会议？"),
            citations=citations,
            event_sink=events.append,
        )
    )
    assert str(response) == "1935年1月15日，参加会议。[E1]\n\n随后主持其他工作。"
    assert response.source_nodes[0].node.node_id == "E1"
    assert synthesizer.last_result.error_code is None
    assert len(calls) == 1
    assert any(item.event == "delta" for item in events)


def test_research_findings_keep_original_sources_and_only_selected_evidence_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _provider(monkeypatch, [_body("1935年1月15日，参加会议。[E1]")])
    citations = [_citation()]
    synthesizer = HistoryResponseSynthesizer(_settings())
    asyncio.run(
        synthesizer.asynthesize(
            "梳理会议情况",
            _nodes(citations),
            citations=citations,
            findings=[
                "研究线索，参加会议。[E1]",
                "另一条未选入证据的结论。[E99]",
                "混入未选入证据的结论。[E1][E99]",
                "混入无效证据编号的结论。[E1][E0]",
                "混入非标准编号的结论。[E1][E01]",
                "没有来源的结论",
            ],
        )
    )
    messages = calls[0]["messages"]
    outline = next(item["content"] for item in messages if "<research_findings>" in item["content"])
    assert "研究线索，参加会议。[E1]" in outline
    assert "[E99]" not in outline
    assert "混入" not in outline
    assert "没有来源的结论" not in outline
    assert citations[0].quote in messages[-1]["content"]
    assert "不是独立史实证据" in outline


def test_synthesis_cancellation_closes_provider_without_reading_remaining_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = Body([_chunk("1935年"), _chunk("1月15日，参加会议。[E1]", finish="stop")])
    calls = _provider(monkeypatch, [body])
    citations = [_citation()]
    synthesizer = HistoryResponseSynthesizer(_settings())

    def cancel_on_delta(event: synthesis.AnswerStreamEvent) -> None:
        if event.event == "delta":
            raise asyncio.CancelledError

    async def run() -> None:
        with pytest.raises(asyncio.CancelledError):
            await synthesizer.asynthesize(
                "何时参加会议？",
                _nodes(citations),
                citations=citations,
                event_sink=cancel_on_delta,
            )

    asyncio.run(run())
    assert body.closed
    assert body.visited == 1
    assert len(calls) == 1


def test_map_failure_preserves_original_quotes_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[str] = []

    async def complete(
        settings: Settings,
        payload: dict[str, object],
        runtime: object = None,
        budget: RequestBudget | None = None,
    ) -> AsyncIterator[str | LLMResult]:
        del settings, runtime, budget
        text = json.dumps(payload, ensure_ascii=False)
        payloads.append(text)
        if "第 1/2 组证据" in text:
            yield LLMResult(answer=None, error_code="read_timeout", usage={"total_tokens": 2})
        elif "第 2/2 组证据" in text:
            yield LLMResult(answer="1935年1月15日，参加会议。[E13]", usage={"total_tokens": 3})
        else:
            assert "第 1 组原文摘录" in text
            assert "[E1] 1935年1月15日" in text
            assert "第 2 组分组归纳摘要" in text
            yield LLMResult(answer="1935年1月15日，参加会议。[E1][E13]", usage={"total_tokens": 5})

    monkeypatch.setattr(synthesis, "_stream_completion", complete)
    citations = [_citation(index) for index in range(1, 14)]
    synthesizer = HistoryResponseSynthesizer(_settings())
    asyncio.run(synthesizer.asynthesize("梳理会议情况", _nodes(citations), citations=citations))
    assert len(payloads) == 3
    assert synthesizer.last_result.error_code == "hierarchical_partial_map_fallback"
    assert synthesizer.last_result.usage == {"total_tokens": 10}
    assert synthesizer.last_result.answer is not None


def test_disabled_generation_and_exhausted_deadline_do_not_start_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(**kwargs: Any) -> None:
        raise AssertionError("network must not start")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    citations = [_citation()]
    disabled = HistoryResponseSynthesizer(Settings(_env_file=None, llm_api_key=None))
    response = asyncio.run(
        disabled.asynthesize("梳理会议情况", _nodes(citations), citations=citations)
    )
    assert "[E1]" in str(response)
    assert disabled.last_result.error_code == "not_configured"
    expired = HistoryResponseSynthesizer(_settings(), budget=RequestBudget(monotonic() - 1))
    asyncio.run(expired.asynthesize("梳理会议情况", _nodes(citations), citations=citations))
    assert expired.last_result.answer is None
    assert expired.last_result.error_code is not None
