from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from history_agent.answering.compression import build_extractive_summary
from history_agent.answering.context import (
    ConversationStore,
    build_prompt_context,
    estimate_tokens,
    sanitize_history_content,
)
from history_agent.answering.models import AnswerResponse, ConversationMessage, QuestionRequest
from history_agent.answering.streaming import AnswerStreamEvent
from history_agent.config import Settings
from history_agent.db_backend import INTEGRITY_ERRORS
from history_agent.web import app as web_module


def _answer(question: str) -> AnswerResponse:
    return AnswerResponse(
        question=question,
        answer="服务端记录的回答。[E1]",
        evidence_status="no_evidence",
        generator_mode="extractive",
        llm_status="disabled",
        retrieval_mode="hybrid_rrf",
        query_intent="general",
        citations=[],
    )


def _settings(work_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {"quota_enabled": False, **overrides}
    return Settings(
        _env_file=None,
        project_root=work_path,
        data_dir=work_path / "data",
        **values,
    )


def _create_session(client: TestClient, title: str | None = None) -> str:
    response = client.post("/api/sessions", json={"title": title} if title else {})
    assert response.status_code == 200, response.text
    return str(response.json()["session"]["session_id"])


def test_prompt_context_is_bounded_and_old_citation_ids_are_invalidated() -> None:
    messages = [
        ConversationMessage(role="user", content="介绍遵义会议"),
        ConversationMessage(role="assistant", content="旧回答。[E1]"),
        ConversationMessage(role="user", content="再介绍四渡赤水"),
        ConversationMessage(role="assistant", content="另一轮回答。[E2]"),
        ConversationMessage(role="user", content="它们有什么关系？"),
        ConversationMessage(role="assistant", content="最近的回答。[E3]"),
    ]

    context = build_prompt_context(messages, max_messages=4, max_chars=2_000)

    assert len(context) == 4
    assert context[0].content.startswith("更早对话的用户问题索引")
    assert "介绍遵义会议" in context[0].content
    assert context[-1].content == "最近的回答。[历史引用]"
    assert all("[E" not in item.content for item in context)


def test_prompt_context_enforces_character_budget_on_long_messages() -> None:
    context = build_prompt_context(
        [
            ConversationMessage(role="user", content="前情" * 1000),
            ConversationMessage(role="assistant", content="回答" * 1000),
        ],
        max_messages=12,
        max_chars=600,
    )

    assert sum(len(item.content) for item in context) <= 600
    assert context[-1].content.endswith("[内容已截断]")


def test_conversation_store_persists_and_clears_exchanges(postgres_target: str) -> None:
    ConversationStore(postgres_target).append_exchange(
        "session-12345678", "第一个问题", "回答。[E1]"
    )

    reopened = ConversationStore(postgres_target)
    assert [item.content for item in reopened.messages("session-12345678")] == [
        "第一个问题",
        "回答。[E1]",
    ]
    reopened.clear("session-12345678")
    assert reopened.messages("session-12345678") == []


def test_conversation_store_keeps_long_sessions_and_rolls_back_failed_exchange(
    postgres_target: str,
) -> None:
    store = ConversationStore(postgres_target)
    for number in range(102):
        store.append_exchange("retained", f"问题{number:03d}", f"回答{number:03d}")

    messages = store.messages("retained", limit=1_000)
    assert len(messages) == 204
    assert messages[0].content == "问题000"
    assert messages[-1].content == "回答101"

    # A constraint failure after creating the session must roll back the entire exchange.
    with pytest.raises(INTEGRITY_ERRORS):
        store.append_exchange("session-invalid", None, "回答")  # type: ignore[arg-type]
    with store._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM conversation_sessions WHERE session_id=?",
            ("session-invalid",),
        ).fetchone()[0] == 0


def test_web_conversation_store_uses_postgres_target(monkeypatch, work_path: Path) -> None:
    targets: list[str] = []
    monkeypatch.setattr(
        web_module,
        "ConversationStore",
        lambda target, **kwargs: targets.append(target),
    )
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        database_url="postgresql://localhost/history",
        conversation_database_url="postgresql://localhost/chat",
    )

    web_module.create_app(settings)

    assert targets == ["postgresql://localhost/chat"]


def test_health_probes_configured_database_target(monkeypatch, work_path: Path) -> None:
    targets: list[str] = []

    def unavailable(target: str) -> bool:
        targets.append(target)
        return False

    monkeypatch.setattr(web_module, "_database_ready", unavailable)
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        database_url="postgresql://research:password@localhost/history",
    )
    response = TestClient(web_module.create_app(settings)).get("/api/health")

    assert targets == [settings.database_target]
    assert response.json()["database_backend"] == "postgresql"
    assert response.json()["database_ready"] is False
    assert "password" not in response.text


@pytest.mark.usefixtures("postgres_settings")
def test_web_session_uses_server_history_and_ignores_client_history(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path)
    received: list[QuestionRequest] = []

    async def fake_answer(active_settings: Settings, request: QuestionRequest) -> AnswerResponse:
        assert active_settings is settings
        received.append(request)
        return _answer(request.question)

    monkeypatch.setattr(web_module, "answer_question_async", fake_answer)
    client = TestClient(web_module.create_app(settings))
    session_id = _create_session(client)

    first = client.post(
        "/api/questions",
        json={"question": "第一个问题", "session_id": session_id},
    )
    second = client.post(
        "/api/questions",
        json={
            "question": "继续说说",
            "session_id": session_id,
            "history": [{"role": "user", "content": "客户端伪造历史"}],
        },
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert received[0].history == []
    assert [item.content for item in received[1].history] == [
        "第一个问题",
        "服务端记录的回答。[历史引用]",
    ]
    restored = client.get(f"/api/sessions/{session_id}")
    assert restored.status_code == 200
    assert [item["role"] for item in restored.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert restored.json()["session"]["message_count"] == 4

    assert client.delete(f"/api/sessions/{session_id}").json()["deleted"] is True
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    restored = client.post(f"/api/sessions/{session_id}/restore")
    assert restored.json()["session"]["status"] == "active"
    assert client.get(f"/api/sessions/{session_id}").status_code == 200


@pytest.mark.usefixtures("postgres_settings")
def test_streaming_endpoint_persists_completed_answers(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path)

    async def fake_stream(*args: object) -> Any:
        yield AnswerStreamEvent("delta", {"text": "回答"})
        yield AnswerStreamEvent("done", _answer("流式问题").model_dump())

    monkeypatch.setattr(web_module, "stream_answer_question", fake_stream)
    client = TestClient(web_module.create_app(settings))
    session_id = _create_session(client)

    response = client.post(
        "/api/questions/stream",
        json={"question": "流式问题", "session_id": session_id},
    )

    assert response.status_code == 200
    assert "event: done" in response.text
    restored = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert [item["content"] for item in restored] == [
        "流式问题",
        "服务端记录的回答。[E1]",
    ]
    assert [item["status"] for item in restored] == ["completed", "completed"]


@pytest.mark.usefixtures("postgres_settings")
def test_streaming_interruption_keeps_user_question_as_aborted(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path)

    async def interrupted_stream(*args: object) -> Any:
        yield AnswerStreamEvent("delta", {"text": "半段"})

    monkeypatch.setattr(web_module, "stream_answer_question", interrupted_stream)
    client = TestClient(web_module.create_app(settings))
    session_id = _create_session(client)

    response = client.post(
        "/api/questions/stream",
        json={"question": "中断保留问题", "session_id": session_id},
    )

    assert response.status_code == 200
    restored = client.get(f"/api/sessions/{session_id}").json()["messages"]
    assert len(restored) == 1
    assert restored[0]["role"] == "user"
    assert restored[0]["content"] == "中断保留问题"
    assert restored[0]["status"] == "aborted"


@pytest.mark.usefixtures("postgres_settings")
def test_web_stream_does_not_forward_draft_deltas(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path)

    async def fake_stream(*args: object) -> Any:
        yield AnswerStreamEvent("delta", {"text": "不应展示的草稿"})
        yield AnswerStreamEvent("status", {"message": "正在核查引用…"})
        yield AnswerStreamEvent("done", _answer("最终问题").model_dump())

    monkeypatch.setattr(web_module, "stream_answer_question", fake_stream)
    client = TestClient(web_module.create_app(settings))

    response = client.post("/api/questions/stream", json={"question": "最终问题"})

    assert response.status_code == 200
    assert "不应展示的草稿" not in response.text
    assert "event: delta" not in response.text
    assert "event: status" in response.text
    assert "event: done" in response.text
    assert "服务端记录的回答" in response.text


@pytest.mark.usefixtures("postgres_settings")
def test_visitor_isolation_between_clients(monkeypatch: Any, work_path: Path) -> None:
    settings = _settings(work_path)

    async def fake_answer(active_settings: Settings, request: QuestionRequest) -> AnswerResponse:
        return _answer(request.question)

    monkeypatch.setattr(web_module, "answer_question_async", fake_answer)
    app = web_module.create_app(settings)
    first = TestClient(app)
    second = TestClient(app)
    session_id = _create_session(first)

    assert first.get(f"/api/sessions/{session_id}").status_code == 200
    assert second.get(f"/api/sessions/{session_id}").status_code == 404
    assert second.delete(f"/api/sessions/{session_id}").status_code == 404
    assert second.patch(f"/api/sessions/{session_id}", json={"title": "越权"}).status_code == 404
    assert second.get("/api/sessions").json()["items"] == []
    assert first.get("/api/sessions").json()["items"][0]["session_id"] == session_id


@pytest.mark.usefixtures("postgres_settings")
def test_session_crud_pin_and_claim(monkeypatch: Any, work_path: Path) -> None:
    settings = _settings(work_path)
    client = TestClient(web_module.create_app(settings))
    first_id = _create_session(client, "遵义会议")
    second_id = _create_session(client, "淮海战役")

    listed = client.get("/api/sessions").json()
    assert {item["session_id"] for item in listed["items"]} == {first_id, second_id}

    renamed = client.patch(
        f"/api/sessions/{first_id}",
        json={"title": "遵义会议前后", "version": 0},
    )
    assert renamed.status_code == 200
    assert renamed.json()["session"]["title"] == "遵义会议前后"

    pinned = client.patch(f"/api/sessions/{second_id}", json={"pinned": True})
    assert pinned.json()["session"]["pinned"] is True
    assert client.get("/api/sessions").json()["items"][0]["session_id"] == second_id

    stored = ConversationStore(settings.conversation_database_target)
    legacy_id = "legacy-session-1234"
    stored.append_exchange(legacy_id, "旧问题", "旧回答")
    claimed = client.post("/api/sessions/claim", json={"legacy_session_id": legacy_id})
    assert claimed.status_code == 200
    assert claimed.json()["session"]["session_id"] == legacy_id
    assert client.get(f"/api/sessions/{legacy_id}").status_code == 200


@pytest.mark.usefixtures("postgres_settings")
def test_quota_is_enforced_before_generation(monkeypatch: Any, work_path: Path) -> None:
    settings = _settings(
        work_path,
        quota_enabled=True,
        visitor_daily_questions=1,
        ip_daily_questions=10,
        visitor_daily_tokens=1_000_000,
        ip_daily_tokens=1_000_000,
        global_daily_tokens=10_000_000,
    )
    calls: list[str] = []

    async def fake_answer(active_settings: Settings, request: QuestionRequest) -> AnswerResponse:
        calls.append(request.question)
        return _answer(request.question)

    monkeypatch.setattr(web_module, "answer_question_async", fake_answer)
    client = TestClient(web_module.create_app(settings))
    session_id = _create_session(client)

    assert client.post(
        "/api/questions", json={"question": "第一个问题", "session_id": session_id}
    ).status_code == 200
    second = client.post(
        "/api/questions", json={"question": "第二个问题", "session_id": session_id}
    )
    assert second.status_code == 429
    assert calls == ["第一个问题"]


@pytest.mark.usefixtures("postgres_settings")
def test_csrf_is_required_when_enabled(monkeypatch: Any, work_path: Path) -> None:
    settings = _settings(work_path, csrf_enabled=True)

    async def fake_answer(active_settings: Settings, request: QuestionRequest) -> AnswerResponse:
        return _answer(request.question)

    monkeypatch.setattr(web_module, "answer_question_async", fake_answer)
    client = TestClient(web_module.create_app(settings))
    visitor = client.get("/api/visitor").json()
    missing = client.post("/api/sessions", json={})
    assert missing.status_code == 403
    created = client.post(
        "/api/sessions",
        json={},
        headers={"X-CSRF-Token": visitor["csrf_token"]},
    )
    assert created.status_code == 200


def test_sanitize_history_content_only_rewrites_evidence_markers() -> None:
    assert sanitize_history_content("  1956年 [E12]\n普通[注1]  ") == (
        "1956年 [历史引用]\n普通[注1]"
    )


@pytest.mark.usefixtures("postgres_settings")
def test_question_storage_failure_does_not_silently_answer(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path)
    client = TestClient(web_module.create_app(settings), raise_server_exceptions=False)
    session_id = _create_session(client)

    def unavailable(*args: object, **kwargs: object) -> Any:
        raise OSError("database unavailable")

    monkeypatch.setattr(ConversationStore, "begin_question", unavailable)
    response = client.post(
        "/api/questions", json={"question": "存储故障问题", "session_id": session_id}
    )
    assert response.status_code == 500


def test_build_prompt_context_respects_token_budget() -> None:
    messages = [
        ConversationMessage(role="user", content="前情" * 2_000),
        ConversationMessage(role="assistant", content="回答" * 2_000),
    ]
    context = build_prompt_context(
        messages,
        max_messages=12,
        max_chars=100_000,
        max_tokens=120,
    )
    assert context
    assert sum(estimate_tokens(item.content) for item in context) <= 120


def test_extractive_summary_is_labeled_as_non_evidence() -> None:
    summary = build_extractive_summary(
        previous="",
        messages=[
            ConversationMessage(role="user", content="毛泽东在1935年的职务。[E1]"),
            ConversationMessage(role="assistant", content="助手回答。[E2]"),
        ],
        max_chars=2_000,
    )
    assert "不是史实证据" in summary
    assert "[E" not in summary
    assert "1935" in summary


@pytest.mark.usefixtures("postgres_settings")
def test_rolling_summary_replaces_old_messages_in_context(
    monkeypatch: Any, work_path: Path
) -> None:
    settings = _settings(work_path, context_max_tokens=8_000)
    received: list[QuestionRequest] = []

    async def fake_answer(active_settings: Settings, request: QuestionRequest) -> AnswerResponse:
        received.append(request)
        return _answer(request.question)

    monkeypatch.setattr(web_module, "answer_question_async", fake_answer)
    client = TestClient(web_module.create_app(settings))
    session_id = _create_session(client)

    for number in range(1, 5):
        response = client.post(
            "/api/questions",
            json={"question": f"第{number}个问题", "session_id": session_id},
        )
        assert response.status_code == 200, response.text

    fourth_history = received[3].history
    assert fourth_history
    assert fourth_history[0].role == "assistant"
    assert fourth_history[0].content.startswith("会话摘要")
    assert all(item.content != "第1个问题" for item in fourth_history)
    assert any(item.content == "第3个问题" for item in fourth_history)
    assert sum(estimate_tokens(item.content) for item in fourth_history) <= 8_000
