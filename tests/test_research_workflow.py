"""Behavioral checks of the one research lifecycle, without model/network calls."""

from __future__ import annotations

import asyncio

import pytest
from history_agent.answering import llamaindex_workflow as workflow
from history_agent.answering.models import (
    Citation,
    QueryEntity,
    QueryPlan,
    QuestionRequest,
    ResearchTask,
    TaskResult,
)
from history_agent.answering.query_understanding import QueryPlanningResult
from history_agent.answering.retrieval_reflection import EvidenceAssessment, ReflectionResult
from history_agent.answering.runtime import RequestBudget
from history_agent.answering.service import answer_question
from history_agent.answering.streaming import stream_answer_question
from history_agent.config import Settings
from history_agent.errors import RetrievalError
from history_agent.retrieval.models import SearchResponse


def citation(page: int = 1) -> Citation:
    return Citation(
        evidence_id="E1",
        document_id="history",
        document="测试史料",
        pdf_page=page,
        section=[],
        quote=f"1935年，会议讨论了第{page}项工作。",
        source_type="official_history",
        verification_status="verified",
        extraction_methods=["text"],
        year_mentions=[1935],
    )


def task(key: str, tool: str = "search", depends: list[str] | None = None) -> ResearchTask:
    return ResearchTask(
        task_id=key,
        tool=tool,
        objective=f"核查{key}证据",
        query="会议经过",
        depends_on=depends or [],
    )


def install(monkeypatch, plan: QueryPlan, execute) -> None:
    monkeypatch.setattr(workflow, "plan_question", lambda *args: QueryPlanningResult(plan, "used"))
    monkeypatch.setattr(workflow.HistoryTaskExecutor, "execute", execute)
    monkeypatch.setattr(workflow, "assess_retrieval", lambda *args: ReflectionResult("skipped"))


def collect(executor, item: ResearchTask, page: int) -> TaskResult:
    evidence = executor.registry.register_citation(citation(page), item.task_id, f"page-{page}")
    return TaskResult(
        task_id=item.task_id,
        tool=item.tool,
        status="completed",
        evidence_ids=[evidence.evidence_id],
    )


def test_simple_question_has_one_task_and_one_shared_delivery(monkeypatch, work_path) -> None:
    calls = []

    async def execute(executor, item, prior):
        calls.append(item.task_id)
        return collect(executor, item, 1)

    install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
    settings = Settings(_env_file=None, project_root=work_path)
    result = answer_question(settings, QuestionRequest(question="会议经过"))
    assert len(calls) == 1
    assert result.rag_framework == "llamaindex"
    assert result.execution_summary.stopped_reason == "completed"
    assert result.execution_summary.replan_count == 0
    assert result.generator_mode == "extractive"
    assert "[E1]" in result.answer


def test_complex_tasks_wait_for_dependencies_and_share_evidence_ids(monkeypatch, work_path) -> None:
    order = []

    async def execute(executor, item, prior):
        order.append(item.task_id)
        if item.tool == "analyze":
            assert {result.task_id for result in prior} == {"first", "second"}
            return TaskResult(
                task_id=item.task_id,
                tool="analyze",
                status="completed",
                evidence_ids=["E1", "E2"],
                findings=["两份材料分别说明工作。[E1][E2]"],
            )
        return collect(executor, item, 1 if item.task_id == "first" else 2)

    plan = QueryPlan(
        normalized_question="会议经过",
        tasks=[
            task("first"),
            task("second"),
            task("compare", "analyze", ["first", "second"]),
        ],
    )
    install(monkeypatch, plan, execute)
    result = answer_question(
        Settings(_env_file=None, project_root=work_path), QuestionRequest(question="会议经过")
    )
    assert order[-1] == "compare"
    assert len(result.citations) == 2
    assert {item.evidence_id for item in result.citations} == {"E1", "E2"}
    assert len(result.execution_summary.task_results) == 3


def test_replanning_is_bounded_and_rechecks_supplementary_evidence(monkeypatch, work_path) -> None:
    calls = []

    async def execute(executor, item, prior):
        calls.append(item.task_id)
        result = collect(executor, item, len(calls))
        result.retrieval = SearchResponse(
            query=item.query,
            query_intent="event_overview",
            query_terms=[],
            query_years=[],
            query_year_range=[],
            query_people=[],
            document_filters=[],
            include_out_of_scope=False,
            hits=[],
        )
        return result

    install(
        monkeypatch, QueryPlan(normalized_question="会议经过", intent="event_overview"), execute
    )
    monkeypatch.setattr(
        workflow,
        "assess_retrieval",
        lambda *args: ReflectionResult(
            "retry",
            EvidenceAssessment(
                sufficient=False, missing_aspects=["会议结果"], reason="缺少结果材料"
            ),
            ("会议结果",),
        ),
    )
    result = answer_question(
        Settings(_env_file=None, project_root=work_path), QuestionRequest(question="会议经过")
    )
    assert len(calls) == 3
    assert result.execution_summary.replan_count == 2
    assert result.execution_summary.stopped_reason == "insufficient_evidence"
    assert result.evidence_status == "partial"
    assert "会议结果" in "".join(result.limitations)


def test_missing_structured_records_become_a_task_in_the_same_plan(monkeypatch, work_path) -> None:
    async def execute(executor, item, prior):
        if item.tool == "timeline":
            return TaskResult(
                task_id=item.task_id, tool=item.tool, status="empty", missing_aspects=["人物活动"]
            )
        return collect(executor, item, 1)

    plan = QueryPlan(
        normalized_question="周恩来1935年活动",
        intent="timeline",
        retrieval_route="structured",
        entities=[QueryEntity(type="person", text="周恩来", canonical="周恩来")],
        start_year=1935,
        end_year=1935,
        tasks=[
            task("timeline", "timeline").model_copy(
                update={
                    "person_names": ["周恩来"],
                    "start_year": 1935,
                    "end_year": 1935,
                }
            )
        ],
    )
    install(monkeypatch, plan, execute)
    result = answer_question(
        Settings(_env_file=None, project_root=work_path),
        QuestionRequest(question="周恩来1935年活动"),
    )
    assert [item.tool for item in result.execution_summary.task_results] == ["timeline", "search"]
    assert result.execution_summary.replan_count == 1
    assert result.execution_summary.stopped_reason == "completed"


def test_services_unavailable_are_not_reported_as_no_evidence(monkeypatch, work_path) -> None:
    calls = []

    async def execute(executor, item, prior):
        calls.append(item.task_id)
        return TaskResult(task_id=item.task_id, tool=item.tool, status="unavailable")

    install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
    with pytest.raises(RetrievalError):
        answer_question(
            Settings(_env_file=None, project_root=work_path), QuestionRequest(question="会议经过")
        )
    assert len(calls) == 2


def test_expired_budget_does_not_start_tools(monkeypatch, work_path) -> None:
    async def execute(*args):
        raise AssertionError("Expired requests cannot start tools")

    install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
    result = answer_question(
        Settings(_env_file=None, project_root=work_path),
        QuestionRequest(question="会议经过"),
        budget=RequestBudget.start(-1),
    )
    assert result.execution_summary.stopped_reason == "budget_exhausted"
    assert all(item.status == "skipped" for item in result.execution_summary.task_results)


def test_sse_and_json_use_same_final_answer_and_task_contract(monkeypatch, work_path) -> None:
    async def execute(executor, item, prior):
        return collect(executor, item, 1)

    install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
    settings = Settings(_env_file=None, project_root=work_path)
    request = QuestionRequest(question="会议经过")
    result = answer_question(settings, request)

    async def stream():
        return [event async for event in stream_answer_question(settings, request)]

    events = asyncio.run(stream())
    assert sum(event.event == "done" for event in events) == 1
    final = events[-1].data
    assert final["answer"] == result.answer
    assert final["citations"] == [item.model_dump() for item in result.citations]
    assert final["execution_summary"]["plan"] == result.execution_summary.plan.model_dump()


def test_full_source_is_not_truncated_to_research_top_k(monkeypatch, work_path) -> None:
    async def execute(executor, item, prior):
        ids = [collect(executor, item, page).evidence_ids[0] for page in range(1, 41)]
        return TaskResult(
            task_id=item.task_id,
            tool=item.tool,
            status="completed",
            evidence_ids=ids,
            content="完整原文最后一页。",
        )

    install(
        monkeypatch,
        QueryPlan(
            normalized_question="给出全文",
            tasks=[
                task("original", "read_source"),
            ],
        ),
        execute,
    )
    result = answer_question(
        Settings(_env_file=None, project_root=work_path), QuestionRequest(question="给出全文")
    )
    assert len(result.citations) == 40
    assert "完整原文最后一页" in result.answer
    assert result.llm_status == "not_applicable"


def test_analysis_gaps_replan_then_analyze_combined_original_evidence(monkeypatch, work_path):
    seen = []

    async def execute(executor, item, prior):
        seen.append(item.tool)
        if item.tool == "search":
            return collect(executor, item, len(seen))
        dependency = next(result for result in prior if result.task_id == item.depends_on[0])
        if item.task_id == "compare":
            return TaskResult(
                task_id=item.task_id,
                tool="analyze",
                status="completed",
                evidence_ids=dependency.evidence_ids,
                findings=["初步事实。[E1]"],
                missing_aspects=["会后职责"],
            )
        assert dependency.evidence_ids == ["E1", "E2"]
        return TaskResult(
            task_id=item.task_id,
            tool="analyze",
            status="completed",
            evidence_ids=dependency.evidence_ids,
            findings=["补足证据后的比较。[E1][E2]"],
        )

    plan = QueryPlan(
        normalized_question="会议经过",
        tasks=[
            task("first"),
            task("compare", "analyze", ["first"]),
        ],
    )
    install(monkeypatch, plan, execute)
    result = answer_question(
        Settings(_env_file=None, project_root=work_path), QuestionRequest(question="会议经过")
    )
    assert seen == ["search", "analyze", "search", "analyze"]
    assert result.execution_summary.replan_count == 1
    assert result.execution_summary.stopped_reason == "completed"
    assert len(result.citations) == 2
    assert result.research_plan.tasks[1].depends_on == ["first"]


def test_cancel_stream_cancels_current_task_and_never_delivers_done(monkeypatch, work_path):
    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        budget = RequestBudget.start(10)

        async def execute(executor, item, prior):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
        events = []

        async def consume():
            async for event in stream_answer_question(
                Settings(_env_file=None, project_root=work_path),
                QuestionRequest(question="会议经过"),
                budget=budget,
            ):
                events.append(event)

        consumer = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), 2)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        await asyncio.wait_for(cancelled.wait(), 2)
        assert budget.cancelled
        assert all(event.event != "done" for event in events)

    asyncio.run(scenario())


def test_exhausted_model_budget_is_visible_even_when_planner_falls_back(monkeypatch, work_path):
    import httpx

    budget = RequestBudget.start(10)
    budget.max_llm_calls = 0

    def planning(settings, request, runtime, shared_budget):
        try:
            shared_budget.consume_call()
        except httpx.TimeoutException:
            return QueryPlanningResult(None, "fallback", error_code="request_timeout")
        raise AssertionError("The exhausted budget must refuse the model call")

    async def execute(executor, item, prior):
        return collect(executor, item, 1)

    install(monkeypatch, QueryPlan(normalized_question="会议经过"), execute)
    monkeypatch.setattr(workflow, "plan_question", planning)
    result = answer_question(
        Settings(_env_file=None, project_root=work_path),
        QuestionRequest(question="会议经过"),
        budget=budget,
    )
    assert result.execution_summary.stopped_reason == "budget_exhausted"
    assert result.evidence_status == "partial"
    assert result.citations
