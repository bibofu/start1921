"""Dictionary mention detection and evidence-based entity anchoring.

This is the query-side entity layer. It never mutates the runtime person
filter catalog and never invents entities: unknown mentions stay unresolved.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from history_agent.retrieval.keyword_common import infer_year_range

EntityType = Literal[
    "person",
    "document",
    "congress",
    "person_group",
    "event",
    "period",
    "place",
    "organization",
]
Status = Literal["anchored", "candidate", "unresolved"]
YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
QUOTED = re.compile(r"《[^》]*》")
ANCHOR_THRESHOLD = 0.75
CANDIDATE_THRESHOLD = 0.50


class EntityDocument(BaseModel):
    document_id: str
    mentions: int = Field(ge=1)


class EntityRelation(BaseModel):
    canonical: str
    count: int = Field(ge=1)


class EntityRecord(BaseModel):
    entity_id: str
    type: EntityType
    canonical: str
    aliases: list[str] = Field(default_factory=list)
    active: dict[str, int] | None = None
    documents: list[EntityDocument] = Field(default_factory=list)
    cooccurrence: list[EntityRelation] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)


class MentionCandidate(BaseModel):
    entity_id: str
    canonical: str
    type: EntityType
    score: float


class DetectedMention(BaseModel):
    text: str
    start: int
    end: int
    candidates: list[MentionCandidate] = Field(default_factory=list)


class AnchoredMention(BaseModel):
    text: str
    start: int
    end: int
    status: Status
    canonicals: list[str] = Field(default_factory=list)
    candidates: list[MentionCandidate] = Field(default_factory=list)


def load_entities(path: Path) -> list[EntityRecord]:
    records = [
        EntityRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = {record.entity_id for record in records}
    for record in records:
        missing = set(record.members) - ids
        if missing:
            raise ValueError(f"unknown group members: {sorted(missing)}")
    return records


def _alias_map(records: list[EntityRecord]) -> list[tuple[str, EntityRecord]]:
    pairs: list[tuple[str, EntityRecord]] = []
    for record in records:
        for alias in {record.canonical, *record.aliases}:
            if alias:
                pairs.append((alias, record))
    return sorted(pairs, key=lambda item: (-len(item[0]), item[0], item[1].entity_id))


def detect_mentions(query: str, records: list[EntityRecord]) -> list[DetectedMention]:
    aliases = _alias_map(records)
    by_id = {record.entity_id: record for record in records}
    mentions: list[DetectedMention] = []
    index = 0
    while index < len(query):
        for alias, record in aliases:
            if not query.startswith(alias, index):
                continue
            members = (
                [by_id[member] for member in record.members if member in by_id]
                if record.type == "person_group"
                else [record]
            )
            mentions.append(
                DetectedMention(
                    text=alias,
                    start=index,
                    end=index + len(alias),
                    candidates=[
                        MentionCandidate(
                            entity_id=member.entity_id,
                            canonical=member.canonical,
                            type=member.type,
                            score=1.0,
                        )
                        for member in members
                    ],
                )
            )
            index += len(alias)
            break
        else:
            index += 1
    return mentions


def query_time_range(question: str) -> tuple[int, int] | None:
    text = QUOTED.sub("", question)
    years = sorted({int(match.group()) for match in YEAR.finditer(text)})
    range_ = infer_year_range(text, years)
    return (range_[0], range_[1]) if range_ else None


def _temporal_score(
    record: EntityRecord, time_range: tuple[int, int] | None
) -> float:
    if time_range is None or record.active is None:
        return 0.5
    start, end = record.active.get("start"), record.active.get("end")
    if start is None or end is None:
        return 0.5
    return 1.0 if start <= time_range[1] and end >= time_range[0] else 0.0


def _cooccurrence_score(
    record: EntityRecord, others: set[str]
) -> float:
    return 1.0 if any(item.canonical in others for item in record.cooccurrence) else 0.0


def anchor_mentions(
    mentions: list[DetectedMention],
    records: list[EntityRecord],
    time_range: tuple[int, int] | None,
) -> list[AnchoredMention]:
    by_id = {record.entity_id: record for record in records}
    detected_canonicals = {
        candidate.canonical
        for mention in mentions
        for candidate in mention.candidates
    }
    anchored: list[AnchoredMention] = []
    for mention in mentions:
        scored: list[MentionCandidate] = []
        for candidate in mention.candidates:
            record = by_id[candidate.entity_id]
            others = detected_canonicals - {record.canonical}
            score = (
                0.70
                + 0.20 * _temporal_score(record, time_range)
                + 0.10 * _cooccurrence_score(record, others)
            )
            scored.append(candidate.model_copy(update={"score": round(score, 4)}))
        scored.sort(key=lambda item: -item.score)
        best = scored[0].score if scored else 0.0
        status: Status = (
            "anchored"
            if best >= ANCHOR_THRESHOLD
            else "candidate"
            if best >= CANDIDATE_THRESHOLD
            else "unresolved"
        )
        canonicals = (
            [candidate.canonical for candidate in scored]
            if status == "anchored"
            else []
        )
        anchored.append(
            AnchoredMention(
                text=mention.text,
                start=mention.start,
                end=mention.end,
                status=status,
                canonicals=canonicals,
                candidates=scored,
            )
        )
    return anchored
