"""LLM candidate generation for entity mentions, constrained to the entity index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from history_agent.answering.entity_linking import EntityRecord
from history_agent.answering.llamaindex_llm import (
    DeepSeekLlamaIndexLLM,
    chat_messages,
    response_usage,
)
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.config import Settings
from history_agent.errors import llm_http_error_code

PROMPT_VERSION = "entity-candidates-v1"
MAX_MENTIONS = 6
MAX_ALLOWED_ENTITIES = 160


class ProposedCandidate(BaseModel):
    mention_text: str = Field(min_length=1, max_length=40)
    entity_id: str = ""
    canonical: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class CandidateSet(BaseModel):
    candidates: list[ProposedCandidate] = Field(default_factory=list, max_length=12)


@dataclass(frozen=True)
class EntityCandidateResult:
    status: Literal["used", "not_configured", "invalid_response", "http_error"]
    candidates: tuple[ProposedCandidate, ...] = ()
    usage: dict[str, int] | None = None
    error_code: str | None = None


def _messages(
    query: str, mentions: list[str], records: list[EntityRecord]
) -> list[dict[str, str]]:
    allowed = []
    for record in records[:MAX_ALLOWED_ENTITIES]:
        aliases = "、".join(record.aliases[:4])
        allowed.append(
            f"{record.entity_id} | {record.type} | {record.canonical}"
            + (f" | {aliases}" if aliases else "")
        )
    system = (
        "你是史料库的实体消歧器，不回答历史问题，不使用外部知识。"
        "给定用户问题和若干未识别的提及，只能从允许的实体列表中选择 entity_id；"
        "不能创造新实体、不能改写问题、不能补充事实。"
        "mention_text 必须是问题中连续出现的最短实体名（2-12 字），不得包含动词、助词、"
        "时间、疑问词或整句；例如“周恩來在重慶参加了哪些谈判”应拆成“周恩來”和“重慶”两个提及。"
        "对每个提及，如果能在允许列表中找到明确对应，返回 1-2 个候选；"
        "如果找不到或不确定，返回空候选。confidence 取 0 到 1。"
        "只输出 JSON："
        '{"candidates":[{"mention_text":"原提及","entity_id":"允许列表中的ID",'
        '"canonical":"规范名","confidence":0.0}]}。'
    )
    user = (
        f"用户问题：{query}\n\n"
        f"待识别提及：{'、'.join(mentions)}\n\n"
        "允许的实体（entity_id | 类型 | 规范名 | 别名）：\n" + "\n".join(allowed)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _validate(
    parsed: CandidateSet,
    *,
    query: str,
    mentions: list[str],
    records: list[EntityRecord],
) -> CandidateSet:
    by_id = {record.entity_id: record for record in records}
    seen: set[tuple[str, str]] = set()
    accepted: list[ProposedCandidate] = []
    for candidate in parsed.candidates:
        if not candidate.entity_id.strip() or not candidate.canonical.strip():
            continue
        record = by_id.get(candidate.entity_id)
        if record is None:
            raise ValueError("unknown entity id")
        if candidate.mention_text not in query:
            continue
        if not 2 <= len(candidate.mention_text) <= 12:
            continue
        if any(
            marker in candidate.mention_text
            for marker in (
                "在", "的", "了", "和", "与", "期间",
                "参加", "什么", "哪些", "年", "月", "日",
            )
        ):
            continue
        if not any(
            candidate.mention_text in mention or mention in candidate.mention_text
            for mention in mentions
        ):
            continue
        if candidate.canonical != record.canonical:
            raise ValueError("canonical mismatch")
        key = (candidate.mention_text, candidate.entity_id)
        if key in seen:
            continue
        seen.add(key)
        accepted.append(candidate)
    return CandidateSet(candidates=accepted)


def propose_candidates(
    settings: Settings,
    query: str,
    mentions: list[str],
    records: list[EntityRecord],
    *,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> EntityCandidateResult:
    mentions = list(dict.fromkeys(mention for mention in mentions if mention.strip()))[
        :MAX_MENTIONS
    ]
    if not mentions:
        return EntityCandidateResult("used", ())
    if not settings.llm_enabled:
        return EntityCandidateResult("not_configured")
    usage: dict[str, int] | None = None
    try:
        timeout = (
            budget.timeout(settings.llm_timeout_seconds)
            if budget is not None
            else settings.llm_timeout_seconds
        )
        payload: dict[str, object] = {
            "model": settings.llm_model,
            "messages": _messages(query, mentions, records),
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": min(1600, settings.llm_max_tokens),
            "temperature": 0,
            "thinking": {"type": "disabled"},
        }
        llm = DeepSeekLlamaIndexLLM(
            settings=settings,
            runtime=runtime,
            budget=budget,
            model=settings.llm_model,
            timeout_seconds=timeout,
        )
        response = llm.chat(chat_messages(payload), request_payload=payload)
        usage = response_usage(response)
        if response.additional_kwargs.get("finish_reason") == "length":
            return EntityCandidateResult(
                "invalid_response", usage=usage, error_code="max_tokens"
            )
        parsed = CandidateSet.model_validate_json((response.message.content or "").strip())
        validated = _validate(
            parsed, query=query, mentions=mentions, records=records
        )
        return EntityCandidateResult("used", tuple(validated.candidates), usage=usage)
    except httpx.HTTPError as exc:
        return EntityCandidateResult(
            "http_error", usage=usage, error_code=llm_http_error_code(exc)
        )
    except (ValidationError, ValueError, KeyError, IndexError, TypeError) as exc:
        return EntityCandidateResult(
            "invalid_response", usage=usage, error_code=f"invalid_response:{type(exc).__name__}"
        )
