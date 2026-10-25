from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from history_agent.answering.models import (
    ConversationMessage,
    QueryPlan,
    QuestionRequest,
    ResearchTask,
)
from history_agent.answering.planning import compile_research_plan, extend_research_plan
from history_agent.answering.query_understanding import plan_question, resolved_request
from history_agent.config import Settings


def _planner(monkeypatch: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> httpx.Response:
        calls.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
        })

    monkeypatch.setattr(httpx, "post", post)
    return calls


@pytest.mark.parametrize("question", [
    "那它具体在哪里召开？为什么中途更换会址？",
    "请补充具体地点与原因。",
    "用表格整理，保留地点和日期。",
    "Can you explain the venue change?",
])
def test_context_reaches_planner_without_a_followup_phrase_allowlist(
    monkeypatch: Any, question: str,
) -> None:
    resolved = "中国共产党第一次全国代表大会的会址及迁址原因"
    calls = _planner(monkeypatch, {
        "normalized_question": resolved,
        "context_message_indices": [1, 2],
        "entities": [{
            "type": "event", "text": "中共一大", "canonical": "中国共产党第一次全国代表大会",
        }],
        "tasks": [{
            "task_id": "venues", "tool": "search", "objective": "查会址", "query": "会址变化",
        }],
    })
    request = QuestionRequest(question=question, history=[
        ConversationMessage(role="user", content="中共一大在哪一年召开？"),
        ConversationMessage(role="assistant", content="1921年召开。[E99]"),
    ])
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), request)
    assert len(calls) == 1  # Resolution remains part of the existing planning call.
    prompt = calls[0]["messages"][-1]["content"]
    assert "中共一大" in prompt and '"index": 2' in prompt
    assert "[E99]" not in prompt and "[历史引用]" in prompt
    assert result.status == "used" and result.research_plan is not None
    assert result.plan is not None and result.plan.entities[0].canonical in resolved
    assert result.plan.start_year is None  # A dated answer is not an inherited filter.
    assert resolved in result.research_plan.tasks[0].query
    assert result.research_plan.question == question
    execution = resolved_request(request, result.plan)
    assert execution.question == resolved and len(execution.history) == 2
    assert request.question == question  # Transcript and response keep the user's wording.


def test_reference_can_come_from_assistant_or_earlier_turn_not_only_latest_user(
    monkeypatch: Any,
) -> None:
    _planner(monkeypatch, {
        "normalized_question": "邓小平在1949年的活动",
        "context_message_indices": [2, 3], "intent": "timeline",
        "start_year": 1949, "end_year": 1949,
        "entities": [{"type": "person", "text": "邓小平", "canonical": "邓小平"}],
    })
    request = QuestionRequest(question="再补充他的工作。", history=[
        ConversationMessage(role="user", content="这份文献的作者是谁？"),
        ConversationMessage(role="assistant", content="作者是邓小平。[E8]"),
        ConversationMessage(role="user", content="介绍他在1949年的情况。"),
        ConversationMessage(role="assistant", content="相关记载……"),
    ])
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), request)
    assert result.status == "used" and result.plan is not None
    assert [entity.canonical for entity in result.plan.entities] == ["邓小平"]
    assert (result.plan.start_year, result.plan.end_year) == (1949, 1949)


def test_source_constraint_in_summary_survives_task_compilation_and_replanning(
    monkeypatch: Any,
) -> None:
    resolved = "仅依据《周恩来年谱》概括周恩来1936年下半年的活动，排除军事活动"
    _planner(monkeypatch, {
        "normalized_question": resolved, "context_message_indices": [1, 2],
        "intent": "timeline", "retrieval_route": "hybrid",
        "start_year": 1936, "end_year": 1936,
        "constraints": ["下半年", "排除军事活动"],
        "entities": [{"type": "person", "text": "周恩来", "canonical": "周恩来"}],
        "tasks": [{
            "task_id": "lookup", "tool": "search", "objective": "查询活动", "query": "活动",
        }],
    })
    request = QuestionRequest(question="只看下半年，排除军事活动。", history=[
        ConversationMessage(role="assistant", content="会话摘要：仅依据《周恩来年谱》研究周恩来。"),
        ConversationMessage(role="user", content="介绍1936年的主要活动。"),
        ConversationMessage(role="assistant", content="已找到部分记录。[E7]"),
    ])
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), request)
    assert result.status == "used" and result.research_plan is not None
    task = result.research_plan.tasks[0]
    assert task.tool == "search" and task.source_title == "周恩来年谱"
    assert resolved in task.query
    revised = extend_research_plan(result.research_plan, [task.model_copy(update={
        "task_id": "more", "query": "补充相关活动", "depends_on": [task.task_id],
    })])
    assert resolved in revised.tasks[-1].query
    assert revised.tasks[-1].source_title == "周恩来年谱"


def test_new_topic_does_not_receive_old_context_in_execution() -> None:
    request = QuestionRequest(question="介绍淮海战役。", history=[
        ConversationMessage(role="user", content="只依据《毛泽东年谱》谈1935年毛泽东。"),
    ])
    plan = QueryPlan(normalized_question=request.question)
    execution = resolved_request(request, plan)
    assert execution.history == []
    assert execution.question == request.question
    task = compile_research_plan(request.question, plan).tasks[0]
    assert task.start_year is None and task.source_title is None and task.person_names == []


def test_current_exclusive_source_replaces_inherited_source(monkeypatch: Any) -> None:
    _planner(monkeypatch, {
        "normalized_question": "仅依据《周恩来年谱》介绍周恩来1936年的活动",
        "context_message_indices": [1],
        "entities": [{"type": "person", "text": "周恩来", "canonical": "周恩来"}],
        "start_year": 1936, "end_year": 1936,
        "tasks": [{
            "task_id": "lookup", "tool": "search", "objective": "查询年谱活动",
            "query": "《周恩来年谱》相关活动", "source_title": "周恩来年谱",
        }],
    })
    request = QuestionRequest(question="改为只依据《毛泽东年谱》，继续介绍他的活动。", history=[
        ConversationMessage(role="user", content="只依据《周恩来年谱》介绍周恩来1936年的活动"),
    ])
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), request)
    assert result.status == "used" and result.research_plan is not None
    assert result.plan is not None
    assert "《毛泽东年谱》" in resolved_request(request, result.plan).question
    task = result.research_plan.tasks[0]
    assert task.source_title == "毛泽东年谱"
    assert "《周恩来年谱》" not in task.query


def test_maximum_length_followup_keeps_resolved_constraints_without_overflow() -> None:
    question = "请继续说明。" + "具体说明。" * 90
    resolved = "介绍毛泽东活动。" + "保留原文。" * 90
    plan = compile_research_plan(question, QueryPlan(
        normalized_question=resolved, context_message_indices=[1],
        tasks=[ResearchTask(
            task_id="long", tool="search", query="查原文。" * 250, objective="查询原文",
        )],
    ))
    assert resolved in plan.tasks[0].query
    assert len(plan.tasks[0].query) <= 1000
    assert plan.question == question


def test_unknown_history_reference_cannot_be_used_as_valid_context(monkeypatch: Any) -> None:
    _planner(monkeypatch, {"normalized_question": "一个臆造的主体", "context_message_indices": [9]})
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), QuestionRequest(
        question="其原因是什么？", history=[ConversationMessage(role="user", content="介绍某会议")],
    ))
    assert result.status == "fallback" and result.error_code == "invalid_plan"
    assert result.plan is not None and result.plan.needs_clarification
    assert result.research_plan is not None and result.research_plan.tasks == []


def test_planner_cannot_silently_omit_context_resolution(monkeypatch: Any) -> None:
    _planner(monkeypatch, {"normalized_question": "其具体原因是什么？"})
    result = plan_question(Settings(_env_file=None, llm_api_key="test"), QuestionRequest(
        question="其具体原因是什么？",
        history=[ConversationMessage(role="user", content="介绍某会议")],
    ))
    assert result.status == "fallback"
    assert result.plan is not None and result.plan.needs_clarification
    assert result.research_plan is not None and result.research_plan.tasks == []


def test_current_source_is_enforced_even_if_rewrite_omits_exclusivity() -> None:
    with pytest.raises(ValueError, match="exclusive source"):
        compile_research_plan("改为只依据《毛泽东年谱》，继续介绍他的活动。", QueryPlan(
            normalized_question="介绍周恩来活动，参考《周恩来年谱》",
            context_message_indices=[1],
            tasks=[ResearchTask(
                task_id="lookup", tool="search", query="相关活动", objective="查询活动",
                source_title="周恩来年谱",
            )],
        ))


@pytest.mark.parametrize("failure", ["timeout", "disabled"])
def test_unavailable_planning_does_not_search_a_bare_followup(
    monkeypatch: Any, failure: str,
) -> None:
    def timeout(*args: Any, **kwargs: Any) -> httpx.Response:
        raise httpx.ReadTimeout("unavailable")

    monkeypatch.setattr(httpx, "post", timeout)
    result = plan_question(Settings(
        _env_file=None, llm_api_key="test", llm_query_planning=failure != "disabled",
    ), QuestionRequest(question="其具体影响是什么？", history=[
        ConversationMessage(role="user", content="介绍某项政策。"),
    ]))
    assert result.plan is not None and result.plan.needs_clarification
    assert result.research_plan is not None and result.research_plan.tasks == []
    assert "未能可靠解析" in (result.plan.clarification_question or "")
