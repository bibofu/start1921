"""Session-to-retrieval regressions with real PostgreSQL and scripted model I/O."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from history_agent.answering.llamaindex_llm import DeepSeekLlamaIndexLLM
from history_agent.answering.synthesis import LLMResult
from history_agent.config import Settings
from history_agent.retrieval.models import SearchHit, SearchResponse
from history_agent.web.app import create_app
from llama_index.core.llms import ChatMessage, ChatResponse


def _plan(question: str, subject: str, *, context: tuple[int, ...] = ()) -> dict[str, Any]:
    return {
        "intent": "event_overview",
        "normalized_question": question,
        "context_message_indices": list(context),
        "entities": [{"type": "event", "text": subject, "canonical": subject}],
    }


class ScriptedBoundary:
    """Keep storage, planner validation, tools and synthesis real; replace external I/O."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        plans: list[dict[str, Any]],
        answers: list[str],
    ) -> None:
        self.planner_payloads: list[dict[str, Any]] = []
        self.searches: list[dict[str, Any]] = []
        self.synthesis_payloads: list[dict[str, object]] = []

        def planning_reply(
            llm: DeepSeekLlamaIndexLLM,
            messages: Sequence[ChatMessage],
            kwargs: dict[str, Any],
        ) -> ChatResponse:
            del llm
            index = len(self.planner_payloads)
            self.planner_payloads.append({
                **kwargs["request_payload"],
                "messages": [
                    {"role": item.role.value, "content": item.content or ""}
                    for item in messages
                ],
            })
            return ChatResponse(
                message=ChatMessage(
                    role="assistant", content=json.dumps(plans[index], ensure_ascii=False),
                ),
            )

        def search(**kwargs: Any) -> SearchResponse:
            self.searches.append(kwargs)
            number = len(self.searches)
            text = answers[number - 1].replace("[E1]", "")
            hit = SearchHit(
                rank=1,
                chunk_id=f"current-chunk-{number}",
                document_id=f"current-source-{number}",
                title=f"本轮回归材料{number}",
                filename="fixture.pdf",
                source_type="history",
                verification_status="verified",
                pdf_page_start=number,
                pdf_page_end=number,
                section_path=[],
                text=text,
                year_mentions=[],
                people=[],
                extraction_methods=["text_layer"],
                score=1.0,
                matched_terms=[],
                keyword_rank=1,
            )
            return SearchResponse(
                query=kwargs["query"],
                query_intent="event_overview",
                query_terms=[],
                query_years=[],
                query_year_range=[],
                query_people=[],
                document_filters=[],
                include_out_of_scope=False,
                hits=[hit],
            )

        async def completion(
            settings: Settings,
            payload: dict[str, object],
            *args: Any,
            **kwargs: Any,
        ) -> AsyncGenerator[str | LLMResult, None]:
            del settings, args, kwargs
            index = len(self.synthesis_payloads)
            self.synthesis_payloads.append(payload)
            yield answers[index]
            yield LLMResult(answer=answers[index])

        monkeypatch.setattr(DeepSeekLlamaIndexLLM, "_sync_response", planning_reply)
        monkeypatch.setattr("history_agent.answering.task_executor.search_hybrid_index", search)
        monkeypatch.setattr("history_agent.answering.synthesis._stream_completion", completion)


def _client(work_path: Path) -> TestClient:
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        person_aliases_path=Path.cwd() / "config/person_aliases.json",
        quota_enabled=False,
        llm_api_key="test-only-key",
        # Scripted replies assume one planner call per turn; gate behavior has
        # separate workflow tests, while this fixture checks session context.
        llm_query_planning_gate=False,
        llm_retrieval_reflection=False,
    )
    return TestClient(create_app(settings))


def _session(client: TestClient) -> str:
    response = client.post("/api/sessions", json={})
    assert response.status_code == 200, response.text
    return str(response.json()["session"]["session_id"])


def _ask(
    client: TestClient,
    session_id: str,
    question: str,
    *,
    stream: bool = False,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/questions/stream" if stream else "/api/questions",
        json={"session_id": session_id, "question": question, "history": history or []},
    )
    assert response.status_code == 200, response.text
    if not stream:
        return dict(response.json())
    completed = []
    for frame in response.text.replace("\r\n", "\n").split("\n\n"):
        if "event: done\n" in frame:
            completed.append(json.loads(frame.split("data: ", 1)[1]))
    assert len(completed) == 1, response.text
    return dict(completed[0])


def _prompt(payload: dict[str, Any]) -> str:
    return "\n".join(str(item["content"]) for item in payload["messages"])


@pytest.mark.usefixtures("postgres_settings")
def test_sync_followups_survive_reload_and_reach_retrieval_and_synthesis(
    monkeypatch: pytest.MonkeyPatch, work_path: Path,
) -> None:
    topic = "中国共产党第一次全国代表大会"
    initial = f"{topic}在哪一年召开？"
    followup = "那它具体在哪里召开？"
    next_followup = "为什么后来又换了地方？"
    resolved = f"{topic}具体在哪里召开？"
    resolved_next = f"{topic}为什么后来改在嘉兴南湖召开？"
    boundary = ScriptedBoundary(monkeypatch, [
        _plan(initial, topic),
        _plan(resolved, topic, context=(1, 2)),
        _plan(resolved_next, topic, context=(4,)),
    ], [
        f"{topic}于1921年召开。[E1]",
        f"{topic}先在上海召开，后转到嘉兴南湖。[E1]",
        f"{topic}因会场安全问题改在嘉兴南湖继续举行。[E1]",
    ])
    with _client(work_path) as client:
        session_id = _session(client)
        first = _ask(client, session_id, initial)
        restored = client.get(f"/api/sessions/{session_id}")
        assert restored.status_code == 200
        assert restored.json()["messages"][0]["content"] == initial
        second = _ask(client, session_id, followup, history=[
            {"role": "user", "content": "客户端伪造的淮海战役上下文"},
        ])
        third = _ask(client, session_id, next_followup)
        messages = client.get(f"/api/sessions/{session_id}").json()["messages"]

    assert first["query_planner_status"] == second["query_planner_status"] == "used"
    assert third["query_planner_status"] == "used"
    assert [item["content"] for item in messages if item["role"] == "user"] == [
        initial, followup, next_followup,
    ]
    assert initial in _prompt(boundary.planner_payloads[1])
    assert "客户端伪造" not in _prompt(boundary.planner_payloads[1])
    assert "[历史引用]" in _prompt(boundary.planner_payloads[1])
    assert "[E1]" not in _prompt(boundary.planner_payloads[1])
    for number, (raw, normalized, result) in enumerate([
        (followup, resolved, second), (next_followup, resolved_next, third),
    ], start=1):
        assert raw not in boundary.searches[number]["query"]
        assert normalized in boundary.searches[number]["query"]
        assert normalized in _prompt(boundary.synthesis_payloads[number])
        assert result["question"] == raw
        assert result["query_plan"]["normalized_question"] == normalized
        assert {item["document_id"] for item in result["citations"]} == {
            f"current-source-{number + 1}",
        }
    history_prompt = next(
        str(item["content"])
        for item in boundary.synthesis_payloads[2]["messages"]
        if "<conversation_history>" in str(item["content"])
    )
    assert "[历史引用]" in history_prompt
    assert "[E1]" not in history_prompt


@pytest.mark.usefixtures("postgres_settings")
def test_streaming_topic_switch_and_summary_reference_share_the_same_context_path(
    monkeypatch: pytest.MonkeyPatch, work_path: Path,
) -> None:
    questions = [
        "介绍1935年遵义会议的召开背景。",
        "介绍七千人大会的召开地点。",
        "介绍西安事变的处理经过。",
        "回到最早讨论的会议，地点是什么？",
    ]
    plans = [
        {**_plan(questions[0], "遵义会议"), "start_year": 1935, "end_year": 1935},
        _plan(questions[1], "七千人大会"),
        _plan(questions[2], "西安事变"),
        _plan("遵义会议在哪里召开？", "遵义会议", context=(1,)),
    ]
    boundary = ScriptedBoundary(monkeypatch, plans, [
        "遵义会议召开前，红军面临军事指挥问题。[E1]",
        "七千人大会在北京召开。[E1]",
        "西安事变最终通过谈判和平解决。[E1]",
        "遵义会议在遵义举行。[E1]",
    ])
    with _client(work_path) as client:
        session_id = _session(client)
        results = [_ask(client, session_id, question, stream=True) for question in questions]
        stored = client.get(f"/api/sessions/{session_id}").json()

    assert all(item["query_planner_status"] == "used" for item in results)
    assert stored["session"]["message_count"] == 8
    # The planner sees context even when its semantic decision is to start a new topic.
    assert questions[0] in _prompt(boundary.planner_payloads[1])
    assert results[1]["query_plan"]["context_message_indices"] == []
    assert "遵义会议" not in boundary.searches[1]["query"]
    assert boundary.searches[1]["plan"].query_year_range == []
    assert boundary.searches[1]["plan"].query_people == []
    assert "会话摘要" in _prompt(boundary.planner_payloads[3])
    assert "遵义会议" in _prompt(boundary.planner_payloads[3])
    assert "[E1]" not in _prompt(boundary.planner_payloads[3])
    assert "遵义会议在哪里召开" in boundary.searches[3]["query"]
    assert "遵义会议在哪里召开" in _prompt(boundary.synthesis_payloads[3])
    assert results[3]["query_plan"]["context_message_indices"] == [1]
    assert {item["document_id"] for item in results[3]["citations"]} == {"current-source-4"}


@pytest.mark.usefixtures("postgres_settings")
def test_ambiguous_followup_clarifies_without_search_or_generation(
    monkeypatch: pytest.MonkeyPatch, work_path: Path,
) -> None:
    initial = "比较遵义会议与瓦窑堡会议的主要议题。"
    followup = "它是在哪里开的？"
    clarification = "你想问遵义会议还是瓦窑堡会议的地点？"
    boundary = ScriptedBoundary(monkeypatch, [
        _plan(initial, "遵义会议"),
        {
            "intent": "event_overview",
            "normalized_question": followup,
            "context_message_indices": [1, 2],
            "needs_clarification": True,
            "clarification_question": clarification,
        },
    ], ["遵义会议讨论军事指挥，瓦窑堡会议讨论抗日民族统一战线。[E1]"])
    with _client(work_path) as client:
        session_id = _session(client)
        _ask(client, session_id, initial)
        result = _ask(client, session_id, followup)

    assert "遵义会议与瓦窑堡会议" in _prompt(boundary.planner_payloads[1])
    assert result["query_planner_status"] == "used"
    assert result["answer"] == clarification
    assert result["execution_summary"]["stopped_reason"] == "clarification"
    assert result["execution_summary"]["retrieval_calls"] == 0
    assert result["citations"] == []
    assert len(boundary.searches) == len(boundary.synthesis_payloads) == 1
