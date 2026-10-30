"""Build and validate retrieval query arms from anchored mentions."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from history_agent.answering.entity_linking import AnchoredMention, EntityRecord

YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")


class QueryArm(BaseModel):
    kind: Literal["raw", "canonical", "per_entity"]
    text: str = Field(min_length=2)
    locked: list[str] = Field(default_factory=list)


class ArmValidation(BaseModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)


def _replace_mentions(
    question: str, mentions: list[AnchoredMention], *, single: str | None = None
) -> str:
    parts: list[str] = []
    cursor = 0
    for mention in sorted(mentions, key=lambda item: item.start):
        if mention.start < cursor or mention.status != "anchored":
            continue
        names = [single] if single else mention.canonicals
        if not names:
            continue
        parts.append(question[cursor : mention.start])
        parts.append(" ".join(names))
        cursor = mention.end
    parts.append(question[cursor:])
    return "".join(parts).strip()


def build_query_arms(
    question: str, mentions: list[AnchoredMention], *, max_arms: int = 6
) -> list[QueryArm]:
    anchored = [mention for mention in mentions if mention.status == "anchored"]
    locked = [name for mention in anchored for name in mention.canonicals]
    arms = [QueryArm(kind="raw", text=question, locked=locked)]
    canonical = _replace_mentions(question, anchored)
    if canonical and canonical != question:
        arms.append(QueryArm(kind="canonical", text=canonical, locked=locked))
    for name in dict.fromkeys(locked):
        text = f"{name} {question}"
        if text not in {arm.text for arm in arms}:
            arms.append(QueryArm(kind="per_entity", text=text, locked=[name]))
    return arms[:max_arms]


def validate_arm(
    arm: QueryArm,
    question: str,
    time_range: tuple[int, int] | None,
    records: list[EntityRecord],
) -> ArmValidation:
    issues: list[str] = []
    if arm.kind != "raw":
        for name in arm.locked:
            if name not in arm.text:
                issues.append(f"missing locked entity: {name}")
    allowed_years = {int(match.group()) for match in YEAR.finditer(question)}
    if time_range is not None:
        allowed_years.update(range(time_range[0], time_range[1] + 1))
    for year in {int(match.group()) for match in YEAR.finditer(arm.text)}:
        if allowed_years and year not in allowed_years:
            issues.append(f"new year: {year}")
    known = {record.canonical for record in records}
    for name in arm.locked:
        if name not in known:
            issues.append(f"unknown entity: {name}")
    if len(arm.text) > 300:
        issues.append("arm too long")
    return ArmValidation(valid=not issues, issues=issues)
