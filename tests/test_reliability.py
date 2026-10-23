import asyncio
from time import monotonic

import httpx
import pytest
from fastapi.testclient import TestClient
from history_agent.answering.llamaindex_llm import DeepSeekLlamaIndexLLM
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.config import Settings
from history_agent.web import app as web_module
from llama_index.core.llms import ChatMessage


def test_request_budget_rejects_work_after_deadline() -> None:
    budget = RequestBudget(monotonic() - 1)

    with pytest.raises(httpx.TimeoutException):
        budget.timeout(20)


def test_call_budget_is_shared_by_models_and_marks_only_rejected_admission(monkeypatch) -> None:
    calls = []

    def complete(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "已完成"}, "finish_reason": "stop"}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", complete)
    settings = Settings(_env_file=None, llm_api_key="test-only-key")
    budget = RequestBudget.start(30)
    budget.max_llm_calls = 1
    planning = DeepSeekLlamaIndexLLM(settings=settings, budget=budget)
    synthesis = DeepSeekLlamaIndexLLM(settings=settings, budget=budget)
    messages = [ChatMessage(role="user", content="检查共享预算")]

    planning.chat(messages)
    assert budget.llm_calls == 1
    assert not budget.llm_exhausted
    with pytest.raises(httpx.TimeoutException, match="model-call budget exhausted"):
        synthesis.chat(messages)
    assert budget.llm_exhausted
    assert budget.llm_calls == 1
    assert len(calls) == 1


def test_cancelled_budget_rejects_new_work_without_using_a_model_call() -> None:
    budget = RequestBudget.start(30)
    budget.cancel()

    with pytest.raises(httpx.TimeoutException, match="request cancelled"):
        budget.timeout(10)
    with pytest.raises(httpx.TimeoutException, match="request cancelled"):
        budget.consume_call()
    assert budget.llm_calls == 0
    assert not budget.llm_exhausted


def test_cancelled_queued_runtime_request_does_not_leak_capacity() -> None:
    async def run() -> None:
        runtime = LLMRuntime(max_concurrency=1)
        entered = asyncio.Event()
        release = asyncio.Event()
        queued = asyncio.Event()
        requests = []

        async def handle(request):
            requests.append(request)
            if len(requests) == 1:
                entered.set()
                await release.wait()
            return httpx.Response(200, json={"ok": True})

        await runtime.async_client.aclose()
        runtime.async_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        acquire = runtime._acquire
        attempts = 0

        async def observed_acquire(deadline):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                queued.set()
            await acquire(deadline)

        runtime._acquire = observed_acquire

        async def request():
            return await runtime.apost(
                "https://model.invalid/chat/completions", timeout=2, headers={}, json={}
            )

        first = asyncio.create_task(request())
        waiting = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            waiting = asyncio.create_task(request())
            await asyncio.wait_for(queued.wait(), 1)
            assert len(requests) == 1
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting
            release.set()
            assert (await asyncio.wait_for(first, 1)).status_code == 200
            # A cancelled waiter must not acquire the newly released permit later.
            assert (await asyncio.wait_for(request(), 1)).status_code == 200
            assert len(requests) == 2
            assert runtime._capacity.acquire(blocking=False)
            assert not runtime._capacity.acquire(blocking=False)
            runtime._capacity.release()
        finally:
            release.set()
            for task in (first, waiting):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (first, waiting) if task is not None), return_exceptions=True
            )
            await runtime.aclose()

    asyncio.run(run())


def test_ready_endpoint_returns_service_unavailable_for_failed_probe(monkeypatch) -> None:
    monkeypatch.setattr(
        web_module,
        "readiness_snapshot",
        lambda settings: {
            "status": "not_ready",
            "components": {"database": True, "keyword": False, "vector": False},
        },
    )

    response = TestClient(web_module.create_app(Settings(_env_file=None))).get("/api/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_ready_endpoint_accepts_single_healthy_retrieval_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        web_module,
        "readiness_snapshot",
        lambda settings: {
            "status": "ready",
            "components": {"database": True, "keyword": True, "vector": False},
        },
    )

    response = TestClient(web_module.create_app(Settings(_env_file=None))).get("/api/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
