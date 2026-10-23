"""SSE transport for the same research run used by the JSON and CLI APIs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import cast

from history_agent.answering.llamaindex_workflow import ProgressEvent, start_question
from history_agent.answering.models import AnswerResponse, QuestionRequest
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.synthesis import AnswerStreamEvent
from history_agent.config import Settings

__all__ = ["AnswerStreamEvent", "stream_answer_question"]


async def stream_answer_question(
    settings: Settings,
    request: QuestionRequest,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> AsyncGenerator[AnswerStreamEvent, None]:
    workflow, handler = start_question(settings, request, runtime, budget)
    completed = False
    try:
        async for event in handler.stream_events():
            if isinstance(event, ProgressEvent):
                yield AnswerStreamEvent(event.event, event.data)
        result = cast(AnswerResponse, await handler)
        if not isinstance(result, AnswerResponse):
            raise TypeError("Research workflow returned an invalid response")
        completed = True
        yield AnswerStreamEvent("done", result.model_dump())
    finally:
        if not completed:
            workflow.budget.cancel()
            await handler.cancel_run()
            # Retrieve cancellation/failure so the detached run cannot leak an
            # unobserved future exception when a browser disconnects.
            with suppress(asyncio.CancelledError, Exception):
                await handler
