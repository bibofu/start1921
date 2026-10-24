from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from history_agent.answering.neighbor_evidence import neighbour_candidates
from history_agent.retrieval.chunk_store import ChunkNeighbourStore
from history_agent.retrieval.models import SearchHit


def _record(
    chunk_id: str,
    *,
    previous: str | None = None,
    next_id: str | None = None,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": "doc",
        "title": "文献",
        "filename": "doc.pdf",
        "volume": None,
        "source_type": "chronology",
        "verification_status": "verified",
        "pdf_page_start": page,
        "pdf_page_end": page,
        "section_path": ["1956年"],
        "text": f"{chunk_id} 正文",
        "year_mentions": [1956],
        "people": ["周恩来"],
        "extraction_methods": ["pymupdf"],
        "previous_chunk_id": previous,
        "next_chunk_id": next_id,
    }


def _write(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
        encoding="utf8",
    )


def _hit(chunk_id: str, rank: int, page: int = 1) -> SearchHit:
    return SearchHit(
        rank=rank,
        chunk_id=chunk_id,
        document_id="doc",
        title="文献",
        filename="doc.pdf",
        source_type="chronology",
        verification_status="verified",
        pdf_page_start=page,
        pdf_page_end=page,
        section_path=[],
        text=f"{chunk_id} 正文",
        year_mentions=[],
        people=[],
        extraction_methods=[],
        score=1.0,
        matched_terms=[],
    )


def test_store_reads_neighbours_from_one_document(tmp_path: Path) -> None:
    _write(
        tmp_path / "doc.jsonl",
        [
            _record("c1", next_id="c2", page=1),
            _record("c2", previous="c1", next_id="c3", page=2),
            _record("c3", previous="c2", page=3),
        ],
    )
    store = ChunkNeighbourStore(tmp_path)

    neighbours = store.neighbours("c2", "doc")

    assert [item["chunk_id"] for item in neighbours] == ["c1", "c3"]


def test_store_rejects_unsafe_document_ids(tmp_path: Path) -> None:
    store = ChunkNeighbourStore(tmp_path)

    assert store.document("../secret") == {}


def test_store_evicts_old_documents(tmp_path: Path) -> None:
    _write(tmp_path / "doc.jsonl", [_record("c1")])
    _write(tmp_path / "other.jsonl", [_record("d1")])
    store = ChunkNeighbourStore(tmp_path, max_documents=1)

    store.document("doc")
    store.document("other")

    assert list(store._cache) == ["other"]


def test_neighbour_candidates_skip_hits_already_returned(tmp_path: Path) -> None:
    _write(
        tmp_path / "doc.jsonl",
        [
            _record("c1", next_id="c2", page=1),
            _record("c2", previous="c1", next_id="c3", page=2),
            _record("c3", previous="c2", page=3),
        ],
    )
    store = ChunkNeighbourStore(tmp_path)

    candidates = neighbour_candidates(store, [_hit("c1", 1), _hit("c2", 2)], limit=4)

    assert [item.chunk_id for item in candidates] == ["c3"]
    assert candidates[0].rank == 3
    assert candidates[0].score == 0.5


def test_neighbour_candidates_respect_the_limit(tmp_path: Path) -> None:
    _write(
        tmp_path / "doc.jsonl",
        [
            _record("c1", next_id="c2", page=1),
            _record("c2", previous="c1", next_id="c3", page=2),
            _record("c3", previous="c2", next_id="c4", page=3),
            _record("c4", previous="c3", page=4),
        ],
    )
    store = ChunkNeighbourStore(tmp_path)

    candidates = neighbour_candidates(store, [_hit("c2", 1)], limit=2)

    assert [item.chunk_id for item in candidates] == ["c1", "c3"]


def test_neighbour_candidates_are_empty_when_disabled(tmp_path: Path) -> None:
    _write(tmp_path / "doc.jsonl", [_record("c1", next_id="c2"), _record("c2")])
    store = ChunkNeighbourStore(tmp_path)

    assert neighbour_candidates(store, [_hit("c1", 1)], limit=0) == []


def test_neighbour_hits_keep_their_own_page_and_metadata(tmp_path: Path) -> None:
    _write(tmp_path / "doc.jsonl", [_record("c1", next_id="c2", page=1), _record("c2", page=2)])
    store = ChunkNeighbourStore(tmp_path)

    candidate = neighbour_candidates(store, [_hit("c1", 1, page=1)], limit=1)[0]

    assert candidate.pdf_page_start == 2
    assert candidate.document_id == "doc"
    assert candidate.people == ["周恩来"]
