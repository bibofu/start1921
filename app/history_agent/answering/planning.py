"""Compile and validate the single executable research plan without model calls."""

from __future__ import annotations

import re
from pathlib import Path

from history_agent.answering.models import QueryEntity, QueryPlan, ResearchPlan, ResearchTask
from history_agent.errors import ExtractionError
from history_agent.processing.chunks import extract_people, load_person_aliases
from history_agent.retrieval.keyword_common import infer_query_intent

QUOTED_TITLE = re.compile(r"《(?P<title>[^》\n]{1,160})》")
FULL_TEXT_MARKER = re.compile(r"全文|完整(?:原文|内容|文本)|原文全文")
SOURCE_LIMIT = re.compile(
    r"(?:只|仅)(?:能|可)?(?:依据|根据|使用|参考|基于|查阅|限于)|限定(?:来源|文献)"
)
YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
YEAR_INTERVAL = re.compile(
    r"(?P<start>(?:18|19|20)\d{2})年?\s*(?:至|到|—|–|-|~|～)\s*"
    r"(?P<end>(?:18|19|20)\d{2})年?"
)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).strip("《》")


def _literal_years(question: str) -> tuple[int | None, int | None]:
    """Never turn a book's publication range into the event's date constraint."""
    without_titles = QUOTED_TITLE.sub("", question)
    interval = YEAR_INTERVAL.search(without_titles)
    if interval is not None:
        start, end = int(interval["start"]), int(interval["end"])
        return (start, end) if start <= end else (None, None)
    years = sorted({int(match.group()) for match in YEAR.finditer(without_titles)})
    if len(years) == 1 and not re.search(r"之前|以前|之后|以后|前|后", without_titles):
        return years[0], years[0]
    return None, None


def _source_titles(question: str) -> list[str]:
    return list(dict.fromkeys(match["title"] for match in QUOTED_TITLE.finditer(question)))


def _constrained_source(question: str) -> str | None:
    titles = _source_titles(question)
    if len(titles) == 1 and SOURCE_LIMIT.search(question):
        return titles[0]
    return None


def _fallback_interpretation(question: str, aliases_path: Path | None) -> QueryPlan:
    start, end = _literal_years(question)
    try:
        aliases = load_person_aliases(aliases_path) if aliases_path is not None else {}
    except ExtractionError:
        aliases = {}
    people = extract_people(question, aliases)
    intent = infer_query_intent(question)
    # The shared domain parser proposes intent and people. A narrow grammar
    # proves there are no extra month, place, source or negative constraints
    # before compiling a structured task while the LLM is unavailable.
    remaining = re.sub(r"[\s，,。！？?!；;、]", "", question)
    for canonical in people:
        for form in sorted([canonical, *aliases.get(canonical, [])], key=len, reverse=True):
            remaining = remaining.replace(form, "")
    remaining = YEAR_INTERVAL.sub("", remaining)
    remaining = YEAR.sub("", remaining)
    remaining = re.sub(
        r"详细介绍|按时间顺序|做了什么|主要做|有哪些|时间线|共同活动|共同经历|"
        r"请列出|请介绍|请梳理|期间|主要|经历|活动|任职|担任|职务|交集|共同|一起|"
        r"列出|介绍|梳理|情况|记录|清单|以及|分别|请|的|在|从|年|和|与", "", remaining,
    )
    structured = (
        intent in {"timeline", "intersection"} and not remaining
        and start is not None and end is not None
        and len(people) == (2 if intent == "intersection" else 1)
    )
    return QueryPlan.model_validate({
        "normalized_question": question, "start_year": start, "end_year": end,
        "intent": intent, "retrieval_route": "structured" if structured else "hybrid",
        "entities": [QueryEntity(type="person", text=name, canonical=name) for name in people],
    })


def _default_task(question: str, interpretation: QueryPlan) -> ResearchTask:
    titles = _source_titles(question)
    people = list(dict.fromkeys(
        entity.canonical for entity in interpretation.entities if entity.type == "person"
    ))
    tool: str = "search"
    source_title = _constrained_source(question)
    if titles and FULL_TEXT_MARKER.search(question):
        tool, source_title = "read_source", titles[0]
    elif interpretation.retrieval_route == "structured":
        expected = 2 if interpretation.intent == "intersection" else 1
        if (
            interpretation.intent in {"timeline", "intersection"}
            and interpretation.start_year is not None
            and interpretation.end_year is not None
            and len(people) == expected
        ):
            tool = interpretation.intent
    return ResearchTask.model_validate({
        "task_id": "task_1", "tool": tool,
        "objective": interpretation.normalized_question,
        "query": question, "person_names": people,
        "start_year": interpretation.start_year, "end_year": interpretation.end_year,
        "source_title": source_title, "coverage": interpretation.coverage,
        "required_aspects": interpretation.constraints,
    })


def _inherit_constraints(
    task: ResearchTask, question: str, interpretation: QueryPlan,
) -> ResearchTask:
    updates: dict[str, object] = {}
    if "coverage" not in task.model_fields_set:
        updates["coverage"] = interpretation.coverage
    if "required_aspects" not in task.model_fields_set:
        updates["required_aspects"] = interpretation.constraints
    if task.start_year is None and interpretation.start_year is not None:
        updates.update(start_year=interpretation.start_year, end_year=interpretation.end_year)
    scope = (
        interpretation.normalized_question if interpretation.context_message_indices else question
    )
    source = _constrained_source(question) or _constrained_source(scope)
    if source is not None and task.source_title is None and task.tool != "analyze":
        updates["source_title"] = source
    # Execute one complete scope, not a mixture of an unresolved follow-up and
    # its resolution. Keep the original wording on ResearchPlan for auditing.
    query = task.query
    if scope not in query:
        suffix = f"\n问题及约束：{scope}"
        query = query[: 1000 - len(suffix)] + suffix
    updates["query"] = query
    return ResearchTask.model_validate({**task.model_dump(), **updates})


def compile_research_plan(
    question: str, interpretation: QueryPlan | None,
    aliases_path: Path | None = None,
) -> ResearchPlan:
    """Compile model-produced tasks or a deterministic single-task fallback.

    Model-off fallback reuses the local alias catalog and query intent parser;
    the evidence tool resolves every structured identity again against the DB.
    """
    semantic = interpretation or _fallback_interpretation(question, aliases_path)
    raw_tasks = semantic.tasks
    semantic = semantic.model_copy(update={"tasks": []})
    terminal = semantic.intent == "out_of_scope" or semantic.needs_clarification
    scope = semantic.normalized_question if semantic.context_message_indices else question
    tasks = [] if terminal else raw_tasks or [_default_task(scope, semantic)]
    tasks = [_inherit_constraints(task, question, semantic) for task in tasks]
    return validate_research_plan(
        ResearchPlan(question=question, interpretation=semantic, tasks=tasks)
    )


def validate_research_plan(
    plan: ResearchPlan, previous: ResearchPlan | None = None,
    *, completed_task_ids: set[str] | None = None,
) -> ResearchPlan:
    """Enforce graph, scope, and immutable user constraints before execution."""
    plan = ResearchPlan.model_validate(plan.model_dump())
    semantic = plan.interpretation
    allowed_people = {
        _compact(name)
        for entity in semantic.entities if entity.type == "person"
        for name in (entity.text, entity.canonical)
    }
    scope = semantic.normalized_question if semantic.context_message_indices else plan.question
    named_titles = {_compact(title) for title in _source_titles(plan.question + scope)}
    required_source = _constrained_source(plan.question) or _constrained_source(scope)
    for task in plan.tasks:
        if scope not in task.query:
            raise ValueError("Task queries must preserve the resolved question and constraints")
        if semantic.start_year is not None and semantic.end_year is not None:
            if (
                task.start_year is None or task.end_year is None
                or task.start_year < semantic.start_year or task.end_year > semantic.end_year
            ):
                raise ValueError("Task dates cannot relax the research plan's time constraint")
        elif task.start_year is not None:
            raise ValueError("Tasks cannot invent a time constraint absent from the interpretation")
        if any(_compact(person) not in allowed_people for person in task.person_names):
            raise ValueError("Task people must be grounded in the validated interpretation")
        if task.source_title is not None and _compact(task.source_title) not in named_titles:
            raise ValueError("Task source titles must be explicitly named in the question")
        if (
            required_source and task.tool != "analyze"
            and _compact(task.source_title or "") != _compact(required_source)
        ):
            raise ValueError("Tasks cannot change the user's exclusive source constraint")
        if task.document_ids and previous is None:
            raise ValueError("Initial plans cannot invent document IDs; tools resolve titles")
        if task.tool in {"timeline", "intersection"}:
            if semantic.retrieval_route != "structured":
                raise ValueError("Structured tasks cannot override hybrid-only user constraints")
            expected = 2 if task.tool == "intersection" else 1
            if (
                len(set(task.person_names)) != expected
                or task.start_year is None or task.end_year is None
            ):
                raise ValueError("Structured tasks require the exact person count and year range")
    if previous is not None:
        if plan.question != previous.question:
            raise ValueError("Replanning cannot change the user's question")
        if semantic.model_dump() != previous.interpretation.model_dump():
            raise ValueError("Replanning cannot change the validated user interpretation")
        if plan.max_replans != previous.max_replans or plan.revision != previous.revision + 1:
            raise ValueError("Replanning must advance once within the original replan budget")
        previous_tasks = {task.task_id: task for task in previous.tasks}
        current_tasks = {task.task_id: task for task in plan.tasks}
        for key, task in previous_tasks.items():
            current = current_tasks.get(key)
            if current == task:
                continue
            can_redirect = (
                current is not None and completed_task_ids is not None
                and key not in completed_task_ids and task.tool == "analyze"
                and current.model_dump(exclude={"depends_on"})
                == task.model_dump(exclude={"depends_on"})
            )
            if not can_redirect or current is None:
                raise ValueError("Replanning cannot alter existing task work or completed tasks")
            # A pending analysis may wait for supplemental evidence, but cannot
            # discard an original evidence branch. The replacement must depend
            # on that branch itself, preserving its evidence ancestry.
            ancestry = set(current.depends_on)
            pending = list(ancestry)
            while pending:
                for dependency in current_tasks[pending.pop()].depends_on:
                    if dependency not in ancestry:
                        ancestry.add(dependency)
                        pending.append(dependency)
            if not set(task.depends_on) <= ancestry:
                raise ValueError("Pending analysis cannot discard its original evidence branches")
        allowed_documents = {
            document for task in previous.tasks for document in task.document_ids
        }
        if any(set(task.document_ids) - allowed_documents for task in plan.tasks):
            raise ValueError("Replanning cannot introduce unverified document IDs")
    return plan


def extend_research_plan(
    previous: ResearchPlan, tasks: list[ResearchTask],
    *, completed_task_ids: set[str] | None = None,
    redirect_pending_dependencies: dict[str, str] | None = None,
) -> ResearchPlan:
    """Append validated work while keeping prior task identity and scope immutable."""
    if not tasks:
        raise ValueError("A revised plan must add at least one new task")
    additions = [
        _inherit_constraints(task, previous.question, previous.interpretation) for task in tasks
    ]
    redirects = redirect_pending_dependencies or {}
    if redirects and completed_task_ids is None:
        raise ValueError("Dependency redirection requires the completed task IDs")
    existing = [
        task.model_copy(update={"depends_on": list(dict.fromkeys(
            redirects.get(dependency, dependency) for dependency in task.depends_on
        ))})
        if task.tool == "analyze" and task.task_id not in (completed_task_ids or set())
        else task
        for task in previous.tasks
    ]
    revised = previous.model_copy(update={
        "tasks": [*existing, *additions], "revision": previous.revision + 1,
    })
    return validate_research_plan(revised, previous, completed_task_ids=completed_task_ids)
