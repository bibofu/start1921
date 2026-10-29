"""Offline LLM candidate-relevance judge for the Golden 20-question set.

Evaluation-only: this module never changes production retrieval or answers. It
labels an already-frozen candidate pool as 0/1/2 with a reason, or abstains.
Labels use basis ``llm_judge`` and must not be presented as human approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from history_agent.answering.llamaindex_llm import (
    DeepSeekLlamaIndexLLM,
    chat_messages,
    response_usage,
)
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.config import Settings
from history_agent.errors import llm_http_error_code

PROMPT_VERSION = "candidate-relevance-v1"
MAX_TEXT_CHARS = 900


class CandidateJudgment(BaseModel):
    candidate_id: str = Field(min_length=1)
    relevance: Literal[0, 1, 2] | None = None
    supported_groups: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=2, max_length=600)
    abstain: bool = False

    @model_validator(mode="after")
    def validate_consistency(self) -> CandidateJudgment:
        if self.abstain:
            if self.relevance is not None:
                raise ValueError("abstained judgment cannot set relevance")
            if self.supported_groups:
                raise ValueError("abstained judgment cannot support groups")
            return self
        if self.relevance is None:
            raise ValueError("non-abstained judgment requires relevance")
        if self.relevance == 0 and self.supported_groups:
            raise ValueError("irrelevant judgment cannot support groups")
        return self


class CandidateJudgmentSet(BaseModel):
    decisions: list[CandidateJudgment] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> CandidateJudgmentSet:
        ids = [item.candidate_id for item in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate candidate IDs")
        return self


@dataclass(frozen=True)
class CandidateJudgeResult:
    status: Literal["used", "not_configured", "invalid_response", "http_error"]
    decisions: tuple[CandidateJudgment, ...] = ()
    usage: dict[str, int] | None = None
    error_code: str | None = None


def _case_context(case: dict) -> tuple[str, str]:
    facts: list[str] = []
    groups: list[str] = []
    for fact in case.get("facts", []):
        facts.append(
            f"- {fact['id']}: {fact['claim']}（证据组：{', '.join(fact['evidence_group_ids'])}）"
        )
    for group in case.get("evidence_groups", []):
        groups.append(f"- {group['id']}: {group['description']}")
    return "\n".join(facts) or "（无必要事实）", "\n".join(groups) or "（无证据组）"


def _messages(case: dict, candidates: list[dict]) -> list[dict[str, str]]:
    facts, groups = _case_context(case)
    blocks = []
    for index, item in enumerate(candidates, start=1):
        section = " > ".join(item.get("section_path") or []) or "未识别"
        blocks.append(
            f"[C{index}] 《{item['document']}》PDF第{item['pdf_page_start']}页；章节：{section}\n"
            f"{str(item['text'])[:MAX_TEXT_CHARS]}"
        )
    system = (
        "你是严格的史料检索候选相关性评测员，不回答历史问题，不使用外部知识。"
        "只判断给定候选原文与当前问题的相关性，以及它是否直接支持给定的必要事实/证据组。"
        "评级：2=直接支持至少一个必要事实或证据组，原文明确写出日期、职务、动作主体、"
        "地点或关系；1=与问题相关的背景或部分支持，但不足以支持任一必要事实；"
        "0=不相关、实体/时间/地点不符，或只有人名、书名、名单共现而没有动作或关系。"
        "人名同段出现不等于共同参与；名单出现不等于担任职务；时间接近不等于同年发生；"
        "原文相关不等于支持更强的因果、评价或互动结论。"
        "候选被截断或信息不足以可靠判断时，abstain=true，relevance=null，"
        "不得用猜测补成0或1。supported_groups只能填写给定组ID；relevance=0时必须为空；"
        "relevance=2时至少填写一个直接支持的组。"
        "必须为每个候选ID返回且只返回一次，不能增加、删除或重复ID。"
        "只输出JSON对象："
        '{"decisions":[{"candidate_id":"C1","relevance":0|1|2|null,'
        '"supported_groups":["组ID"],"reason":"简短依据","abstain":false}]}。'
    )
    user = (
        f"问题：{case['question']}\n\n"
        f"必要事实：\n{facts}\n\n"
        f"证据组：\n{groups}\n\n"
        f"候选原文：\n\n" + "\n\n".join(blocks)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _validate(
    parsed: CandidateJudgmentSet,
    *,
    candidate_ids: set[str],
    group_ids: set[str],
) -> None:
    returned = {item.candidate_id for item in parsed.decisions}
    if returned != candidate_ids:
        missing = sorted(candidate_ids - returned)
        extra = sorted(returned - candidate_ids)
        raise ValueError(f"candidate IDs differ; missing={missing}; extra={extra}")
    for item in parsed.decisions:
        if not set(item.supported_groups) <= group_ids:
            raise ValueError(f"unknown group for {item.candidate_id}")


def judge_candidates(
    settings: Settings,
    case: dict,
    candidates: list[dict],
    *,
    runtime: LLMRuntime | None = None,
    budget: RequestBudget | None = None,
) -> CandidateJudgeResult:
    """Label one case's frozen candidates; never invent a label on failure."""

    if not settings.llm_enabled:
        return CandidateJudgeResult("not_configured")
    candidate_ids = {item["candidate_id"] for item in candidates}
    group_ids = {group["id"] for group in case.get("evidence_groups", [])}
    if not candidate_ids:
        return CandidateJudgeResult("used", ())

    usage: dict[str, int] | None = None
    try:
        timeout = (
            budget.timeout(settings.llm_timeout_seconds)
            if budget is not None
            else settings.llm_timeout_seconds
        )
        payload: dict[str, object] = {
            "model": settings.llm_model,
            "messages": _messages(case, candidates),
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": min(3200, settings.llm_max_tokens),
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
            return CandidateJudgeResult("invalid_response", usage=usage, error_code="max_tokens")
        content = (response.message.content or "").strip()
        parsed = CandidateJudgmentSet.model_validate_json(content)
        _validate(parsed, candidate_ids=candidate_ids, group_ids=group_ids)
        return CandidateJudgeResult("used", tuple(parsed.decisions), usage=usage)
    except httpx.HTTPError as exc:
        return CandidateJudgeResult(
            "http_error", usage=usage, error_code=llm_http_error_code(exc)
        )
    except (ValidationError, ValueError, KeyError, IndexError, TypeError):
        return CandidateJudgeResult("invalid_response", usage=usage, error_code="invalid_response")


def judgment_to_record(
    judgment: CandidateJudgment,
    *,
    unit_id: str,
    model: str,
    reviewed_at: str,
) -> dict | None:
    """Convert one label to a PilotJudgment dict; abstentions produce no record."""

    if judgment.abstain or judgment.relevance is None:
        return None
    return {
        "unit_id": unit_id,
        "relevance": judgment.relevance,
        "reason": judgment.reason,
        "reviewer": f"llm:{model}:{PROMPT_VERSION}",
        "reviewed_at": reviewed_at,
        "basis": "llm_judge",
        "supported_groups": list(judgment.supported_groups),
    }
