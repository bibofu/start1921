from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from history_agent.answering.models import QueryEntity, QueryPlan, QuestionRequest, ResearchTask
from history_agent.answering.planning import (
    compile_research_plan,
    extend_research_plan,
    validate_research_plan,
)
from history_agent.answering.query_understanding import _messages, plan_question
from history_agent.answering.runtime import RequestBudget
from history_agent.config import Settings
from pydantic import ValidationError

QUESTION = "比较毛泽东在1935至1936年的主要活动"


def _interpretation(**updates: Any) -> QueryPlan:
    return QueryPlan.model_validate({
        "normalized_question": QUESTION, "intent": "comparison",
        "start_year": 1935, "end_year": 1936,
        "entities": [QueryEntity(type="person", text="毛泽东", canonical="毛泽东")],
        **updates,
    })


def _task(task_id: str = "first", **updates: Any) -> ResearchTask:
    return ResearchTask.model_validate({
        "task_id": task_id, "tool": "search", "objective": "寻找活动记录", "query": "主要活动",
        **updates,
    })


def test_simple_and_complex_plans_share_one_executable_schema() -> None:
    simple = compile_research_plan(QUESTION, _interpretation())
    assert len(simple.tasks) == 1
    assert simple.tasks[0].tool == "search"
    assert simple.tasks[0].person_names == ["毛泽东"]
    assert simple.interpretation.tasks == []

    complex_plan = compile_research_plan(QUESTION, _interpretation(tasks=[
        _task("first", start_year=1935, end_year=1935),
        _task("second", start_year=1936, end_year=1936),
        _task("compare", tool="analyze", depends_on=["first", "second"]),
    ]))
    assert len(complex_plan.tasks) == 3
    assert complex_plan.interpretation.tasks == []
    assert complex_plan.tasks[2].depends_on == ["first", "second"]
    assert all(QUESTION in task.query for task in complex_plan.tasks)
    assert complex_plan.tasks[2].start_year == 1935


@pytest.mark.parametrize("invalid_tasks", [
    [_task("same"), _task("same")],
    [_task("first", depends_on=["missing"])],
    [_task("first", depends_on=["second"]), _task("second", depends_on=["first"])],
    [_task("first", depends_on=["first"])],
    [_task("first"), _task("second", depends_on=["first", "first"])],
    [_task("first", tool="analyze")],
])
def test_invalid_task_graphs_are_rejected(invalid_tasks: list[ResearchTask]) -> None:
    with pytest.raises(ValidationError):
        compile_research_plan(QUESTION, _interpretation(tasks=invalid_tasks))


@pytest.mark.parametrize("updates", [
    {"tool": "execute_python"}, {"arguments": {"sql": "SELECT 1"}},
    {"start_year": 1935}, {"start_year": 1936, "end_year": 1935},
])
def test_tool_allowlist_and_typed_arguments_reject_invalid_values(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _task(**updates)


@pytest.mark.parametrize("updates", [
    {"start_year": 1934, "end_year": 1936},
    {"person_names": ["林彪"]},
    {"source_title": "不存在于问题的书名"},
    {"document_ids": ["invented-local-id"]},
])
def test_tasks_cannot_broaden_scope_or_invent_filters(updates: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        compile_research_plan(QUESTION, _interpretation(tasks=[_task(**updates)]))


def test_exclusive_source_and_untyped_constraints_are_preserved() -> None:
    question = "仅依据《毛泽东年谱》说明1935年1月毛泽东在遵义的活动，不含其他地点"
    plan = compile_research_plan(question, QueryPlan(normalized_question=question, tasks=[_task()]))
    assert plan.tasks[0].source_title == "毛泽东年谱"
    assert question in plan.tasks[0].query


def test_full_text_and_book_publication_dates_compile_conservatively() -> None:
    question = "提供《毛泽东选集（1921—1949）》下卷某篇文章全文"
    plan = compile_research_plan(question, None)
    assert plan.tasks[0].tool == "read_source"
    assert plan.tasks[0].source_title == "毛泽东选集（1921—1949）"
    assert plan.tasks[0].start_year is None
    assert "下卷" in plan.tasks[0].query


def test_validated_structured_intent_compiles_a_tool_task() -> None:
    plan = compile_research_plan(QUESTION, _interpretation(
        intent="timeline", retrieval_route="structured",
    ))
    assert plan.tasks[0].tool == "timeline"
    assert plan.tasks[0].person_names == ["毛泽东"]


def test_omitted_task_coverage_and_aspects_inherit_global_requirements() -> None:
    plan = compile_research_plan(QUESTION, _interpretation(
        coverage="per_year", constraints=["逐年列出"], tasks=[_task()],
    ))
    assert plan.tasks[0].coverage == "per_year"
    assert plan.tasks[0].required_aspects == ["逐年列出"]


def test_structured_tool_cannot_bypass_hybrid_only_constraints() -> None:
    with pytest.raises(ValueError, match="hybrid-only"):
        compile_research_plan(QUESTION, _interpretation(tasks=[
            _task(tool="timeline", person_names=["毛泽东"]),
        ]))


@pytest.mark.parametrize("updates", [
    {"intent": "out_of_scope"},
    {"needs_clarification": True, "clarification_question": "你指哪位人物？"},
])
def test_terminal_plans_have_no_executable_tasks(updates: dict[str, Any]) -> None:
    plan = compile_research_plan(QUESTION, _interpretation(tasks=[_task()], **updates))
    assert plan.tasks == []
    assert plan.interpretation.tasks == []


def test_replanning_preserves_completed_work_and_limits_revision_count() -> None:
    initial = compile_research_plan(QUESTION, _interpretation())
    second = extend_research_plan(initial, [_task("supplement_1", depends_on=["task_1"])])
    third = extend_research_plan(second, [_task("supplement_2", depends_on=["supplement_1"])])
    assert third.revision == 2
    assert third.tasks[0] == initial.tasks[0]
    assert all(QUESTION in task.query for task in third.tasks)
    with pytest.raises(ValidationError):
        extend_research_plan(third, [_task("supplement_3")])
    with pytest.raises(ValueError):
        extend_research_plan(initial, [])
    with pytest.raises(ValidationError):
        extend_research_plan(initial, [_task(f"extra_{number}") for number in range(8)])


def test_pending_analysis_can_wait_for_supplement_without_dropping_original_evidence() -> None:
    initial = compile_research_plan(QUESTION, _interpretation(tasks=[
        _task("first"), _task("compare", tool="analyze", depends_on=["first"]),
    ]))
    revised = extend_research_plan(
        initial, [_task("supplement", depends_on=["first"])],
        completed_task_ids={"first"}, redirect_pending_dependencies={"first": "supplement"},
    )
    assert revised.tasks[1].depends_on == ["supplement"]
    assert revised.tasks[0] == initial.tasks[0]
    assert revised.tasks[1].query == initial.tasks[1].query
    with pytest.raises(ValueError, match="original evidence branches"):
        extend_research_plan(
            initial, [_task("unrelated")], completed_task_ids={"first"},
            redirect_pending_dependencies={"first": "unrelated"},
        )
    with pytest.raises(ValueError, match="completed task IDs"):
        extend_research_plan(initial, [_task("supplement")],
                             redirect_pending_dependencies={"first": "supplement"})
    with pytest.raises(ValueError, match="completed tasks"):
        validate_research_plan(revised, initial, completed_task_ids={"first", "compare"})


@pytest.mark.parametrize("changed", ["question", "interpretation", "task"])
def test_replanning_cannot_rewrite_user_scope_or_existing_work(changed: str) -> None:
    initial = compile_research_plan(QUESTION, _interpretation())
    revised = extend_research_plan(initial, [_task("supplement")])
    if changed == "question":
        revised = revised.model_copy(update={"question": "改变了用户问题"})
    elif changed == "interpretation":
        revised = revised.model_copy(update={
            "interpretation": revised.interpretation.model_copy(update={"coverage": "per_year"}),
        })
    else:
        revised.tasks[0] = revised.tasks[0].model_copy(update={"objective": "悄悄更改目标"})
    with pytest.raises(ValueError):
        validate_research_plan(revised, initial, completed_task_ids=set())


def test_one_planner_call_produces_semantics_and_dependency_plan(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    payload = _interpretation(tasks=[
        _task("first"), _task("compare", tool="analyze", depends_on=["first"]),
    ]).model_dump()

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        calls.append(kwargs)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 80, "total_tokens": 130},
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    budget = RequestBudget.start(60)
    result = plan_question(
        Settings(_env_file=None, llm_api_key="sk-test"), QuestionRequest(question=QUESTION),
        budget=budget,
    )
    assert result.status == "used"
    assert len(calls) == 1
    assert budget.llm_calls == 1
    assert result.research_plan is not None
    assert result.plan == result.research_plan.interpretation
    assert result.plan is not None and result.plan.tasks == []
    assert [task.tool for task in result.research_plan.tasks] == ["search", "analyze"]
    assert result.usage is not None and result.usage["total_tokens"] == 130


def test_disabled_planner_still_compiles_a_single_executable_task(monkeypatch: Any) -> None:
    def unexpected_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Disabled planning must not call the LLM")

    monkeypatch.setattr(httpx, "post", unexpected_call)
    result = plan_question(Settings(_env_file=None, llm_query_planning=False),
                           QuestionRequest(question=QUESTION))
    assert result.status == "disabled"
    assert result.plan is None
    assert result.research_plan is not None
    assert len(result.research_plan.tasks) == 1
    assert result.research_plan.tasks[0].start_year == 1935


@pytest.mark.parametrize(("question", "tool"), [
    ("毛泽东在1935至1936年的主要活动", "timeline"),
    ("毛泽东与周恩来在1935年的共同活动", "intersection"),
    ("毛泽东1935年1月的活动", "search"),
    ("毛泽东1935年在遵义的活动", "search"),
    ("仅依据《毛泽东年谱》列出毛泽东1935年的活动", "search"),
    ("毛泽东1935年除遵义外的活动", "search"),
    ("提供《论持久战》全文", "read_source"),
])
def test_model_off_compiles_narrow_domain_tools(question: str, tool: str) -> None:
    result = plan_question(Settings(_env_file=None, llm_query_planning=False),
                           QuestionRequest(question=question))
    assert result.research_plan is not None
    assert result.research_plan.tasks[0].tool == tool


def test_invalid_model_tasks_fall_back_to_same_schema_without_second_call(monkeypatch: Any) -> None:
    calls = 0
    payload = _interpretation().model_dump()
    payload["tasks"] = [_task().model_dump() | {"tool": "browser"}]

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    result = plan_question(Settings(_env_file=None, llm_api_key="sk-test"),
                           QuestionRequest(question=QUESTION))
    assert result.status == "fallback"
    assert result.error_code == "invalid_plan"
    assert result.research_plan is not None
    assert result.research_plan.tasks[0].tool == "search"
    assert calls == 1


def test_planner_prompt_respects_explicit_token_ceiling_and_reserves_task_slots() -> None:
    request = QuestionRequest(question=QUESTION)
    small = _messages(Settings(_env_file=None, llm_query_planner_max_tokens=700), request)[0]
    large = _messages(Settings(_env_file=None, llm_query_planner_max_tokens=2000), request)[0]
    assert "最多700 tokens" in small["content"]
    assert "初始计划最多3个任务" in small["content"]
    assert "初始计划最多6个任务" in large["content"]
    assert "无需重复原问题" in small["content"]


def test_truncated_plan_keeps_usage_and_uses_conservative_fallback(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        captured.update(kwargs)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"finish_reason": "length", "message": {"content": '{"tasks":['}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 700, "total_tokens": 750},
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    result = plan_question(
        Settings(_env_file=None, llm_api_key="sk-test", llm_query_planner_max_tokens=700),
        QuestionRequest(question=QUESTION),
    )
    assert captured["json"]["max_tokens"] == 700
    assert result.error_code == "max_tokens_exhausted"
    assert result.usage is not None and result.usage["total_tokens"] == 750
    assert result.research_plan is not None and len(result.research_plan.tasks) == 1
