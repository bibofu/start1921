from __future__ import annotations

from history_agent.answering.models import ConversationMessage, QuestionRequest
from history_agent.answering.query_triggers import (
    is_context_dependent,
    is_low_recall,
    should_plan_query,
    should_rewrite_after_retrieval,
)
from history_agent.config import Settings
from test_retrieval import _hit, _response


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, llm_api_key="sk-test", **overrides)


def test_simple_self_contained_question_skips_the_planner() -> None:
    settings = _settings()
    assert not should_plan_query(
        settings, QuestionRequest(question="毛泽东在1949年的活动")
    )


def test_follow_up_complex_and_context_dependent_questions_plan() -> None:
    settings = _settings()
    history = [ConversationMessage(role="user", content="毛泽东在1949年的活动")]
    assert should_plan_query(
        settings, QuestionRequest(question="后来呢", history=history)
    )
    assert should_plan_query(
        settings, QuestionRequest(question="详细介绍淮海战役的前后经过")
    )
    assert should_plan_query(
        settings, QuestionRequest(question="他后来采取了什么政策")
    )
    assert is_context_dependent("这场战役的意义是什么")


def test_only_out_of_scope_years_still_reach_the_planner() -> None:
    settings = _settings()
    assert should_plan_query(
        settings, QuestionRequest(question="辛亥革命1911年发生了什么")
    )
    assert not should_plan_query(
        settings, QuestionRequest(question="辛亥革命1927年发生了什么")
    )


def test_gate_can_be_disabled_and_requires_a_configured_model() -> None:
    assert should_plan_query(
        _settings(llm_query_planning_gate=False),
        QuestionRequest(question="毛泽东在1949年的活动"),
    )
    assert not should_plan_query(
        Settings(_env_file=None, llm_api_key=None),
        QuestionRequest(question="毛泽东在1949年的活动"),
    )


def test_low_recall_is_counted_but_degraded_branches_are_not_rewritten() -> None:
    assert is_low_recall(_response([]))
    assert is_low_recall(_response([_hit("a", 1, page=1)]))
    assert not is_low_recall(
        _response([_hit(str(index), index, page=index) for index in range(1, 4)])
    )
    gapped = _response([_hit(str(index), index, page=index) for index in range(1, 4)]).model_copy(
        update={"coverage_gaps": ["1949年"]}
    )
    assert is_low_recall(gapped)
    degraded = _response([]).model_copy(update={"degraded_components": ["vector"]})
    assert not is_low_recall(degraded)


def test_late_rewrite_requires_a_skipped_planner_and_no_evidence_or_low_recall() -> None:
    settings = _settings()
    request = QuestionRequest(question="毛泽东在1949年的活动")
    low = _response([])
    assert should_rewrite_after_retrieval(
        settings,
        request,
        planner_skipped=True,
        retrieval=low,
        task_status="empty",
    )
    assert not should_rewrite_after_retrieval(
        settings,
        request,
        planner_skipped=False,
        retrieval=low,
        task_status="empty",
    )
    # Low recall still triggers even when the task produced some evidence.
    assert should_rewrite_after_retrieval(
        settings,
        request,
        planner_skipped=True,
        retrieval=low,
        task_status="completed",
    )
    sufficient = _response([_hit(str(index), index, page=index) for index in range(1, 4)])
    assert not should_rewrite_after_retrieval(
        settings,
        request,
        planner_skipped=True,
        retrieval=sufficient,
        task_status="completed",
    )
