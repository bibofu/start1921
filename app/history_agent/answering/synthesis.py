"""One asynchronous, evidence-grounded LlamaIndex response synthesizer.

The request workflow owns decisions to retry or repair. This module performs one
bounded synthesis attempt, preserves source citations, and reports repair inputs.
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
from llama_index.core.schema import NodeWithScore, TextNode

from history_agent.answering.context import requires_conversation_context, sanitize_history_content
from history_agent.answering.llamaindex_llm import (
    DeepSeekLlamaIndexLLM,
    chat_messages,
    response_usage,
)
from history_agent.answering.models import Citation, QuestionRequest
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.validation import (
    FULL_DATE_REFERENCE,
    citation_event_date,
    normalize_chinese_dates,
    remove_uncited_claim_blocks,
    validate_grounded_answer,
)
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
    """A validated answer or a repair proposal for the owning workflow."""

    answer: str | None
    error_code: str | None = None
    usage: dict[str, int] | None = None
    uncited_claims: tuple[str, ...] = ()
    repair_payload: dict[str, object] | None = None
    repair_kind: Literal["citation", "citation_date", "timeline_year"] | None = None
    map_failed: bool = False


EventSink = Callable[[AnswerStreamEvent], None]

SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；])")


QUESTION_YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")


ANSWER_YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}年")


MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")


TIMELINE_DATE = re.compile(
    r"(?:(?P<year>(?:18|19|20)\d{2})\s*年\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*月"
    r"(?:\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*日)?"
)


PROMPT_VERSION = "grounded-answer-v15"


LLM_EVIDENCE_BATCH_SIZE = 12


def _citations_used_by_answer(answer: str, citations: list[Citation]) -> list[Citation]:
    """Expose only evidence the authoritative answer actually cites."""

    used_ids = set(validate_grounded_answer(answer, citations).used_evidence_ids)
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


def _salvage_llm_result(
    answer: str,
    citations: list[Citation],
    uncited_claims: tuple[str, ...],
    usage: dict[str, int] | None,
) -> LLMResult | None:
    salvaged = remove_uncited_claim_blocks(answer, uncited_claims)
    if salvaged is None or not validate_grounded_answer(salvaged, citations).valid:
        return None
    return LLMResult(
        answer=salvaged,
        error_code="removed_uncited_claims",
        usage=usage,
        uncited_claims=uncited_claims,
    )


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
    history_items = request.history if requires_conversation_context(request.question) else []
    history_text = "\n".join(
        f"{item.role}: {sanitize_history_content(item.content)}" for item in history_items
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


def _repair_request_payload(
    request_payload: dict[str, object],
    answer: str,
    citations: list[Citation],
    uncited_claims: tuple[str, ...],
) -> dict[str, object]:
    missing_claims = "\n".join(f"- {claim}" for claim in uncited_claims)
    valid_markers = "、".join(f"[{item.evidence_id}]" for item in citations)
    repair_instruction = (
        "上一版回答因部分事实要点缺少引用而未通过校验。请重新输出完整回答，不要增加新事实，"
        "根据原文修复引用覆盖：有证据支持才添加对应编号，没有证据支持的事实必须删除，"
        "不能随意挂靠引用。每个包含日期、职务、地点、行动、会议决定或人物关系的段落、"
        f"列表项或表格行都要使用对应的合法编号（仅限：{valid_markers}）。"
        "单纯说明资料不足以确认某事不需要引用。缺少引用的要点如下：\n"
        f"{missing_claims}"
    )
    return {
        **request_payload,
        "messages": [
            *cast(list[dict[str, object]], request_payload["messages"]),
            {"role": "assistant", "content": answer},
            {"role": "user", "content": repair_instruction},
        ],
    }


def _has_ambiguous_timeline_years(request: QuestionRequest, answer: str) -> bool:
    """Detect month-only timeline items that lost their year in a multi-year answer."""

    question_years = {int(year) for year in QUESTION_YEAR.findall(request.question)}
    if len(question_years) < 2 or min(question_years) == max(question_years):
        return False
    active_year: int | None = None
    previous_date: tuple[int, int, int] | None = None
    for line in answer.splitlines():
        stripped = line.strip()
        if MARKDOWN_HEADING.match(stripped):
            heading_year = ANSWER_YEAR.search(stripped)
            active_year = int(heading_year.group()[:4]) if heading_year else None
            previous_date = None
            continue
        if "[E" in stripped and ANSWER_YEAR.search(stripped) is None and active_year is None:
            return True
        if "[E" not in stripped:
            continue
        for match in TIMELINE_DATE.finditer(stripped):
            year = int(match["year"]) if match["year"] else active_year
            if year is None:
                continue
            active_year = year
            current = (
                year,
                int(match["month"]),
                int(match["day"]) if match["day"] else 0,
            )
            if previous_date is not None and current < previous_date:
                return True
            previous_date = current
    return False


def _timeline_year_repair_payload(
    request_payload: dict[str, object], answer: str
) -> dict[str, object]:
    return {
        **request_payload,
        "messages": [
            *cast(list[dict[str, object]], request_payload["messages"]),
            {"role": "assistant", "content": answer},
            {
                "role": "user",
                "content": (
                    "上一版跨年回答丢失了部分时间点的四位年份，导致不同年份的月份混在一起。"
                    "请重新输出完整回答：每个时间要点都写明四位年份，或置于明确的四位年份"
                    "小标题下，并严格按年份先后排序。不得增加证据中没有的年份或事实，原有"
                    "事实仍须保留对应证据编号。"
                ),
            },
        ],
    }


def _citation_date_repair_payload(
    request_payload: dict[str, object], answer: str, mismatches: tuple[str, ...]
) -> dict[str, object]:
    return {
        **request_payload,
        "messages": [
            *cast(list[dict[str, object]], request_payload["messages"]),
            {"role": "assistant", "content": answer},
            {
                "role": "user",
                "content": (
                    "上一版回答中的下列日期与同段所引证据原文不一致："
                    + "、".join(mismatches)
                    + "。请重新输出完整回答，日期必须逐字依据对应证据，不得根据相邻文字"
                    "猜测或补全；无法确认的日期就删除具体月日。其他事实仍须保留对应证据编号。"
                ),
            },
        ],
    }


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


def _demote_unsupported_dates(
    answer: str,
    citations: list[Citation],
    mismatches: tuple[str, ...],
) -> str | None:
    """Replace an unverifiable date with the precision its cited passages support.

    A model repair gets one attempt. When it still cannot align a date, dropping
    the whole answer for an extractive excerpt is worse than losing day precision,
    so the surrounding claim survives at the coarsest supported precision. When no
    cited passage supports even the year, the answer is not demoted at all.
    """

    if not mismatches:
        return None
    normalized_quotes = {
        citation.evidence_id: normalize_chinese_dates(citation.quote) for citation in citations
    }

    def supported_precision(year: int, month: int) -> str | None:
        for citation in citations:
            structured = citation_event_date(citation)
            if structured is not None and structured[0] == year:
                if structured[1] == month:
                    return f"{year}年{month}月"
                return f"{year}年"
            quote = normalized_quotes[citation.evidence_id]
            if (
                year in citation.year_mentions
                or re.search(rf"(?<!\d){year}(?!\d)", quote) is not None
            ):
                if re.search(rf"(?<!\d)0?{month}\s*月", quote) is not None:
                    return f"{year}年{month}月"
                return f"{year}年"
        return None

    candidate = answer
    for broken in mismatches:
        match = FULL_DATE_REFERENCE.search(broken)
        if match is None:
            continue
        replacement = supported_precision(int(match["year"]), int(match["month"]))
        if replacement is None:
            return None
        if broken not in candidate:
            normalized = normalize_chinese_dates(candidate)
            if broken not in normalized:
                continue
            candidate = normalized
        candidate = candidate.replace(broken, replacement)
    candidate = re.sub(r"[（(]\s*[）)]", "", candidate)
    candidate = re.sub(r"(，\s*，|，\s*。)", "，", candidate)
    candidate = candidate.strip()
    if candidate == answer:
        return None
    return candidate if validate_grounded_answer(candidate, citations).valid else None


def _check_generated_answer(
    request: QuestionRequest,
    citations: list[Citation],
    payload: dict[str, object],
    result: LLMResult,
    *,
    propose_repair: bool,
    allow_date_demotion: bool = False,
) -> LLMResult:
    """Clean deterministic defects, returning repair data without executing it."""
    if not result.answer:
        return result
    validation = validate_grounded_answer(result.answer, citations)
    if validation.valid:
        if not _has_ambiguous_timeline_years(request, result.answer):
            return result
        return LLMResult(
            answer=None,
            error_code="ambiguous_timeline_years",
            usage=result.usage,
            repair_kind="timeline_year" if propose_repair else None,
            repair_payload=(
                _timeline_year_repair_payload(payload, result.answer) if propose_repair else None
            ),
        )
    if validation.error_code == "citation_date_mismatch":
        if allow_date_demotion:
            # The single repair attempt could not align the dates. Keep the claim
            # and drop the unsupported precision instead of discarding the answer.
            demoted = _demote_unsupported_dates(
                result.answer, citations, validation.date_mismatches
            )
            if demoted is not None:
                return LLMResult(
                    answer=demoted,
                    error_code="demoted_unverified_dates",
                    usage=result.usage,
                )
        return LLMResult(
            answer=None,
            error_code=validation.error_code,
            usage=result.usage,
            repair_kind="citation_date" if propose_repair else None,
            repair_payload=(
                _citation_date_repair_payload(payload, result.answer, validation.date_mismatches)
                if propose_repair
                else None
            ),
        )
    if validation.error_code == "uncited_core_claim":
        salvaged = _salvage_llm_result(
            result.answer, citations, validation.uncited_claims, result.usage
        )
        if salvaged is not None:
            if not _has_ambiguous_timeline_years(request, salvaged.answer or ""):
                return salvaged
            return LLMResult(
                answer=None,
                error_code="ambiguous_timeline_years",
                usage=result.usage,
                uncited_claims=validation.uncited_claims,
                repair_kind="timeline_year" if propose_repair else None,
                repair_payload=(
                    _timeline_year_repair_payload(payload, salvaged.answer or "")
                    if propose_repair
                    else None
                ),
            )
        return LLMResult(
            answer=None,
            error_code=validation.error_code,
            usage=result.usage,
            uncited_claims=validation.uncited_claims,
            repair_kind="citation" if propose_repair else None,
            repair_payload=(
                _repair_request_payload(
                    payload, result.answer, citations, validation.uncited_claims
                )
                if propose_repair
                else None
            ),
        )
    return LLMResult(
        answer=None,
        error_code=validation.error_code,
        usage=result.usage,
        uncited_claims=validation.uncited_claims,
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
    propose_repair: bool = True,
    emit_deltas: bool = True,
    repair_kind: str | None = None,
) -> AsyncGenerator[AnswerStreamEvent | LLMResult, None]:
    """Perform exactly one model call and one validation; no retry loop."""
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
    if result.answer:
        yield AnswerStreamEvent("status", {"message": "正在核查引用…"})
        result = _check_generated_answer(
            request,
            citations,
            payload,
            result,
            propose_repair=propose_repair,
            allow_date_demotion=repair_kind is not None,
        )
    if repair_kind and result.answer is None:
        result = LLMResult(
            answer=None,
            error_code=f"{repair_kind}_repair_{result.error_code}",
            usage=result.usage,
            uncited_claims=result.uncited_claims,
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
                    propose_repair=False,
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
        f"第 {index + 1} 组{'原文摘录' if result.answer is None else '已核查摘要'}：\n{summary}"
        for index, (summary, result) in enumerate(mapped)
    )
    return HierarchicalPreparation(
        request_payload=_llm_request_payload(
            settings=settings,
            request=request,
            citations=citations,
            evidence_override=(
                "以下是分组证据经逐组引用校验后的摘要，失败分组保留原文摘录。"
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
    and an optional synchronous ``event_sink``. ``last_result`` contains validation
    diagnostics and a repair proposal. Only the workflow may call ``repair_once``.
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
                repair_kind=response_kwargs.get("repair_kind"),
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
        repair_kind: str | None = None,
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
        if findings and repair_kind is None:
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
                propose_repair=repair_kind is None,
                emit_deltas=repair_kind is None,
                repair_kind=repair_kind,
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
                        uncited_claims=item.uncited_claims,
                        repair_payload=item.repair_payload,
                        repair_kind=item.repair_kind,
                        map_failed=True,
                    )
                yield item

    async def repair_once(
        self,
        request: QuestionRequest,
        citations: list[Citation],
        result: LLMResult,
        *,
        event_sink: EventSink | None = None,
        nodes: list[NodeWithScore] | None = None,
    ) -> LLMResult:
        """Execute a workflow-approved repair once, using the same remaining budget."""
        if result.repair_payload is None or result.repair_kind is None:
            return result
        source_nodes = (
            nodes
            if nodes is not None
            else [
                NodeWithScore(
                    node=TextNode(
                        id_=citation.evidence_id,
                        text=citation.quote,
                        metadata={"citation": citation.model_dump(mode="json")},
                    )
                )
                for citation in citations
            ]
        )
        await self.asynthesize(
            request.question,
            source_nodes,
            request=request,
            citations=citations,
            request_payload=result.repair_payload,
            initial_usage=result.usage,
            repair_kind=result.repair_kind,
            map_failed=result.map_failed,
            event_sink=event_sink,
        )
        return self.last_result
