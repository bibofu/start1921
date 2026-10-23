"""The single Plan-and-Execute lifecycle for every question and transport."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypeVar
from uuid import uuid4

import httpx
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from workflows.handler import WorkflowHandler

from history_agent.answering.delivery import deliver_answer
from history_agent.answering.evidence import EvidenceRegistry
from history_agent.answering.models import (
    AnswerResponse,
    ExecutionSummary,
    QuestionRequest,
    ResearchPlan,
    ResearchTask,
    TaskResult,
)
from history_agent.answering.planning import compile_research_plan, extend_research_plan
from history_agent.answering.query_understanding import QueryPlanningResult, plan_question
from history_agent.answering.retrieval_reflection import assess_retrieval
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.synthesis import HistoryResponseSynthesizer, LLMResult
from history_agent.answering.task_executor import HistoryTaskExecutor
from history_agent.config import Settings
from history_agent.errors import RetrievalError

T = TypeVar("T")


class ResearchStartEvent(StartEvent):
    request: QuestionRequest


class ProgressEvent(Event):
    event: Literal["status", "delta", "reset", "done", "error"] = "status"
    data: dict[str, Any]


class DispatchEvent(Event):
    pass


class ReviewEvent(Event):
    task_ids: list[str]


class SynthesisEvent(Event):
    pass


class RepairEvent(Event):
    pass


class FinishEvent(Event):
    pass


class HistoryResearchWorkflow(Workflow):
    """One request-local scheduler; tools and synthesizers cannot replan themselves."""

    def __init__(
        self,
        settings: Settings,
        runtime: LLMRuntime | None = None,
        budget: RequestBudget | None = None,
    ) -> None:
        # Await deadlines leave room for deterministic partial-result delivery.
        super().__init__(timeout=None, workflow_name="history-plan-and-execute")
        self.settings, self._llm_runtime = settings, runtime
        self.budget = budget or RequestBudget.start(settings.request_timeout_seconds)
        self.run_id = str(uuid4())
        self.registry = EvidenceRegistry()
        self.results: dict[str, TaskResult] = {}
        self.supplements: dict[str, str] = {}
        self.usage: dict[str, dict[str, int]] = {}
        self.retrieval_calls = 0
        self.stop_reason: Literal[
            "completed",
            "budget_exhausted",
            "insufficient_evidence",
            "clarification",
            "out_of_scope",
            "failed",
            "cancelled",
        ] = "completed"
        self.llm_result = LLMResult(answer=None)
        self.selected_ids: list[str] = []
        self.request: QuestionRequest
        self.plan: ResearchPlan
        self.planning: QueryPlanningResult
        self.executor: HistoryTaskExecutor
        self.synthesizer = HistoryResponseSynthesizer(settings, runtime, self.budget)

    async def bounded(self, operation: Awaitable[T]) -> T:
        return await asyncio.wait_for(operation, timeout=max(0.001, self.budget.remaining))

    def record_usage(self, stage: str, usage: dict[str, int] | None) -> None:
        if usage:
            total = self.usage.setdefault(stage, {})
            for key, value in usage.items():
                total[key] = total.get(key, 0) + value

    def progress(self, ctx: Context, message: str, **details: Any) -> None:
        ctx.write_event_to_stream(ProgressEvent(data={"message": message, **details}))

    async def snapshot(self, ctx: Context) -> None:
        await ctx.store.set("research_plan", self.plan.model_dump(mode="json"))
        await ctx.store.set(
            "task_results",
            {key: result.model_dump(mode="json") for key, result in self.results.items()},
        )

    @step
    async def make_plan(self, ctx: Context, ev: ResearchStartEvent) -> DispatchEvent | FinishEvent:
        self.request = ev.request
        self.progress(ctx, "正在理解问题并安排研究任务…")
        try:
            self.planning = await self.bounded(
                asyncio.to_thread(
                    plan_question,
                    self.settings,
                    self.request,
                    self._llm_runtime,
                    self.budget,
                )
            )
        except (TimeoutError, httpx.TimeoutException):
            self.planning = QueryPlanningResult(None, "fallback", error_code="request_timeout")
            self.stop_reason = "budget_exhausted"
        self.record_usage("planning", self.planning.usage)
        self.plan = self.planning.research_plan or compile_research_plan(
            self.request.question,
            self.planning.plan,
            self.settings.person_aliases_path,
        )
        self.executor = HistoryTaskExecutor(
            self.settings,
            self.request,
            self.registry,
            self._llm_runtime,
            self.budget,
            interpretation=self.plan.interpretation,
        )
        await self.snapshot(ctx)
        if self.plan.interpretation.intent == "out_of_scope":
            self.stop_reason = "out_of_scope"
            return FinishEvent()
        if self.plan.interpretation.needs_clarification:
            self.stop_reason = "clarification"
            return FinishEvent()
        self.progress(
            ctx,
            f"已安排 {len(self.plan.tasks)} 项任务。",
            tasks=[{"id": task.task_id, "objective": task.objective} for task in self.plan.tasks],
        )
        return DispatchEvent()

    async def execute_one(self, task: ResearchTask) -> TaskResult:
        for attempt in range(2):
            try:
                self.budget.timeout(float("inf"))
                result = await self.bounded(
                    self.executor.execute(task, list(self.results.values()))
                )
            except (TimeoutError, httpx.TimeoutException):
                self.stop_reason = "budget_exhausted"
                return TaskResult(
                    task_id=task.task_id,
                    tool=task.tool,
                    status="unavailable",
                    error_code="request_timeout",
                    missing_aspects=task.required_aspects,
                )
            except RetrievalError:
                result = TaskResult(
                    task_id=task.task_id,
                    tool=task.tool,
                    status="unavailable",
                    error_code="retrieval_unavailable",
                )
            if task.tool == "search":
                self.retrieval_calls += 1
            self.record_usage("analysis" if task.tool == "analyze" else "tools", result.usage)
            if result.status != "unavailable" or attempt or self.budget.remaining <= 1:
                return result
        raise AssertionError("unreachable")

    @step
    async def dispatch(self, ctx: Context, ev: DispatchEvent) -> ReviewEvent | SynthesisEvent:
        del ev
        if self.budget.remaining <= 0 or self.stop_reason == "budget_exhausted":
            self.stop_reason = "budget_exhausted"
            return SynthesisEvent()
        pending = [task for task in self.plan.tasks if task.task_id not in self.results]
        if not pending:
            return SynthesisEvent()
        ready = [task for task in pending if all(dep in self.results for dep in task.depends_on)]
        if not ready:
            raise RuntimeError("Validated research plan has unsatisfied task dependencies")
        evidence_tasks = [task for task in ready if task.tool != "analyze"]
        ready = (evidence_tasks or ready)[:2]
        for task in ready:
            self.progress(ctx, task.objective, task_id=task.task_id, phase="executing")
        outputs = await asyncio.gather(*(self.execute_one(task) for task in ready))
        for result in outputs:
            if result.task_id in self.supplements.values():
                task = next(item for item in ready if item.task_id == result.task_id)
                # Analysis redirected to a supplement must retain the ancestor
                # evidence as well as the newly retrieved pages.
                ancestor_ids = [
                    evidence_id
                    for dependency in task.depends_on
                    for evidence_id in self.results[dependency].evidence_ids
                ]
                result.evidence_ids = list(dict.fromkeys([*ancestor_ids, *result.evidence_ids]))
            self.results[result.task_id] = result
            self.progress(
                ctx,
                "任务已返回，正在检查证据。",
                task_id=result.task_id,
                task_status=result.status,
                evidence_count=len(result.evidence_ids),
            )
        await self.snapshot(ctx)
        return ReviewEvent(task_ids=[task.task_id for task in ready])

    def add_supplements(self, additions: list[tuple[ResearchTask, ResearchTask]]) -> bool:
        if not additions or self.plan.revision >= self.plan.max_replans:
            return False
        tasks: list[ResearchTask] = []
        redirects: dict[str, str] = {}
        supplements: dict[str, str] = {}
        for old, new in additions:
            needed = 2 if old.tool == "analyze" else 1
            if len(self.plan.tasks) + len(tasks) + needed > 8:
                continue
            tasks.append(new)
            supplements[old.task_id] = new.task_id
            redirects[old.task_id] = new.task_id
            if old.tool == "analyze":
                # Keep completed analysis immutable. Revisit it as a new task
                # after collecting the missing evidence, in this same plan.
                reassess = old.model_copy(
                    update={
                        "task_id": f"reanalyze_{self.plan.revision + 1}_{len(tasks)}",
                        "depends_on": [new.task_id],
                    }
                )
                tasks.append(reassess)
                redirects[old.task_id] = reassess.task_id
        if not tasks:
            return False
        self.plan = extend_research_plan(
            self.plan,
            tasks,
            completed_task_ids=set(self.results),
            redirect_pending_dependencies=redirects,
        )
        self.supplements.update(supplements)
        return True

    @step
    async def review(self, ctx: Context, ev: ReviewEvent) -> DispatchEvent | SynthesisEvent:
        additions: list[tuple[ResearchTask, ResearchTask]] = []
        for task_id in ev.task_ids:
            task = next(task for task in self.plan.tasks if task.task_id == task_id)
            result = self.results[task_id]
            if result.status == "ambiguous":
                self.stop_reason = "clarification"
                return SynthesisEvent()
            query: str | None = None
            missing = list(result.missing_aspects)
            if task.tool == "timeline" and result.status in {
                "empty",
                "not_applicable",
            }:
                query = task.query
                missing = missing or task.required_aspects or [task.objective[:120]]
            elif task.tool == "analyze" and result.status in {"completed", "empty"} and missing:
                query = task.query + "；待核查：" + "；".join(missing)
            elif task.tool == "search" and result.retrieval is not None:
                interpretation = self.plan.interpretation.model_copy(
                    update={
                        "normalized_question": task.query[:500],
                        "coverage": task.coverage,
                        "start_year": task.start_year,
                        "end_year": task.end_year,
                    }
                )
                try:
                    assessment = await self.bounded(
                        asyncio.to_thread(
                            assess_retrieval,
                            self.settings,
                            self.request.model_copy(update={"question": task.query[:500]}),
                            interpretation,
                            result.retrieval,
                            self._llm_runtime,
                            self.budget,
                        )
                    )
                    self.record_usage("assessment", assessment.usage)
                    if assessment.assessment is not None:
                        missing = (
                            []
                            if assessment.assessment.sufficient
                            else list(assessment.assessment.missing_aspects)
                        )
                    if assessment.status == "retry":
                        query = "；".join(assessment.followup_queries)
                    elif assessment.status == "fallback":
                        result.limitations.append("部分证据覆盖未能完成模型核查。")
                except (TimeoutError, httpx.TimeoutException):
                    self.stop_reason = "budget_exhausted"
                result.missing_aspects = missing
            if query and self.budget.remaining > 1:
                supplement = task.model_copy(
                    update={
                        "task_id": f"supplement_{self.plan.revision + 1}_{len(additions) + 1}",
                        "tool": "search",
                        "objective": ("补充证据：" + "、".join(missing))[:500],
                        "query": query[:1000],
                        "depends_on": [task_id],
                        "required_aspects": list(
                            dict.fromkeys(aspect[:120] for aspect in missing if aspect.strip())
                        )[:12],
                    }
                )
                additions.append((task, supplement))
        if self.add_supplements(additions):
            self.progress(
                ctx, "已更新未完成任务，针对证据缺口继续检索。", plan_revision=self.plan.revision
            )
        await self.snapshot(ctx)
        if self.stop_reason == "budget_exhausted":
            return SynthesisEvent()
        return DispatchEvent()

    def unresolved(self) -> list[TaskResult]:
        return [
            result
            for key, result in self.results.items()
            if key not in self.supplements
            and (result.status != "completed" or result.missing_aspects)
        ]

    def select_evidence(self) -> list[str]:
        # Scores from different queries are not comparable. Reserve evidence per
        # task before filling the remaining context budget.
        groups = [
            list(result.evidence_ids) for result in self.results.values() if result.evidence_ids
        ]
        if len(self.plan.tasks) == 1 and self.plan.tasks[0].tool == "read_source":
            return list(dict.fromkeys(item for group in groups for item in group))
        selected: list[str] = []
        for index in range(max((len(group) for group in groups), default=0)):
            for group in groups:
                if index < len(group) and group[index] not in selected:
                    selected.append(group[index])
                    if len(selected) >= 36:
                        return selected
        return selected

    def sink(self, ctx: Context) -> Callable[[Any], None]:
        def emit(event: Any) -> None:
            ctx.write_event_to_stream(ProgressEvent(event=event.event, data=event.data))

        return emit

    @step
    async def synthesize(self, ctx: Context, ev: SynthesisEvent) -> RepairEvent | FinishEvent:
        del ev
        self.selected_ids = self.select_evidence()
        if self.stop_reason == "completed" and self.unresolved():
            self.stop_reason = "insufficient_evidence"
        if not self.selected_ids:
            unavailable = any(result.status == "unavailable" for result in self.results.values())
            if unavailable and self.stop_reason != "budget_exhausted":
                raise RetrievalError("Required local evidence services are unavailable.")
            return FinishEvent()
        if self.stop_reason == "clarification" or (
            len(self.plan.tasks) == 1 and self.plan.tasks[0].tool == "read_source"
        ):
            return FinishEvent()
        if not self.settings.llm_enabled or self.budget.remaining <= 0:
            return FinishEvent()
        self.progress(ctx, "正在综合任务证据并核查引用…")
        findings = [
            finding
            for task_id, result in self.results.items()
            if task_id not in self.supplements
            for finding in result.findings
        ]
        try:
            await self.bounded(
                self.synthesizer.asynthesize(
                    self.request.question,
                    self.registry.nodes(self.selected_ids),
                    request=self.request,
                    citations=self.registry.citations(self.selected_ids),
                    event_sink=self.sink(ctx),
                    findings=findings,
                )
            )
            self.llm_result = self.synthesizer.last_result
        except (TimeoutError, httpx.TimeoutException):
            self.stop_reason = "budget_exhausted"
            self.llm_result = LLMResult(answer=None, error_code="request_timeout")
        if getattr(self.llm_result, "repair_payload", None) and self.budget.remaining > 0:
            return RepairEvent()
        self.record_usage("synthesis", self.llm_result.usage)
        return FinishEvent()

    @step
    async def repair(self, ctx: Context, ev: RepairEvent) -> FinishEvent:
        del ev
        self.progress(ctx, "正在修复与证据不一致的引用或日期…")
        try:
            self.llm_result = await self.bounded(
                self.synthesizer.repair_once(
                    self.request,
                    self.registry.citations(self.selected_ids),
                    self.llm_result,
                    event_sink=self.sink(ctx),
                    nodes=self.registry.nodes(self.selected_ids),
                )
            )
        except (TimeoutError, httpx.TimeoutException):
            self.stop_reason = "budget_exhausted"
            self.llm_result = LLMResult(
                answer=None, error_code="request_timeout", usage=self.llm_result.usage
            )
        self.record_usage("synthesis", self.llm_result.usage)
        return FinishEvent()

    @step
    async def finish(self, ctx: Context, ev: FinishEvent) -> StopEvent:
        del ev
        if self.budget.llm_exhausted and self.stop_reason not in {"clarification", "out_of_scope"}:
            self.stop_reason = "budget_exhausted"
        for task in self.plan.tasks:
            if task.task_id not in self.results and self.stop_reason not in {
                "clarification",
                "out_of_scope",
            }:
                self.results[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    tool=task.tool,
                    status="skipped",
                    missing_aspects=task.required_aspects or [task.objective[:120]],
                    error_code=self.stop_reason,
                )
        summary = ExecutionSummary(
            run_id=self.run_id,
            plan=self.plan,
            task_results=list(self.results.values()),
            replan_count=self.plan.revision,
            usage_by_stage=self.usage,
            retrieval_calls=self.retrieval_calls,
            stopped_reason=self.stop_reason,
        )
        response = deliver_answer(
            self.settings,
            self.request,
            self.planning,
            summary,
            self.registry.citations(self.selected_ids),
            self.llm_result,
            unresolved=self.unresolved(),
        )
        await self.snapshot(ctx)
        return StopEvent(result=response)


def start_question(
    settings: Settings,
    request: QuestionRequest,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> tuple[HistoryResearchWorkflow, WorkflowHandler]:
    workflow = HistoryResearchWorkflow(settings, runtime, budget)
    handler = workflow.run(start_event=ResearchStartEvent(request=request))
    return workflow, handler


async def run_question(
    settings: Settings,
    request: QuestionRequest,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> AnswerResponse:
    workflow, handler = start_question(settings, request, runtime, budget)
    try:
        result = await handler
        if not isinstance(result, AnswerResponse):
            raise TypeError("Research workflow returned an invalid response")
        return result
    except asyncio.CancelledError:
        workflow.budget.cancel()
        await handler.cancel_run()
        raise
