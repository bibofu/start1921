from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from history_agent.answering.models import (
    QueryEntity,
    QueryPlan,
    QuestionRequest,
    ResearchTask,
    TaskResult,
)
from history_agent.answering.query_understanding import QueryPlanningResult
from history_agent.answering.service import answer_question
from history_agent.answering.streaming import stream_answer_question
from history_agent.answering.synthesis import HierarchicalPreparation, LLMResult, _stream_completion
from history_agent.answering.task_executor import HistoryTaskExecutor
from history_agent.config import Settings
from history_agent.errors import RetrievalError
from history_agent.web.app import create_app
from test_answering import _citation
from test_retrieval import _hit, _response


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.visited = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.visited += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def _chunk(text: str | None = None, *, finish: str | None = None, usage: int = 0) -> bytes:
    payload = {
        "choices": [{"delta": {"content": text}, "finish_reason": finish}],
        "usage": {"total_tokens": usage} if usage else None,
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\r\n\r\n".encode()


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_api_key="test-only-key",
        llm_query_planning=False,
        llm_retrieval_reflection=False,
    )


def _provider(
    monkeypatch: pytest.MonkeyPatch, streams: list[ChunkStream], *, status: int = 200
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(status, stream=streams[len(requests) - 1])

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    return requests


def _context(
    monkeypatch: pytest.MonkeyPatch,
    *,
    citations: list[Any] | None = None,
    retrieval: Any = None,
    tool: str = "search",
    content: str | None = None,
) -> list[ResearchTask]:
    citations = citations if citations is not None else [_citation()]
    retrieval = retrieval if retrieval is not None else _response([_hit("one", 1, page=688)])
    received: list[ResearchTask] = []

    async def execute(
        self: HistoryTaskExecutor, task: ResearchTask, prior: list[TaskResult]
    ) -> TaskResult:
        received.append(task)
        ids = [
            self.registry.register_citation(citation, task.task_id, f"fixture:{index}").evidence_id
            for index, citation in enumerate(citations)
        ]
        return TaskResult(
            task_id=task.task_id,
            tool=task.tool,
            status="completed" if ids else "empty",
            evidence_ids=ids,
            retrieval=retrieval if tool == "search" else None,
            content=content,
        )

    monkeypatch.setattr(HistoryTaskExecutor, "execute", execute)
    if tool != "search":
        plan = QueryPlan(
            intent="timeline",
            retrieval_route="structured",
            normalized_question="整理结构化年谱",
            start_year=1956,
            end_year=1956,
            entities=[QueryEntity(type="person", text="周恩来", canonical="周恩来")],
            tasks=[
                ResearchTask(
                    task_id="timeline",
                    tool="timeline",
                    objective="整理年谱记录",
                    query="整理结构化年谱",
                    person_names=["周恩来"],
                    start_year=1956,
                    end_year=1956,
                )
            ],
        )
        monkeypatch.setattr(
            "history_agent.answering.llamaindex_workflow.should_plan_query",
            lambda *a: True,
        )
        monkeypatch.setattr(
            "history_agent.answering.llamaindex_workflow.plan_question",
            lambda *a: QueryPlanningResult(plan, "used"),
        )
    return received


def _events(settings: Settings | None = None) -> list[Any]:
    async def collect() -> list[Any]:
        return [
            event
            async for event in stream_answer_question(
                settings or _settings(), QuestionRequest(question="测试观点")
            )
        ]

    return asyncio.run(collect())


def test_provider_delivers_delta_before_reading_remainder_and_closes_on_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = ChunkStream([_chunk("第一段"), _chunk("第二段", finish="stop"), b"data: [DONE]\n\n"])
    requests = _provider(monkeypatch, [body])

    async def read_first() -> None:
        stream = _stream_completion(_settings(), {"messages": []})
        assert await anext(stream) == "第一段"
        assert body.visited == 1
        await stream.aclose()
        assert body.closed

    asyncio.run(read_first())
    assert requests[0]["stream"] is True
    assert requests[0]["stream_options"] == {"include_usage": True}


def test_stream_preserves_unicode_and_final_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    wire = _chunk("参加有关") + _chunk("会议。[E1]", finish="stop", usage=20) + b"data: [DONE]\n\n"
    body = ChunkStream([bytes([byte]) for byte in wire])
    _provider(monkeypatch, [body])
    _context(monkeypatch)
    events = _events()
    assert "".join(e.data["text"] for e in events if e.event == "delta") == "参加有关会议。[E1]"
    assert events[-1].event == "done"
    assert events[-1].data["llm_status"] == "used"
    assert events[-1].data["llm_usage"] == {"total_tokens": 20}
    assert events[-1].data["citations"][0]["pdf_page"] == 688
    assert body.closed


def test_stream_returns_raw_answer_without_background_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ChunkStream(
        [
            _chunk("参加有关会议。[E1]\n\n随后主持工作。", finish="stop", usage=20),
            b"data: [DONE]\n\n",
        ]
    )
    requests = _provider(monkeypatch, [first])
    _context(monkeypatch)
    events = _events()
    assert all(e.event != "reset" for e in events)
    assert "".join(e.data["text"] for e in events if e.event == "delta") == (
        "参加有关会议。[E1]\n\n随后主持工作。"
    )
    assert not any(e.event == "status" and e.data["message"] == "正在后台补全引用…" for e in events)
    assert events[-1].data["answer"] == "参加有关会议。[E1]\n\n随后主持工作。"
    assert events[-1].data["llm_error_code"] is None
    assert events[-1].data["llm_usage"] == {"total_tokens": 20}
    assert len(requests) == 1


@pytest.mark.parametrize(
    "chunks,reason",
    [
        ([_chunk("参加有关会议。[E1]", finish="stop")], "incomplete_stream"),
        (
            [_chunk("参加有关会议。[E1]", finish="length"), b"data: [DONE]\n\n"],
            "max_tokens_exhausted",
        ),
        ([b"data: invalid-json\n\n"], "invalid_response"),
    ],
)
def test_failed_stream_is_replaced_with_evidence_excerpt(
    monkeypatch: pytest.MonkeyPatch, chunks: list[bytes], reason: str
) -> None:
    _provider(monkeypatch, [ChunkStream(chunks)])
    _context(monkeypatch)
    data = _events()[-1].data
    assert data["llm_status"] == "fallback"
    assert data["generator_mode"] == "extractive"
    assert "E99" not in data["answer"]
    assert any(reason in item for item in data["limitations"])


def test_stream_removes_unknown_marker_at_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _provider(
        monkeypatch,
        [ChunkStream([_chunk("错误引用。[E99]", finish="stop"), b"data: [DONE]\n\n"])],
    )
    _context(monkeypatch)
    data = _events()[-1].data
    assert data["answer"] == "错误引用。"
    assert data["llm_status"] == "used"
    assert data["llm_error_code"] is None
    assert any("无法核实的引用标记" in item for item in data["limitations"])


def test_stream_does_not_send_reasoning_as_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    reasoning = b'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}\n\n'
    body = ChunkStream(
        [reasoning, _chunk("参加有关会议。[E1]", finish="stop"), b"data: [DONE]\n\n"]
    )
    _provider(monkeypatch, [body])
    _context(monkeypatch)
    events = _events()
    assert "private reasoning" not in "".join(e.encode() for e in events)


def test_no_model_configuration_finishes_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    _context(monkeypatch)
    data = _events(_settings().model_copy(update={"llm_api_key": None}))[-1].data
    assert data["llm_status"] == "disabled"


def test_stream_uses_semantic_plan_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = QueryPlan(
        intent="event_overview",
        normalized_question="介绍中国共产党第一次全国代表大会",
        search_queries=["中国共产党第一次全国代表大会 代表 决议"],
    )
    planning = QueryPlanningResult(
        plan, "used", model_name="deepseek-v4-flash", usage={"total_tokens": 50}
    )
    received = _context(monkeypatch, citations=[], retrieval=_response([]))
    monkeypatch.setattr(
        "history_agent.answering.llamaindex_workflow.should_plan_query", lambda *a: True
    )
    monkeypatch.setattr(
        "history_agent.answering.llamaindex_workflow.plan_question", lambda *a: planning
    )
    events = _events(_settings().model_copy(update={"llm_query_planning": True}))
    assert received and received[0].objective == plan.normalized_question
    assert any(event.event == "status" and "任务" in event.data["message"] for event in events)
    assert events[-1].data["query_planner_status"] == "used"
    assert events[-1].data["query_plan"]["normalized_question"] == plan.normalized_question
    assert events[-1].data["execution_summary"]["task_results"][0]["task_id"] == received[0].task_id


def test_stream_endpoint_sends_final_result_and_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _context(monkeypatch)
    settings = _settings().model_copy(update={"llm_api_key": None})
    client = TestClient(create_app(settings))
    response = client.post("/api/questions/stream", json={"question": "测试观点"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done\n" in response.text
    assert "event: status\n" in response.text
    assert client.post("/api/questions/stream", json={"question": ""}).status_code == 422

    async def failed(*args: object) -> LLMResult:
        raise RetrievalError("internal path and secret must not leak")

    monkeypatch.setattr(HistoryTaskExecutor, "execute", failed)
    response = client.post("/api/questions/stream", json={"question": "测试观点"})
    assert "event: error\n" in response.text
    assert "internal path" not in response.text


def test_disabled_planner_uses_rag_without_generic_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    def search(**kwargs: Any) -> Any:
        queries.append(kwargs["query"])
        return _response([], intent="timeline")

    monkeypatch.setattr("history_agent.answering.task_executor.search_hybrid_index", search)
    client = TestClient(create_app(_settings().model_copy(update={"llm_api_key": None})))
    response = client.post("/api/questions/stream", json={"question": "毛泽东有哪些经历"})
    assert queries == ["毛泽东有哪些经历"]
    assert response.status_code == 200
    assert "event: done\n" in response.text
    assert "event: error\n" not in response.text
    assert "请明确人物和年份" not in response.text


def test_stream_out_of_scope_stops_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = QueryPlan(intent="out_of_scope", normalized_question="介绍辛亥革命的情况")
    monkeypatch.setattr(
        "history_agent.answering.llamaindex_workflow.should_plan_query",
        lambda *a: True,
    )
    monkeypatch.setattr(
        "history_agent.answering.llamaindex_workflow.plan_question",
        lambda *a: QueryPlanningResult(plan, "used"),
    )

    async def unexpected(*args: object, **kwargs: object) -> TaskResult:
        raise AssertionError("out-of-scope question must not start retrieval")

    monkeypatch.setattr(HistoryTaskExecutor, "execute", unexpected)
    events = _events(_settings().model_copy(update={"llm_query_planning": True}))
    assert events[-1].event == "done"
    assert events[-1].data["retrieval_mode"] == "out_of_scope"
    assert events[-1].data["evidence_status"] == "no_evidence"
    assert events[-1].data["citations"] == []
    assert events[-1].data["query_plan"]["intent"] == "out_of_scope"
    assert events[-1].data["answer"].startswith("这个问题超出本地知识库的史料范围")
    assert all(event.event != "delta" for event in events)


def test_structured_summary_streams_through_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _context(monkeypatch, tool="timeline", content="结构化记录摘录。[E1]")
    _provider(
        monkeypatch,
        [ChunkStream([_chunk("可归纳为外事和会议工作。[E1]", finish="stop"), b"data: [DONE]\n\n"])],
    )
    events = _events()
    assert any(event.event == "status" and "综合" in event.data["message"] for event in events)
    assert events[-1].data["retrieval_mode"] == "structured_timeline"
    assert events[-1].data["llm_status"] == "used"
    assert events[-1].data["answer"] == "可归纳为外事和会议工作。[E1]"


def test_structured_record_list_also_streams_through_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _context(monkeypatch, tool="timeline", content="结构化记录摘录。[E1]")
    _provider(
        monkeypatch,
        [ChunkStream([_chunk("整理后的记录。[E1]", finish="stop"), b"data: [DONE]\n\n"])],
    )

    async def collect() -> list[Any]:
        return [
            event
            async for event in stream_answer_question(
                _settings(), QuestionRequest(question="请列出1956年周恩来的时间线")
            )
        ]

    events = asyncio.run(collect())
    assert events[-1].data["llm_status"] == "used"
    assert events[-1].data["answer"] == "整理后的记录。[E1]"


def test_stream_structured_timeline_miss_finishes_with_filtered_hybrid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question = "彭德怀在1930-1935年的主要经历"
    task = ResearchTask(
        task_id="timeline",
        tool="timeline",
        objective=question,
        query=question,
        start_year=1930,
        end_year=1935,
        person_names=["彭德怀"],
    )
    plan = QueryPlan(
        intent="timeline",
        retrieval_route="structured",
        normalized_question=question,
        start_year=1930,
        end_year=1935,
        tasks=[task],
        entities=[QueryEntity(type="person", text="彭德怀", canonical="彭德怀")],
    )
    monkeypatch.setattr(
        "history_agent.answering.llamaindex_workflow.plan_question",
        lambda *a: QueryPlanningResult(plan, "used", model_name="deepseek-v4-flash"),
    )
    citation = _citation("1935年11月3日，彭德怀被任命为红一方面军司令员。").model_copy(
        update={"year_mentions": [1935]}
    )
    calls = []

    async def execute(
        self: HistoryTaskExecutor, task: ResearchTask, prior: list[TaskResult]
    ) -> TaskResult:
        calls.append(task.tool)
        if task.tool == "timeline":
            return TaskResult(
                task_id=task.task_id,
                tool=task.tool,
                status="empty",
                limitations=["未找到年谱主体记录。"],
            )
        registered = self.registry.register_citation(citation, task.task_id, "fixture:timeline")
        retrieval = _response([_hit("one", 1, page=688)]).model_copy(
            update={
                "query": question,
                "query_intent": "timeline",
                "query_people": ["彭德怀"],
                "query_year_range": [1930, 1935],
                "retrieval_mode": "planned_hybrid_rrf_subject_filtered",
            }
        )
        return TaskResult(
            task_id=task.task_id,
            tool=task.tool,
            status="completed",
            evidence_ids=[registered.evidence_id],
            retrieval=retrieval,
            limitations=["核对主体后剔除 4 条候选。"],
        )

    monkeypatch.setattr(HistoryTaskExecutor, "execute", execute)
    _provider(
        monkeypatch,
        [
            ChunkStream(
                [
                    _chunk("1935年11月3日，彭德怀被任命为司令员。[E1]", finish="stop"),
                    b"data: [DONE]\n\n",
                ]
            )
        ],
    )

    async def collect() -> list[Any]:
        return [
            event
            async for event in stream_answer_question(
                _settings().model_copy(update={"llm_query_planning": True}),
                QuestionRequest(question=question),
            )
        ]

    done = asyncio.run(collect())[-1].data
    assert calls == ["timeline", "search"]
    assert done["retrieval_mode"] == "planned_hybrid_rrf_subject_filtered"
    assert any("年谱主体记录" in item for item in done["limitations"])
    assert any("剔除 4 条" in item for item in done["limitations"])
    assert done["execution_summary"]["replan_count"] == 1


def test_cancelling_answer_closes_nested_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class WaitingStream(ChunkStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            self.visited += 1
            yield _chunk("参加有关")
            # The workflow producer is independent of its SSE consumer. Keep a
            # real upstream read pending so cancellation must close it promptly.
            await asyncio.Event().wait()

    body = WaitingStream([])
    _provider(monkeypatch, [body])
    _context(monkeypatch)

    async def cancel() -> None:
        answers = stream_answer_question(_settings(), QuestionRequest(question="测试观点"))
        async for event in answers:
            if event.event == "delta":
                break
        await answers.aclose()
        assert body.closed
        assert body.visited == 1

    asyncio.run(cancel())


def test_stream_keeps_uncited_paragraph_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = [_chunk("参加有关会议。[E1]\n\n随后主持工作。", finish="stop"), b"data: [DONE]\n\n"]
    requests = _provider(monkeypatch, [ChunkStream(draft)])
    _context(monkeypatch)
    final = _events()[-1].data
    assert len(requests) == 1
    assert final["llm_status"] == "used"
    assert final["llm_error_code"] is None
    assert final["answer"] == "参加有关会议。[E1]\n\n随后主持工作。"
    assert final["uncited_claims"] == []


def test_large_evidence_set_uses_hierarchical_generation_in_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    citations = [
        _citation().model_copy(update={"evidence_id": f"E{index}"}) for index in range(1, 14)
    ]
    _context(monkeypatch, citations=citations)

    async def prepare(**kwargs: Any) -> HierarchicalPreparation:
        return HierarchicalPreparation(
            request_payload={"messages": []}, usage={"total_tokens": 5}, map_failed=False
        )

    monkeypatch.setattr("history_agent.answering.synthesis._prepare_hierarchical_answer", prepare)
    _provider(
        monkeypatch,
        [
            ChunkStream(
                [
                    _chunk("分层", usage=20),
                    _chunk("综合答案。[E1][E13]", finish="stop"),
                    b"data: [DONE]\n\n",
                ]
            )
        ],
    )
    events = _events()
    assert any(event.event == "status" and "分组归纳" in event.data["message"] for event in events)
    assert [event.data["text"] for event in events if event.event == "delta"] == [
        "分层",
        "综合答案。[E1][E13]",
    ]
    assert events[-1].data["answer"] == "分层综合答案。[E1][E13]"
    assert events[-1].data["llm_usage"] == {"total_tokens": 25}
    assert [item["evidence_id"] for item in events[-1].data["citations"]] == ["E1", "E13"]
    assert events[-1].data["retrieved_evidence_count"] == 13


@pytest.mark.parametrize("missing_fact", [False, True])
def test_ceremony_overview_has_same_validation_and_diagnostics_in_both_apis(
    monkeypatch: pytest.MonkeyPatch,
    missing_fact: bool,
) -> None:
    fact = "1949年10月1日，开国大典在北京天安门广场举行。"
    draft = f"## 开国大典\n\n> {fact}\n> [E1]\n\n现有资料不足以确认所有参与人员的具体分工。"
    if missing_fact:
        draft += "\n\n随后主持其他会议。"
    _context(monkeypatch, citations=[_citation(fact)])
    requests = _provider(
        monkeypatch,
        [
            ChunkStream([_chunk(draft, finish="stop", usage=20), b"data: [DONE]\n\n"])
            for _ in range(2)
        ],
    )
    question = QuestionRequest(question="介绍一下开国大典的情况")
    synchronous = answer_question(_settings(), question).model_dump()

    async def collect() -> list[Any]:
        return [event async for event in stream_answer_question(_settings(), question)]

    streamed = asyncio.run(collect())[-1].data
    # Different requests have distinct run IDs; all answer and execution semantics agree.
    assert synchronous["execution_summary"].pop("run_id") != streamed["execution_summary"].pop(
        "run_id"
    )
    assert synchronous == streamed
    assert len(requests) == 2
    assert streamed["llm_status"] == "used"
    assert streamed["answer"] == draft
    assert streamed["uncited_claims"] == []
    assert streamed["llm_error_code"] is None


def test_rate_limit_becomes_final_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _provider(monkeypatch, [ChunkStream([])], status=429)
    _context(monkeypatch)
    final = _events()[-1].data
    assert final["llm_status"] == "fallback"
    assert any("rate_limited" in item for item in final["limitations"])


def test_read_timeout_replaces_an_unfinished_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimedOutStream(ChunkStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield _chunk("尚未完成的文字")
            raise httpx.ReadTimeout("test timeout")

    body = TimedOutStream([])
    _provider(monkeypatch, [body])
    _context(monkeypatch)
    events = _events()
    assert any(e.event == "delta" for e in events)
    final = events[-1].data
    assert final["llm_status"] == "fallback"
    assert "尚未完成的文字" not in final["answer"]
    assert body.closed
