from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from history_agent.retrieval.models import SearchResponse

MessageStatus = Literal["pending", "completed", "aborted", "failed"]


class ConversationMessage(BaseModel):
    message_id: int | None = Field(default=None, exclude=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=100_000)
    status: MessageStatus = Field(default="completed", exclude=True)
    created_at: str | None = Field(default=None, exclude=True)
    metadata: dict[str, Any] = Field(default_factory=dict, exclude=True)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=12, ge=1, le=12)
    history: list[ConversationMessage] = Field(default_factory=list, max_length=12)
    session_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    client_request_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class QueryEntity(BaseModel):
    type: Literal["person", "organization", "event", "place", "document", "other"]
    text: str = Field(min_length=1, max_length=80)
    canonical: str = Field(min_length=1, max_length=120)


ShortQueryText = Annotated[str, Field(min_length=1, max_length=180)]
ConstraintText = Annotated[str, Field(min_length=1, max_length=120)]
TaskTool = Literal["search", "timeline", "intersection", "read_source", "analyze"]
CoverageMode = Literal["relevance", "per_year", "per_item", "balanced_period"]


class ResearchTask(BaseModel):
    """A validated task; execution state belongs to TaskResult, never the planner."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    tool: TaskTool
    objective: str = Field(min_length=2, max_length=500)
    query: str = Field(min_length=2, max_length=1000)
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    person_names: list[str] = Field(default_factory=list, max_length=12)
    start_year: int | None = Field(default=None, ge=1800, le=2100)
    end_year: int | None = Field(default=None, ge=1800, le=2100)
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    source_title: str | None = Field(default=None, max_length=160)
    coverage: CoverageMode = "relevance"
    required_aspects: list[ConstraintText] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_year_range(self) -> ResearchTask:
        if (self.start_year is None) != (self.end_year is None):
            raise ValueError("Task years must be provided as a complete interval")
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year > self.end_year
        ):
            raise ValueError("Task start_year cannot exceed end_year")
        return self


class QueryPlan(BaseModel):
    """Validated semantic interpretation used to build a retrieval query."""

    intent: Literal[
        "general",
        "event_overview",
        "timeline",
        "intersection",
        "viewpoint",
        "observation",
        "comparison",
        "causal_analysis",
        "out_of_scope",
    ] = "general"
    retrieval_route: Literal["structured", "hybrid"] = "hybrid"
    normalized_question: str = Field(min_length=2, max_length=500)
    context_message_indices: list[Annotated[int, Field(ge=1)]] = Field(
        default_factory=list, max_length=50,
    )
    search_queries: list[ShortQueryText] = Field(default_factory=list, max_length=8)
    entities: list[QueryEntity] = Field(default_factory=list, max_length=12)
    start_year: int | None = Field(default=None, ge=1800, le=2100)
    end_year: int | None = Field(default=None, ge=1800, le=2100)
    coverage: CoverageMode = "relevance"
    constraints: list[ConstraintText] = Field(default_factory=list, max_length=12)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)
    tasks: list[ResearchTask] = Field(default_factory=list, max_length=8)


class ResearchPlan(BaseModel):
    """The only executable plan used by the research workflow."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=500)
    interpretation: QueryPlan
    tasks: list[ResearchTask] = Field(default_factory=list, max_length=8)
    revision: int = Field(default=0, ge=0, le=2)
    max_replans: int = Field(default=2, ge=0, le=2)

    @model_validator(mode="after")
    def validate_task_graph(self) -> ResearchPlan:
        if self.interpretation.tasks:
            raise ValueError("Only ResearchPlan.tasks may contain executable tasks")
        terminal = (
            self.interpretation.intent == "out_of_scope"
            or self.interpretation.needs_clarification
        )
        if not self.tasks and not terminal:
            raise ValueError("A nonterminal research plan needs at least one task")
        if terminal and self.tasks:
            raise ValueError("Clarification and out-of-scope plans cannot execute tasks")
        if self.revision > self.max_replans:
            raise ValueError("Research plan exceeds its replan budget")
        tasks = {task.task_id: task for task in self.tasks}
        if len(tasks) != len(self.tasks):
            raise ValueError("Task IDs must be unique")
        for task in self.tasks:
            if len(set(task.depends_on)) != len(task.depends_on):
                raise ValueError("Task dependencies must be unique")
            if task.task_id in task.depends_on or any(dep not in tasks for dep in task.depends_on):
                raise ValueError("Task dependencies must reference other tasks in this plan")
            if task.tool == "analyze" and not task.depends_on:
                raise ValueError("Analysis tasks require evidence-producing dependencies")
        remaining = set(tasks)
        completed: set[str] = set()
        while remaining:
            ready = {key for key in remaining if set(tasks[key].depends_on) <= completed}
            if not ready:
                raise ValueError("Research task dependencies contain a cycle")
            completed.update(ready)
            remaining.difference_update(ready)
        return self


class TaskResult(BaseModel):
    """Tool output referencing evidence held in the request's evidence registry."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    tool: TaskTool
    status: Literal[
        "completed", "empty", "unavailable", "not_applicable", "ambiguous", "failed", "skipped"
    ]
    evidence_ids: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    missing_aspects: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    content: str | None = None
    error_code: str | None = None
    retrieval: SearchResponse | None = None
    usage: dict[str, int] | None = None


class ExecutionSummary(BaseModel):
    """Auditable execution outcome shared by synchronous and streaming delivery."""

    run_id: str
    plan: ResearchPlan
    task_results: list[TaskResult] = Field(default_factory=list)
    replan_count: int = Field(default=0, ge=0, le=2)
    usage_by_stage: dict[str, dict[str, int]] = Field(default_factory=dict)
    retrieval_calls: int = Field(default=0, ge=0)
    stopped_reason: Literal[
        "completed", "budget_exhausted", "insufficient_evidence", "clarification",
        "out_of_scope", "failed", "cancelled"
    ] = "completed"


class Citation(BaseModel):
    evidence_id: str = Field(pattern=r"^E[1-9]\d*$")
    document_id: str
    document: str
    volume: str | None = None
    pdf_page: int = Field(ge=1)
    pdf_page_end: int | None = Field(default=None, ge=1)
    section: list[str]
    quote: str
    source_type: str
    verification_status: str
    extraction_methods: list[str]
    year_mentions: list[int] = Field(default_factory=list)
    # Structured indexes can carry an exact date even when the quoted prose
    # only contains the event description. Keep it separate from the quote so
    # date validation does not have to infer it from document text.
    event_date: str | None = None


class AnswerResponse(BaseModel):
    question: str
    answer: str
    evidence_status: Literal["supported", "partial", "no_evidence"]
    generator_mode: Literal["extractive", "llm"]
    llm_status: Literal["used", "disabled", "fallback", "not_applicable"]
    model_name: str | None = None
    llm_usage: dict[str, int] | None = None
    llm_error_code: str | None = None
    uncited_claims: list[str] = Field(default_factory=list)
    query_plan: QueryPlan | None = None
    research_plan: ResearchPlan | None = None
    execution_summary: ExecutionSummary | None = None
    query_planner_status: Literal["used", "disabled", "fallback", "not_applicable"] = (
        "not_applicable"
    )
    query_planner_model: str | None = None
    query_planner_usage: dict[str, int] | None = None
    query_planner_error_code: str | None = None
    retrieval_mode: str
    query_intent: str
    retrieval_reflection_status: Literal[
        "not_applicable", "disabled", "skipped", "sufficient", "retried", "fallback"
    ] = "not_applicable"
    retrieval_rounds: int = Field(default=1, ge=1, le=3)
    retrieval_missing_aspects: list[str] = Field(default_factory=list, max_length=4)
    retrieval_reflection_usage: dict[str, int] | None = None
    retrieval_reflection_error_code: str | None = None
    citations: list[Citation]
    retrieved_evidence_count: int = Field(default=0, ge=0)
    limitations: list[str] = Field(default_factory=list)
    rag_framework: Literal["native", "llamaindex"] = "native"
