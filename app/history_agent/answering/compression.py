"""Deterministic rolling conversation compression for the prompt budget."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from history_agent.answering.context import (
    ConversationMessage,
    ConversationStore,
    SessionNotFound,
    estimate_tokens,
    sanitize_history_content,
)
from history_agent.processing.chunks import extract_people, load_person_aliases

YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
CONSTRAINT_HINT = re.compile(r"只|仅|必须|不要|限定|范围|优先|引用|地区|月份|年份|来源|篇目")
SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class CompressionConfig:
    trigger_messages: int = 6
    keep_recent_messages: int = 2
    max_summary_chars: int = 1_800
    trigger_chars: int = 6_000


def _clip(text: str, limit: int) -> str:
    value = SPACE.sub(" ", sanitize_history_content(text)).strip()
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"


def _people(text: str, aliases: dict[str, list[str]]) -> list[str]:
    if not aliases:
        return []
    try:
        return extract_people(text, aliases)
    except Exception:
        return []


def build_extractive_summary(
    *,
    previous: str,
    messages: list[ConversationMessage],
    max_chars: int = 1_800,
    person_aliases: dict[str, list[str]] | None = None,
) -> str:
    """Build a compact, explicitly non-evidentiary research-state summary."""

    if not messages:
        return _clip(previous, max_chars)
    questions: list[str] = []
    answers: list[str] = []
    constraints: list[str] = []
    for message in messages:
        if message.role == "user":
            question = _clip(message.content, 180)
            if question:
                questions.append(question)
                if CONSTRAINT_HINT.search(question):
                    constraints.append(_clip(question, 120))
        else:
            answer = _clip(message.content, 220)
            if answer:
                answers.append(answer)
    combined = "\n".join([*(item.content for item in messages), previous])
    years = sorted({int(year) for year in YEAR.findall(combined)})
    people = _people(combined, person_aliases or {})
    lines = ["会话摘要（自动压缩，仅用于承接，不是史实证据）："]
    if previous.strip():
        lines.append(f"此前摘要：{_clip(previous, 500)}")
    if questions:
        lines.append("已讨论问题：" + "；".join(questions[-8:]))
    if people:
        lines.append("涉及人物：" + "、".join(people[:12]))
    if years:
        lines.append("涉及年份：" + "、".join(str(year) for year in years[-12:]))
    if constraints:
        lines.append("用户约束/关注点：" + "；".join(dict.fromkeys(constraints[-5:])))
    if answers:
        lines.append(
            "助手曾提到的线索（需本轮证据复核，不作为事实）："
            + "；".join(answers[-3:])
        )
    summary = "\n".join(lines)
    if len(summary) > max_chars:
        summary = summary[: max(1, max_chars - 1)].rstrip() + "…"
    return summary


def maybe_compress_session(
    store: ConversationStore,
    visitor_id: str,
    session_id: str,
    *,
    person_aliases_path: Path | None = None,
    config: CompressionConfig | None = None,
) -> bool:
    """Persist one rolling summary when enough complete messages accumulated.

    Compression is deliberately deterministic and local: it never calls an LLM
    and never turns old assistant text into evidence.
    """

    options = config or CompressionConfig()
    try:
        summary = store.latest_summary(visitor_id, session_id)
        messages = store.session_messages(
            visitor_id,
            session_id,
            after=summary.through_message_id if summary else None,
            limit=1_000,
            include_unfinished=False,
        )
    except SessionNotFound:
        return False
    if len(messages) <= options.keep_recent_messages:
        return False
    if len(messages) < options.trigger_messages and sum(
        len(item.content) for item in messages
    ) < options.trigger_chars:
        return False
    compress_count = len(messages) - options.keep_recent_messages
    if compress_count <= 0:
        return False
    to_compress = messages[:compress_count]
    through_message_id = to_compress[-1].message_id
    if through_message_id is None:
        return False
    aliases: dict[str, list[str]] = {}
    if person_aliases_path is not None:
        try:
            aliases = load_person_aliases(person_aliases_path)
        except Exception:
            aliases = {}
    content = build_extractive_summary(
        previous=summary.content if summary else "",
        messages=to_compress,
        max_chars=options.max_summary_chars,
        person_aliases=aliases,
    )
    if not content:
        return False
    saved = store.save_summary(
        visitor_id,
        session_id,
        through_message_id,
        content,
        model="extractive-v1",
    )
    return saved is not None


def summary_token_count(content: str) -> int:
    return estimate_tokens(content)
