"""Public adapters to the single LlamaIndex research workflow."""

from __future__ import annotations

import asyncio

from history_agent.answering.llamaindex_workflow import run_question
from history_agent.answering.models import AnswerResponse, QuestionRequest
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.synthesis import PROMPT_VERSION as PROMPT_VERSION
from history_agent.answering.synthesis import check_deepseek_connection as check_deepseek_connection
from history_agent.config import Settings


async def answer_question_async(
    settings: Settings,
    request: QuestionRequest,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> AnswerResponse:
    return await run_question(settings, request, runtime, budget)


def answer_question(
    settings: Settings,
    request: QuestionRequest,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> AnswerResponse:
    return asyncio.run(answer_question_async(settings, request, runtime, budget))
