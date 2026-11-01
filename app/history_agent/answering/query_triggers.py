"""Deterministic gates deciding when an LLM query rewrite is worth a call.

The planner is useful for conversational resolution, multi-aspect questions and
long-tail wording, but it is not needed before every local retrieval. These
gates keep the cheap deterministic path for simple self-contained questions and
reserve the model call for the cases that actually need it.
"""

from __future__ import annotations

import re

from history_agent.answering.models import QuestionRequest
from history_agent.config import Settings
from history_agent.retrieval.models import SearchResponse

COMPLEX_QUESTION = re.compile(
    r"详细|全面|系统|完整|经过|过程|前后|各阶段|主要经历|梳理|演变|变化|"
    r"原因|影响|意义|比较|异同"
)
# A standalone question that relies on an unstated antecedent needs the planner
# even without history so it can request clarification instead of retrieving on
# a guessed subject.
CONTEXT_DEPENDENT_QUESTION = re.compile(
    r"(?<!其)他(?:们)?|她(?:们)?|(?<!其)它(?:们)?|"
    r"这(?:场|次|位|些)|那(?:场|次|位|些)|"
    r"该(?:事件|人物|战役|会议|文献|问题)|上述|前述|此人|该人"
)
YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
LOW_RECALL_MIN_HITS = 3


def is_complex_question(question: str) -> bool:
    """Return True when the wording itself asks for multi-aspect coverage."""

    return bool(COMPLEX_QUESTION.search(question))


def is_context_dependent(question: str) -> bool:
    """Return True when the question cannot be executed without resolving a referent."""

    return bool(CONTEXT_DEPENDENT_QUESTION.search(question))


def _mentions_only_out_of_scope_years(settings: Settings, question: str) -> bool:
    years = [int(match.group()) for match in YEAR.finditer(question)]
    if not years:
        return False
    return all(
        year < settings.research_start.year or year > settings.research_end.year
        for year in years
    )


def should_plan_query(settings: Settings, request: QuestionRequest) -> bool:
    """Decide whether the first pass should call the query planner."""

    if not settings.llm_query_planning or not settings.llm_enabled:
        return False
    if not settings.llm_query_planning_gate:
        return True
    if (
        request.history
        or is_complex_question(request.question)
        or is_context_dependent(request.question)
    ):
        return True
    # Keep the dedicated out-of-scope refusal for questions whose only explicit
    # dates are outside the corpus. Retrieval alone cannot produce that answer.
    return _mentions_only_out_of_scope_years(settings, request.question)


def is_low_recall(retrieval: SearchResponse) -> bool:
    """A cheap first-pass signal; degraded branches are an infrastructure issue."""

    if retrieval.degraded_components:
        return False
    return len(retrieval.hits) < LOW_RECALL_MIN_HITS or bool(retrieval.coverage_gaps)


def should_rewrite_after_retrieval(
    settings: Settings,
    request: QuestionRequest,
    *,
    planner_skipped: bool,
    retrieval: SearchResponse | None,
    task_status: str,
) -> bool:
    """Trigger one late rewrite when a previously skipped first pass found too little."""

    if not settings.llm_query_planning or not settings.llm_enabled:
        return False
    if not settings.llm_query_planning_gate or not planner_skipped:
        return False
    if request.history or retrieval is None:
        return False
    return task_status == "empty" or is_low_recall(retrieval)
