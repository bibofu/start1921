"""Shared HTTP resources, admission control, and per-request deadlines for LLM calls."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

import httpx
from llama_index.core.callbacks import CallbackManager


@dataclass
class RequestBudget:
    deadline: float
    max_llm_calls: int = 24
    llm_calls: int = 0
    llm_exhausted: bool = False
    cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def start(cls, total_seconds: float) -> RequestBudget:
        return cls(monotonic() + total_seconds)

    def timeout(self, cap_seconds: float) -> float:
        if self.cancelled:
            raise httpx.TimeoutException("request cancelled")
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise httpx.TimeoutException("request time budget exhausted")
        return min(cap_seconds, remaining)

    @property
    def remaining(self) -> float:
        return max(0.0, self.deadline - monotonic())

    def consume_call(self) -> None:
        """One shared admission budget for planning, analysis, synthesis and repair."""
        with self._lock:
            self.timeout(float("inf"))
            if self.llm_calls >= self.max_llm_calls:
                self.llm_exhausted = True
                raise httpx.TimeoutException("request model-call budget exhausted")
            self.llm_calls += 1

    def cancel(self) -> None:
        with self._lock:
            self.cancelled = True


class LLMRuntime:
    """Application-scoped HTTP pools guarded by one shared concurrency limit."""

    def __init__(self, max_concurrency: int) -> None:
        limits = httpx.Limits(
            max_connections=max_concurrency,
            max_keepalive_connections=max_concurrency,
        )
        self.sync_client = httpx.Client(
            limits=limits,
            transport=httpx.HTTPTransport(retries=1),
        )
        self.async_client = httpx.AsyncClient(
            limits=limits,
            transport=httpx.AsyncHTTPTransport(retries=1),
        )
        self._capacity = threading.BoundedSemaphore(max_concurrency)
        self.callback_manager = CallbackManager()

    def post(
        self,
        url: str,
        *,
        timeout: float,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        deadline = monotonic() + timeout
        if not self._capacity.acquire(timeout=timeout):
            raise httpx.PoolTimeout("LLM concurrency limit reached")
        try:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise httpx.PoolTimeout("LLM concurrency deadline reached")
            return self.sync_client.post(
                url,
                timeout=remaining,
                headers=headers,
                json=json,
            )
        finally:
            self._capacity.release()

    async def _acquire(self, deadline: float) -> None:
        # A cancelled to_thread(semaphore.acquire) can acquire a permit later and
        # leak it. Nonblocking acquisition keeps ownership on the event loop.
        while not self._capacity.acquire(blocking=False):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise httpx.PoolTimeout("LLM concurrency limit reached")
            await asyncio.sleep(min(0.02, remaining))

    async def apost(
        self,
        url: str,
        *,
        timeout: float,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> httpx.Response:
        deadline = monotonic() + timeout
        await self._acquire(deadline)
        try:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise httpx.PoolTimeout("LLM concurrency deadline reached")
            return await self.async_client.post(
                url,
                timeout=remaining,
                headers=headers,
                json=json,
            )
        finally:
            self._capacity.release()

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> AsyncIterator[httpx.Response]:
        deadline = monotonic() + timeout
        await self._acquire(deadline)
        try:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise httpx.PoolTimeout("LLM concurrency deadline reached")
            async with self.async_client.stream(
                method,
                url,
                timeout=remaining,
                headers=headers,
                json=json,
            ) as response:
                yield response
        finally:
            self._capacity.release()

    async def aclose(self) -> None:
        await self.async_client.aclose()
        self.sync_client.close()
