"""Dictionary mention detection and evidence-based entity anchoring.

This is the query-side entity layer. It never mutates the runtime person
filter catalog and never invents entities: unknown mentions stay unresolved.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
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


def _mention_from(
    alias: str, start: int, record: EntityRecord, by_id: dict[str, EntityRecord], score: float
) -> DetectedMention:
    members = (
        [by_id[member] for member in record.members if member in by_id]
        if record.type == "person_group"
        else [record]
    )
    return DetectedMention(
        text=alias,
        start=start,
        end=start + len(alias),
        candidates=[
            MentionCandidate(
                entity_id=member.entity_id,
                canonical=member.canonical,
                type=member.type,
                score=score,
            )
            for member in members
        ],
    )


def _fuzzy_mentions(
    query: str,
    aliases: list[tuple[str, EntityRecord]],
    by_id: dict[str, EntityRecord],
    covered: list[tuple[int, int]],
) -> list[DetectedMention]:
    matches: list[DetectedMention] = []
    for start in range(len(query)):
        if any(left <= start < right for left, right in covered):
            continue
        best: tuple[float, str, EntityRecord] | None = None
        for length in range(2, min(8, len(query) - start) + 1):
            window = query[start : start + length]
            if not re.fullmatch(r"[一-鿿A-Za-z0-9]+", window):
                continue
            for alias, record in aliases:
                if abs(len(alias) - length) > 2:
                    continue
                ratio = SequenceMatcher(None, window, alias).ratio()
                if ratio < 0.82:
                    continue
                if best is None or ratio > best[0]:
                    best = (ratio, window, record)
        if best is not None and not any(
            left <= start < right for left, right in covered
        ):
            ratio, window, record = best
            matches.append(_mention_from(window, start, record, by_id, round(ratio, 4)))
            covered.append((start, start + len(window)))
    return matches


def detect_mentions(
    query: str, records: list[EntityRecord], *, fuzzy: bool = False
) -> list[DetectedMention]:
    aliases = _alias_map(records)
    by_id = {record.entity_id: record for record in records}
    mentions: list[DetectedMention] = []
    covered: list[tuple[int, int]] = []
    index = 0
    while index < len(query):
        for alias, record in aliases:
            if not query.startswith(alias, index):
                continue
            mentions.append(_mention_from(alias, index, record, by_id, 1.0))
            covered.append((index, index + len(alias)))
            index += len(alias)
            break
        else:
            index += 1
    if fuzzy:
        mentions.extend(_fuzzy_mentions(query, aliases, by_id, covered))
    mentions.sort(key=lambda mention: mention.start)
    return mentions


def uncovered_spans(query: str, mentions: list[DetectedMention]) -> list[str]:
    """Return CJK/alnum runs not covered by a detected mention."""

    covered = [(mention.start, mention.end) for mention in mentions]
    spans: list[str] = []
    for match in re.finditer(r"[一-鿿A-Za-z0-9]{2,30}", query):
        start, end = match.span()
        cursor = start
        for left, right in sorted(covered):
            if right <= cursor or left >= end:
                continue
            if left > cursor:
                spans.append(query[cursor:left])
            cursor = max(cursor, right)
        if cursor < end:
            spans.append(query[cursor:end])
    return [span for span in dict.fromkeys(spans) if len(span) >= 2][:8]


PRONOUNS = ("他", "她", "它", "其", "该人", "此人", "该同志")


def resolve_followup(
    question: str, history: list[str] | None, records: list[EntityRecord]
) -> tuple[str, list[str]]:
    """Resolve a pronoun or a terse year-only follow-up from recent history."""

    if not history:
        return question, []
    inherited: list[str] = []
    for text in reversed(history):
        for mention in detect_mentions(text, records):
            for candidate in mention.candidates:
                if candidate.type == "person":
                    inherited.append(candidate.canonical)
        if inherited:
            break
    if not inherited:
        return question, []
    person = inherited[0]
    resolved = question
    if any(pronoun in question for pronoun in PRONOUNS):
        for pronoun in PRONOUNS:
            if pronoun in question:
                resolved = question.replace(pronoun, person, 1)
                break
    elif len(question) <= 12 and re.search(r"(?:18|19|20)\d{2}", question):
        resolved = f"{person} {question}"
    if resolved == question:
        return question, []
    return resolved, inherited


def entity_normalization_pairs(
    records: list[EntityRecord],
) -> list[tuple[str, str]]:
    """Alias -> query text, with canonical self-mappings to block substrings."""

    pairs: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    for record in records:
        if record.type == "person_group":
            members = [member for member in record.members]
            by_id = {item.entity_id: item for item in records}
            text = " ".join(
                by_id[member].canonical for member in members if member in by_id
            )
            if not text:
                continue
        else:
            text = record.canonical
        for alias in {record.canonical, *record.aliases}:
            if not alias:
                continue
            if record.type in {"person", "place"} and len(alias) < 3:
                continue
            if record.type == "place":
                # Historical place names are time-specific (北平 vs 北京);
                # keep them for mention linking, not deterministic rewriting.
                continue
            if alias in seen:
                continue
            seen[alias] = text
            pairs.append((alias, text))
    return sorted(pairs, key=lambda item: (-len(item[0]), item[0]))


def normalize_entities(query: str, records: list[EntityRecord]) -> str:
    """Replace exact aliases with their canonical text using longest match."""

    pairs = entity_normalization_pairs(records)
    output: list[str] = []
    index = 0
    while index < len(query):
        for alias, canonical in pairs:
            if query.startswith(alias, index):
                output.append(canonical)
                index += len(alias)
                break
        else:
            output.append(query[index])
            index += 1
    return "".join(output)


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
