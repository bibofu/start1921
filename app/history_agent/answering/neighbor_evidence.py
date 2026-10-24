"""Build adjacent-context evidence from the chunks next to a retrieved hit.

The model only sees a 420-character quote per evidence item, so a date or an
event detail that sits in the neighbouring chunk is invisible unless it becomes
its own evidence entry. These candidates are appended after the ranked hits and
never change retrieval order, so retrieval metrics stay comparable.
"""

from __future__ import annotations

from typing import Any

from history_agent.retrieval.chunk_store import ChunkNeighbourStore
from history_agent.retrieval.models import SearchHit

NEIGHBOUR_SCORE_DECAY = 0.5


def _record_hit(record: dict[str, Any], rank: int, score: float) -> SearchHit:
    page_start = int(record["pdf_page_start"])
    return SearchHit(
        rank=rank,
        chunk_id=str(record["chunk_id"]),
        document_id=str(record["document_id"]),
        title=str(record.get("title") or ""),
        filename=str(record.get("filename") or ""),
        volume=record.get("volume"),
        source_type=str(record.get("source_type") or ""),
        verification_status=str(record.get("verification_status") or ""),
        pdf_page_start=page_start,
        pdf_page_end=int(record.get("pdf_page_end") or page_start),
        section_path=[str(item) for item in record.get("section_path") or []],
        text=str(record.get("text") or ""),
        year_mentions=[int(item) for item in record.get("year_mentions") or []],
        people=[str(item) for item in record.get("people") or []],
        extraction_methods=[str(item) for item in record.get("extraction_methods") or []],
        score=round(score, 8),
        matched_terms=[],
    )


def neighbour_candidates(
    store: ChunkNeighbourStore,
    hits: list[SearchHit],
    *,
    limit: int,
) -> list[SearchHit]:
    """Adjacent chunks not already present in ``hits``, capped at ``limit``."""

    if limit <= 0 or not hits:
        return []
    seen = {hit.chunk_id for hit in hits}
    candidates: list[SearchHit] = []
    rank = len(hits)
    for hit in hits:
        for record in store.neighbours(hit.chunk_id, hit.document_id):
            chunk_id = str(record["chunk_id"])
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank += 1
            candidates.append(_record_hit(record, rank, hit.score * NEIGHBOUR_SCORE_DECAY))
            if len(candidates) >= limit:
                return candidates
    return candidates
