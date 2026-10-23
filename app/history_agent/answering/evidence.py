"""Request-scoped, source-preserving evidence for research tasks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from llama_index.core.schema import MetadataMode, NodeWithScore, TextNode

from history_agent.answering.models import Citation
from history_agent.retrieval.llamaindex import node_to_search_hit, search_hit_to_node
from history_agent.retrieval.models import SearchHit

WHITESPACE = re.compile(r"\s+")
TRUNCATED_LEADING_MONTH = re.compile(
    r"^(?P<prefix>……)?\s*\d{1,2}\s*月(?!\s*(?:\d{1,2}\s*日|上旬|中旬|下旬))"
)


def _compact(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def _clean_quote_start(text: str) -> str:
    """Remove a month token cut off from its day/context at a chunk boundary."""

    match = TRUNCATED_LEADING_MONTH.match(text)
    if match is None:
        return text
    prefix = match["prefix"] or ""
    return prefix + text[match.end() :].lstrip()


def quote_for_hit(
    hit: SearchHit,
    query_terms: list[str],
    limit: int = 420,
    *,
    query_people: list[str] | None = None,
) -> str:
    text = _compact(hit.text)
    people = set(query_people or [])
    if len(people) == 1:
        position = text.find(next(iter(people)))
        if position > 0:
            window_start = max(0, position - 180)
            boundary = max(text.rfind(mark, window_start, position) for mark in "。！？；")
            if boundary >= window_start:
                text = "……" + text[boundary + 1 :]
    if len(text) <= limit:
        return _clean_quote_start(text)
    person_positions = [
        match.start() for person in people for match in re.finditer(re.escape(person), text)
    ]
    positions = person_positions or [text.find(term) for term in query_terms if len(term) >= 2]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    if len(people) == 2:
        mentions = sorted(
            (match.start(), match.end(), person)
            for person in people
            for match in re.finditer(re.escape(person), text)
        )
        # Center the quote on the closest pair of mentions, not the first occurrence
        # of a common keyword. Proximity selects context; it does not prove interaction.
        pairs = [
            (right[1] - left[0], left[0], right[1])
            for left, right in zip(mentions, mentions[1:], strict=False)
            if left[2] != right[2] and right[1] - left[0] <= limit
        ]
        if pairs:
            _, center, pair_end = min(pairs)
            # Keep the preceding event context, including when a roster is at the
            # end of the passage. A short tail alone can lose which meeting it names.
            window_start = max(0, pair_end - limit, min(center - 110, len(text) - limit))
            boundaries = [text.find(mark, window_start, center) for mark in "。！？；"]
            boundary = min((position for position in boundaries if position >= 0), default=-1)
            start = boundary + 1 if boundary >= 0 else window_start
            end = min(len(text), start + limit)
            return _clean_quote_start(
                ("……" if start else "") + text[start:end] + ("……" if end < len(text) else "")
            )
    window_start = max(0, center - 180)
    boundaries = [text.rfind(mark, window_start, center) for mark in "。！？；"]
    boundary = max(boundaries)
    if boundary >= window_start:
        start = boundary + 1
    else:
        date_context_start = max(0, window_start - 40)
        date_matches = list(
            re.finditer(
                r"(?:(?:18|19|20)\d{2}\s*年\s*)?\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
                text[date_context_start:center],
            )
        )
        start = date_context_start + date_matches[-1].start() if date_matches else window_start
    end = min(len(text), start + limit)
    prefix = "……" if start else ""
    suffix = "……" if end < len(text) else ""
    return _clean_quote_start(f"{prefix}{text[start:end]}{suffix}")


@dataclass(frozen=True)
class CollectedEvidence:
    citation: Citation
    source_key: str
    raw_text: str
    finding: str = ""


@dataclass
class EvidenceCollection:
    status: Literal["completed", "empty", "unavailable", "not_applicable", "ambiguous", "failed"]
    items: list[CollectedEvidence] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    content: str | None = None
    error_code: str | None = None
    total: int = 0
    source_title: str | None = None


@dataclass
class _RegisteredEvidence:
    citation: Citation
    node: NodeWithScore
    task_ids: list[str]
    excerpts: list[str]


class EvidenceRegistry:
    """Assign stable request-local IDs without replacing source text by summaries."""

    def __init__(self) -> None:
        self._by_id: dict[str, _RegisteredEvidence] = {}
        self._by_source: dict[str, str] = {}

    def __len__(self) -> int:
        return len(self._by_id)

    def register_citation(
        self,
        citation: Citation,
        task_id: str,
        source_key: str,
        raw_text: str | None = None,
        *,
        node: NodeWithScore | None = None,
    ) -> Citation:
        raw = raw_text if raw_text is not None else citation.quote
        # A source may yield multiple independent spans. Keep both rather than
        # silently overwriting one with a later, shorter excerpt.
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        key = f"{source_key}:{digest}"
        existing_id = self._by_source.get(key)
        if existing_id is not None:
            existing = self._by_id[existing_id]
            if task_id not in existing.task_ids:
                existing.task_ids.append(task_id)
            if citation.quote not in existing.excerpts:
                existing.excerpts.append(citation.quote)
                existing.citation = existing.citation.model_copy(
                    update={"quote": "\n……\n".join(existing.excerpts)}
                )
            existing.node.node.metadata["task_ids"] = list(existing.task_ids)
            return existing.citation.model_copy(deep=True)
        evidence_id = f"E{len(self._by_id) + 1}"
        registered = citation.model_copy(update={"evidence_id": evidence_id}, deep=True)
        if node is None:
            node = NodeWithScore(node=TextNode(id_=source_key, text=raw, metadata={}), score=None)
        else:
            node = node.model_copy(deep=True)
        node.node.metadata.update(
            {
                "evidence_id": evidence_id,
                "source_key": source_key,
                "document_id": citation.document_id,
                "title": citation.document,
                "volume": citation.volume,
                "pdf_page_start": citation.pdf_page,
                "pdf_page_end": citation.pdf_page_end or citation.pdf_page,
                "section_path": list(citation.section),
                "source_type": citation.source_type,
                "verification_status": citation.verification_status,
                "extraction_methods": list(citation.extraction_methods),
                "year_mentions": list(citation.year_mentions),
                "task_ids": [task_id],
            }
        )
        self._by_id[evidence_id] = _RegisteredEvidence(
            registered, node, [task_id], [citation.quote]
        )
        self._by_source[key] = evidence_id
        return registered.model_copy(deep=True)

    def register_hit(self, hit: SearchHit, task_id: str, quote: str | None = None) -> Citation:
        return self.register_node(search_hit_to_node(hit), task_id, quote)

    def register_node(
        self, node: NodeWithScore, task_id: str, quote: str | None = None
    ) -> Citation:
        """Accept the actual postprocessed node, preserving its text and metadata."""
        hit = node_to_search_hit(node, rank=1)
        citation = Citation(
            evidence_id="E1",
            document_id=hit.document_id,
            document=hit.title,
            volume=hit.volume,
            pdf_page=hit.pdf_page_start,
            pdf_page_end=hit.pdf_page_end,
            section=hit.section_path,
            quote=quote if quote is not None else hit.text,
            source_type=hit.source_type,
            verification_status=hit.verification_status,
            extraction_methods=hit.extraction_methods,
            year_mentions=hit.year_mentions,
        )
        return self.register_citation(
            citation,
            task_id,
            f"chunk:{hit.chunk_id}",
            hit.text,
            node=node,
        )

    def citations(self, evidence_ids: list[str] | None = None) -> list[Citation]:
        ids = self._by_id if evidence_ids is None else dict.fromkeys(evidence_ids)
        return [self._by_id[item].citation.model_copy(deep=True) for item in ids]

    def nodes(self, evidence_ids: list[str] | None = None) -> list[NodeWithScore]:
        ids = self._by_id if evidence_ids is None else dict.fromkeys(evidence_ids)
        return [self._by_id[item].node.model_copy(deep=True) for item in ids]

    def raw_text(self, evidence_id: str) -> str:
        return self._by_id[evidence_id].node.node.get_content(metadata_mode=MetadataMode.NONE)

    def contains(self, evidence_id: str) -> bool:
        return evidence_id in self._by_id


LEADING_ENTITY = re.compile(
    r"^(?:请问|我想知道|想知道|帮我查)?(?P<entity>[\u3400-\u4dbf\u4e00-\u9fff·]{2,18})"
    r"(?:在|于)(?=(?:18|19|20)\d{2}年)"
)
ENTITY_SEPARATOR = re.compile(r"[、和与]")


def unsupported_leading_entity(question: str, hits: list[SearchHit]) -> str | None:
    match = LEADING_ENTITY.search(question.strip())
    if match is None:
        return None
    entities = [entity for entity in ENTITY_SEPARATOR.split(match.group("entity")) if entity]
    for entity in entities:
        if not any(
            entity in hit.title
            or entity in hit.text
            or any(entity in part for part in hit.section_path)
            for hit in hits
        ):
            return entity
    return None
