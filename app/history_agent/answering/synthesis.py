"""One asynchronous, evidence-grounded LlamaIndex response synthesizer.

The workflow performs exactly one bounded synthesis attempt. The model answer is
returned unchanged; citation validation and answer repair live outside production.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, cast

import httpx
from llama_index.core.callbacks import CallbackManager
from llama_index.core.llms.mock import MockLLM
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.prompts.mixin import PromptDictType
from llama_index.core.response_synthesizers.base import BaseSynthesizer

from history_agent.answering.context import sanitize_history_content
from history_agent.answering.llamaindex_llm import (
    DeepSeekLlamaIndexLLM,
    chat_messages,
    response_usage,
)
from history_agent.answering.models import Citation, QuestionRequest
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.config import Settings
from history_agent.errors import llm_http_error_code


@dataclass(frozen=True)
class AnswerStreamEvent:
    event: Literal["status", "delta", "reset", "done", "error"]
    data: dict[str, Any]

    def encode(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


@dataclass(frozen=True)
class LLMResult:
    """The model output and usage; the workflow performs no answer validation."""

    answer: str | None
    error_code: str | None = None
    usage: dict[str, int] | None = None
    map_failed: bool = False


EventSink = Callable[[AnswerStreamEvent], None]

SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；])")


PROMPT_VERSION = "grounded-answer-v15"


LLM_EVIDENCE_BATCH_SIZE = 12


def _citations_used_by_answer(answer: str, citations: list[Citation]) -> list[Citation]:
    """Expose only evidence the authoritative answer actually cites."""

    used_ids = set(re.findall(r"\[(E\d+)\]", answer))
    return [citation for citation in citations if citation.evidence_id in used_ids]


def _extractive_answer(intent: str, citations: list[Citation]) -> str:
    if not citations:
        return "现有本地资料中没有检索到足以回答这个问题的证据。"
    lead = {
        "timeline": "根据当前本地资料，可先按以下史料线索梳理：",
        "intersection": (
            "根据当前本地资料，检索到以下涉及两位人物的史料线索，可据原文核查具体交集："
        ),
        "viewpoint": "根据当前本地资料，相关观点主要见于以下原文：",
    }.get(intent, "根据当前本地资料，检索到以下可核验线索：")
    bullets: list[str] = []
    for citation in citations[:5]:
        sentences = [
            item.strip()
            for item in SENTENCE_BOUNDARY.split(citation.quote)
            if len(item.replace("…", "").strip().strip("。")) >= 12
        ]
        summary = (sentences[0] if sentences else citation.quote)[:180].strip()
        summary = re.sub(r"^[…，、\s]+", "", summary)
        year_prefix = ""
        if intent == "timeline" and citation.year_mentions:
            year_prefix = "、".join(str(year) for year in citation.year_mentions[:3]) + "年："
        bullets.append(f"- {year_prefix}{summary} [{citation.evidence_id}]")
    return lead + "\n\n" + "\n".join(bullets)


def _merge_usage(*items: dict[str, int] | None) -> dict[str, int] | None:
    keys = {key for item in items if item for key in item}
    if not keys:
        return None
    return {key: sum(item.get(key, 0) for item in items if item) for key in keys}


def _llm_request_payload(
    *,
    settings: Settings,
    request: QuestionRequest,
    citations: list[Citation],
    evidence_override: str | None = None,
    max_tokens: int | None = None,
) -> dict[str, object]:
    evidence = evidence_override or "\n\n".join(
        f"[{item.evidence_id}] 《{item.document}》PDF第{item.pdf_page}页"
        f"；片段标注年份：{'、'.join(str(year) for year in item.year_mentions) or '未标注'}"
        f"；章节：{' > '.join(item.section) or '未识别'}\n{item.quote}"
        for item in citations
    )
    system = (
        "你是中国近现代史本地史料研究助手。只能根据用户提供的证据回答，不能用模型记忆"
        "补充事实。每个事实性结论后必须标注对应证据编号，如[E1]。区分原文观点、年谱记载"
        "和后人叙述；证据不足就明确说明。不要虚构页码或证据编号。先给简明结论，再按时间"
        "或主题组织要点，最后说明资料限制。不要输出证据包中不存在的知识。回答中必须至少"
        "出现一个本次证据编号；引用格式只能是[E1]、[E2]这种形式。每一条包含日期、职务、"
        "地点、行动或人物关系的事实必须在同一段或同一列表项给出证据编号；同一要点正常换行"
        "不必重复标注。如需写文献名或PDF页码，必须与证据包完全一致。"
        "对于人物交集问题，必须说明原文支持两人围绕哪一具体事件发生了什么互动，"
        "区分共同参与、意见支持与分工协作，不能把人名共现推断成共同参与。"
        "若问题指定长征等历史时期，只总结证据明确支持属于该时期的活动；"
        "检索年份范围只是召回线索，不能把同年其他活动或后来的回忆当作当时的交集。"
        "若证据覆盖所问时期的多个阶段，须按阶段组织回答，不能只总结前半段；"
        "对于跨年人物活动梳理，若证据覆盖多个年份，须按年份组织，不能只回答起止年份；"
        "跨年问题的每个时间要点必须写明四位年份，或放在明确的四位年份小标题下；"
        "不能脱离年份标题只写‘10月’、‘11月3日’或‘同年’，也不能打乱跨年顺序；"
        "对于人物经历或活动问题，只纳入证据明确表明目标人物亲自实施、参与或承担角色的事项；"
        "他人致电、邀请、评价或提到目标人物，以及目标人物仅作为收件人、被会见者或名单成员"
        "而没有明确行动的材料，不能自动写成该人物的经历。没有目标人物专属年谱时，可以使用"
        "其他年谱、党史和文献中的直接记载，但必须逐项核对动作主体；"
        "对于结构化年谱记录，若用户询问主要经历、概括或总结，应合并同类活动，按阶段"
        "或主题归纳；若用户明确要求列出时间线、逐条记录、原文或明细，则保持记录粒度和"
        "先后顺序，但仍整理成通顺回答。结构化索引日期只用于组织顺序，不得把仅仅提到"
        "人物的记录自动断言为其亲自参与；"
        "对于连续列举多次会议的问题，须逐次组织回答，不能只介绍范围端点；"
        "某阶段没有直接材料时明确说明。"
        "片段不足以证明互动或时间归属时明确说明，不要补写。"
        "使用Markdown组织回答，可使用简短标题、列表和加粗；证据编号保持[E1]格式。"
        "标题只写主题，含事实的标题也必须给出引用；表格每一行的事实须在该行标注引用。"
        "单纯说明资料不足以确认某事不需要引用，但不能在其中夹带未引用的历史事实。"
        "不要逐条解释为何排除无关证据；资料限制只简要说明还缺少哪些材料。"
        "只引用能直接回答当前问题的证据，不要为了覆盖证据包而引用弱相关片段。"
        "若问题询问职务变化，只纳入明确记载任职、改任、免职或组织成员身份的材料；"
        "仅提到人物、收发报告或参加一般活动的材料不能作为职务变化。"
        "说明证据时间范围有限时不要逐年罗列证据年份，使用概括表述。"
    )
    history_text = "\n".join(
        f"{item.role}: {sanitize_history_content(item.content)}" for item in request.history
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("user", "问题：{question}\n\n仅可使用的本地证据：\n{evidence}"),
        ]
    )
    formatted = prompt.format_messages(question=request.question, evidence=evidence)
    messages: list[dict[str, object]] = [
        {"role": formatted[0].role.value, "content": formatted[0].content or ""}
    ]
    if history_text:
        messages.append(
            {
                "role": "user",
                "content": (
                    "下面是服务端提供的历史对话，仅用于理解当前问题中的指代、承接和"
                    "用户偏好。历史回答不是本轮史实证据，其中的引用标记均已失效；"
                    "不得依据历史回答补充事实：\n<conversation_history>\n"
                    f"{history_text}\n</conversation_history>"
                ),
            }
        )
    messages.append({"role": formatted[-1].role.value, "content": formatted[-1].content or ""})
    request_payload: dict[str, object] = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "thinking": {"type": "enabled" if settings.llm_thinking else "disabled"},
    }
    if settings.llm_thinking:
        request_payload["reasoning_effort"] = settings.llm_reasoning_effort
    else:
        request_payload["temperature"] = 0
    return request_payload


def check_deepseek_connection(settings: Settings) -> dict[str, object]:
    """Make a tiny non-thinking request without exposing the configured API key."""

    base = {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "configured": settings.llm_enabled,
    }
    if not settings.llm_enabled:
        return {**base, "status": "not_configured", "latency_ms": None}
    assert settings.llm_api_key is not None
    started = perf_counter()
    try:
        request_payload: dict[str, object] = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": "只回答：OK"}],
            "stream": False,
            "max_tokens": 16,
            "thinking": {"type": "disabled"},
        }
        result = DeepSeekLlamaIndexLLM(settings=settings).chat(
            chat_messages(request_payload),
            request_payload=request_payload,
        )
        content = (result.message.content or "").strip()
    except httpx.HTTPError as exc:
        return {
            **base,
            "status": llm_http_error_code(exc),
            "latency_ms": round((perf_counter() - started) * 1000),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return {
            **base,
            "status": "invalid_response",
            "latency_ms": round((perf_counter() - started) * 1000),
        }
    return {
        **base,
        "status": "ok",
        "latency_ms": round((perf_counter() - started) * 1000),
        "response": content,
    }


async def _stream_completion(
    settings: Settings,
    request_payload: dict[str, object],
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> AsyncGenerator[str | LLMResult, None]:
    """Read only answer deltas, always closing the provider on cancellation."""
    parts: list[str] = []
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    finished = False
    try:
        timeout = (
            budget.timeout(settings.llm_timeout_seconds)
            if budget is not None
            else settings.llm_timeout_seconds
        )
        llm = DeepSeekLlamaIndexLLM(
            settings=settings,
            runtime=runtime,
            budget=budget,
            timeout_seconds=timeout,
        )
        stream = llm.raw_astream_chat(
            chat_messages(request_payload), request_payload=request_payload
        )
        async with aclosing(stream):
            async for response in stream:
                usage = response_usage(response) or usage
                if response.additional_kwargs.get("done"):
                    finished = True
                    break
                if response.delta:
                    parts.append(response.delta)
                    yield response.delta
                if response.additional_kwargs.get("finish_reason") is not None:
                    finish_reason = str(response.additional_kwargs["finish_reason"])
    except httpx.HTTPError as exc:
        yield LLMResult(answer=None, error_code=llm_http_error_code(exc), usage=usage)
        return
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        yield LLMResult(answer=None, error_code="invalid_response", usage=usage)
        return
    if finish_reason == "length":
        yield LLMResult(answer=None, error_code="max_tokens_exhausted", usage=usage)
    elif not finished or finish_reason != "stop":
        yield LLMResult(answer=None, error_code="incomplete_stream", usage=usage)
    else:
        answer = "".join(parts).strip()
        yield LLMResult(
            answer=answer or None,
            error_code=None if answer else "empty_response",
            usage=usage,
        )


async def _generation_events(
    settings: Settings,
    request: QuestionRequest,
    citations: list[Citation],
    runtime: LLMRuntime | None,
    budget: RequestBudget | None,
    *,
    request_payload: dict[str, object] | None = None,
    initial_usage: dict[str, int] | None = None,
    emit_deltas: bool = True,
) -> AsyncGenerator[AnswerStreamEvent | LLMResult, None]:
    """Perform exactly one model call and return its answer unchanged."""
    payload = request_payload or _llm_request_payload(
        settings=settings, request=request, citations=citations
    )
    result = LLMResult(answer=None, error_code="incomplete_stream")
    async with aclosing(_stream_completion(settings, payload, runtime, budget)) as completion:
        async for item in completion:
            if isinstance(item, str):
                if emit_deltas:
                    yield AnswerStreamEvent("delta", {"text": item})
            else:
                result = item
    result = LLMResult(
        answer=result.answer,
        error_code=result.error_code,
        usage=_merge_usage(initial_usage, result.usage),
    )
    yield result


@dataclass(frozen=True)
class HierarchicalPreparation:
    request_payload: dict[str, object]
    usage: dict[str, int] | None
    map_failed: bool


async def _prepare_hierarchical_answer(
    *,
    settings: Settings,
    request: QuestionRequest,
    citations: list[Citation],
    runtime: LLMRuntime | None,
    budget: RequestBudget | None,
) -> HierarchicalPreparation:
    """Summarize independent batches once; failed batches retain their raw quotes."""
    batches = [
        citations[index : index + LLM_EVIDENCE_BATCH_SIZE]
        for index in range(0, len(citations), LLM_EVIDENCE_BATCH_SIZE)
    ]
    capacity = asyncio.Semaphore(3)

    async def summarize(index: int, batch: list[Citation]) -> tuple[str, LLMResult]:
        instruction = (
            f"{request.question}\n\n这是覆盖检索的第 {index + 1}/{len(batches)} 组证据。"
            "请只提炼本组能支持的局部结论，保留每项原始证据编号，控制在600字以内；"
            "不要因为这是局部证据就下完整性结论。"
        )
        partial_request = request.model_copy(update={"question": instruction, "history": []})
        payload = _llm_request_payload(
            settings=settings,
            request=partial_request,
            citations=batch,
            max_tokens=min(settings.llm_max_tokens, 1200),
        )
        result = LLMResult(answer=None, error_code="incomplete_stream")
        async with (
            capacity,
            aclosing(
                _generation_events(
                    settings,
                    partial_request,
                    batch,
                    runtime,
                    budget,
                    request_payload=payload,
                    emit_deltas=False,
                )
            ) as events,
        ):
            async for item in events:
                if isinstance(item, LLMResult):
                    result = item
        if result.answer:
            return result.answer, result
        return "\n".join(f"[{item.evidence_id}] {item.quote}" for item in batch), result

    tasks = [asyncio.create_task(summarize(index, batch)) for index, batch in enumerate(batches)]
    try:
        mapped = await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    summaries = "\n\n".join(
        f"第 {index + 1} 组{'原文摘录' if result.answer is None else '分组归纳摘要'}：\n{summary}"
        for index, (summary, result) in enumerate(mapped)
    )
    return HierarchicalPreparation(
        request_payload=_llm_request_payload(
            settings=settings,
            request=request,
            citations=citations,
            evidence_override=(
                "以下是分组证据经分组归纳后的摘要，失败分组保留原文摘录。"
                "请合并重复内容，检查各分组覆盖，形成完整回答；"
                "只能使用以下内容中出现的原始证据编号。\n\n" + summaries
            ),
        ),
        usage=_merge_usage(*(result.usage for _, result in mapped)),
        map_failed=any(result.answer is None for _, result in mapped),
    )


class HistoryResponseSynthesizer(BaseSynthesizer):
    """A per-request synthesizer with one async path for buffered and streamed APIs.

    The workflow calls ``asynthesize`` with source nodes, ``request``, ``citations``
    and an optional synchronous ``event_sink``. ``last_result`` contains the model
    answer, usage and transport error, if any; no validation or repair is performed.
    """

    def __init__(
        self,
        settings: Settings,
        runtime: LLMRuntime | None = None,
        budget: RequestBudget | None = None,
    ) -> None:
        self._settings = settings
        self._runtime = runtime
        self._budget = budget
        self.last_result = LLMResult(answer=None, error_code="no_evidence")
        callbacks = runtime.callback_manager if runtime is not None else CallbackManager()
        # With generation disabled the metadata-only placeholder is never called.
        # Passing an explicit LLM also prevents BaseSynthesizer loading a default provider.
        llm = (
            DeepSeekLlamaIndexLLM(settings=settings, runtime=runtime, budget=budget)
            if settings.llm_enabled
            else MockLLM()
        )
        super().__init__(
            llm=llm,
            callback_manager=callbacks,
            streaming=False,
            empty_response=_extractive_answer("general", []),
        )

    def _get_prompts(self) -> PromptDictType:
        return {}

    def _update_prompts(self, prompts: PromptDictType) -> None:
        if prompts:
            raise ValueError("History synthesis prompts are versioned with the evidence rules")

    def get_response(
        self, query_str: str, text_chunks: Sequence[str], **response_kwargs: Any
    ) -> str:
        """Synchronous LlamaIndex compatibility uses the same async implementation."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aget_response(query_str, text_chunks, **response_kwargs))
        raise RuntimeError("Use asynthesize inside an active event loop")

    async def aget_response(
        self, query_str: str, text_chunks: Sequence[str], **response_kwargs: Any
    ) -> str:
        del text_chunks  # Citation quotes carry the checked source identity and page mapping.
        request = response_kwargs.get("request") or QuestionRequest(question=query_str)
        citations = response_kwargs.get("citations")
        if not isinstance(request, QuestionRequest) or not isinstance(citations, list):
            raise ValueError("History synthesis requires a QuestionRequest and source citations")
        sink: EventSink | None = response_kwargs.get("event_sink")
        async with aclosing(
            self.synthesize_events(
                request,
                citations,
                request_payload=response_kwargs.get("request_payload"),
                initial_usage=response_kwargs.get("initial_usage"),
                map_failed=response_kwargs.get("map_failed", False),
                findings=response_kwargs.get("findings", []),
            )
        ) as events:
            async for item in events:
                if isinstance(item, LLMResult):
                    self.last_result = item
                elif sink is not None:
                    sink(item)
        return self.last_result.answer or _extractive_answer(
            response_kwargs.get("intent", "general"), citations
        )

    async def synthesize_events(
        self,
        request: QuestionRequest,
        citations: list[Citation],
        *,
        request_payload: dict[str, object] | None = None,
        initial_usage: dict[str, int] | None = None,
        map_failed: bool = False,
        findings: Sequence[str] = (),
    ) -> AsyncGenerator[AnswerStreamEvent | LLMResult, None]:
        if not citations:
            yield LLMResult(answer=None, error_code="no_evidence")
            return
        if not self._settings.llm_enabled:
            yield LLMResult(answer=None, error_code="not_configured")
            return
        preparation: HierarchicalPreparation | None = None
        if request_payload is None and len(citations) > LLM_EVIDENCE_BATCH_SIZE:
            yield AnswerStreamEvent("status", {"message": "正在分组归纳跨阶段证据…"})
            preparation = await _prepare_hierarchical_answer(
                settings=self._settings,
                request=request,
                citations=citations,
                runtime=self._runtime,
                budget=self._budget,
            )
            request_payload = preparation.request_payload
            initial_usage = _merge_usage(initial_usage, preparation.usage)
            map_failed = map_failed or preparation.map_failed
        if findings:
            request_payload = request_payload or _llm_request_payload(
                settings=self._settings, request=request, citations=citations
            )
            allowed = {citation.evidence_id for citation in citations}
            selected: list[str] = []
            size = 0
            for finding in findings:
                markers = set(re.findall(r"\bE\d+\b", finding))
                if not markers or not markers <= allowed:
                    continue
                if size + len(finding) > 8_000:
                    break
                selected.append(finding)
                size += len(finding)
            if selected:
                messages = list(cast(list[dict[str, object]], request_payload["messages"]))
                messages.insert(
                    -1,
                    {
                        "role": "user",
                        "content": (
                            "以下是研究任务形成的待核实提纲，仅帮助组织回答，不是独立史实证据。"
                            "请逐项对照本轮原文证据核实，保留差异和缺口，不能仅凭提纲补充事实。\n"
                            "<research_findings>\n" + "\n".join(selected) + "\n</research_findings>"
                        ),
                    },
                )
                request_payload = {**request_payload, "messages": messages}
        async with aclosing(
            _generation_events(
                self._settings,
                request,
                citations,
                self._runtime,
                self._budget,
                request_payload=request_payload,
                initial_usage=initial_usage,
            )
        ) as events:
            async for item in events:
                if isinstance(item, LLMResult) and map_failed:
                    item = LLMResult(
                        answer=item.answer,
                        error_code=(
                            "hierarchical_partial_map_fallback"
                            if item.answer and item.error_code is None
                            else item.error_code
                        ),
                        usage=item.usage,
                        map_failed=True,
                    )
                yield item
