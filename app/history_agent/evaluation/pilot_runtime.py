"""Record actual outbound LLM bodies for offline evaluation, never credentials."""

from __future__ import annotations

import copy
import threading
from time import perf_counter
from typing import Any

import httpx

from history_agent.answering.runtime import LLMRuntime
from history_agent.retrieval.models import SearchResponse


class RecordedLLMRuntime(LLMRuntime):
    capture_retrieval_trace = True

    def __init__(self, max_concurrency: int) -> None:
        super().__init__(max_concurrency)
        self.calls: list[dict[str, Any]] = []
        self.retrieval_calls: list[dict[str, Any]] = []
        self._record_lock = threading.Lock()

    def record_retrieval(self, phase: str, response: SearchResponse) -> None:
        with self._record_lock:
            self.retrieval_calls.append(
                {
                    "phase": phase,
                    "response": response.model_dump(mode="json"),
                }
            )

    def _start(self, payload: dict[str, object]) -> dict[str, Any]:
        # Explicit allowlist: headers, URLs and secrets never enter the artifact.
        entry: dict[str, Any] = {
            "request": copy.deepcopy(
                {
                    key: payload[key]
                    for key in (
                        "model",
                        "messages",
                        "temperature",
                        "max_tokens",
                        "thinking",
                        "reasoning_effort",
                        "response_format",
                        "stream",
                    )
                    if key in payload
                }
            ),
            "status": "started",
            "elapsed_ms": None,
        }
        with self._record_lock:
            entry["call_index"] = len(self.calls) + 1
            self.calls.append(entry)
        return entry

    @staticmethod
    def _record_response(entry: dict[str, Any], response: httpx.Response) -> None:
        entry.update(status="response", http_status=response.status_code)
        if response.status_code != 200:
            return  # Error bodies can echo request headers or endpoint details.
        try:
            payload = response.json()
        except ValueError:
            entry["response_capture_status"] = "invalid_json"
            return
        if not isinstance(payload, dict):
            entry["response_capture_status"] = "unexpected_shape"
            return
        choices = []
        raw_choices = payload.get("choices")
        for choice in raw_choices if isinstance(raw_choices, list) else []:
            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                continue
            content = choice["message"].get("content")
            if not isinstance(content, str):
                continue
            choices.append(
                {
                    "index": choice.get("index"),
                    "finish_reason": choice.get("finish_reason"),
                    "message": {"role": "assistant", "content": content},
                }
            )
        usage = payload.get("usage", {})
        entry["response_summary"] = {
            "model": payload.get("model") if isinstance(payload.get("model"), str) else None,
            "choices": choices,
            "usage": {
                key: value
                for key, value in usage.items()
                if key
                in {
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                }
                and type(value) is int
                and value >= 0
            }
            if isinstance(usage, dict)
            else {},
        }
        entry["response_capture_status"] = "recorded"

    def post(
        self, url: str, *, timeout: float, headers: dict[str, str], json: dict[str, object]
    ) -> httpx.Response:
        entry = self._start(json)
        started = perf_counter()
        try:
            response = super().post(url, timeout=timeout, headers=headers, json=json)
            self._record_response(entry, response)
            return response
        except httpx.HTTPError as exc:
            entry.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            entry["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)

    async def apost(
        self, url: str, *, timeout: float, headers: dict[str, str], json: dict[str, object]
    ) -> httpx.Response:
        entry = self._start(json)
        started = perf_counter()
        try:
            response = await super().apost(url, timeout=timeout, headers=headers, json=json)
            self._record_response(entry, response)
            return response
        except httpx.HTTPError as exc:
            entry.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            entry["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
