"""Lazy access to chunk neighbours for evidence-time context expansion.

Retrieval ranks pages; the model only ever sees the 420-character quote of each
selected chunk. A date or an event detail often sits in the chunk next door, so
delivery-time expansion needs the neighbouring chunk text. Loading every chunk
file would cost hundreds of megabytes, so this store loads one document at a
time and keeps a small LRU cache.
"""

from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

SAFE_DOCUMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class ChunkNeighbourStore:
    """Read ``previous_chunk_id`` / ``next_chunk_id`` records by document."""

    def __init__(self, chunks_dir: Path, *, max_documents: int = 3) -> None:
        self.chunks_dir = chunks_dir
        self._max_documents = max(1, max_documents)
        self._cache: OrderedDict[str, dict[str, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()

    def document(self, document_id: str) -> dict[str, dict[str, Any]]:
        if SAFE_DOCUMENT_ID.fullmatch(document_id) is None:
            return {}
        with self._lock:
            cached = self._cache.get(document_id)
            if cached is not None:
                self._cache.move_to_end(document_id)
                return cached
        records = self._load(document_id)
        with self._lock:
            self._cache[document_id] = records
            self._cache.move_to_end(document_id)
            while len(self._cache) > self._max_documents:
                self._cache.popitem(last=False)
        return records

    def _load(self, document_id: str) -> dict[str, dict[str, Any]]:
        path = self.chunks_dir / f"{document_id}.jsonl"
        if not path.is_file():
            return {}
        records: dict[str, dict[str, Any]] = {}
        with path.open(encoding="utf8") as handle:
            for line in handle:
                record = json.loads(line)
                records[str(record["chunk_id"])] = record
        return records

    def neighbours(self, chunk_id: str, document_id: str) -> list[dict[str, Any]]:
        records = self.document(document_id)
        record = records.get(chunk_id)
        if record is None:
            return []
        found: list[dict[str, Any]] = []
        for key in ("previous_chunk_id", "next_chunk_id"):
            neighbour = records.get(str(record.get(key) or ""))
            if neighbour is not None:
                found.append(neighbour)
        return found


_STORES: OrderedDict[str, ChunkNeighbourStore] = OrderedDict()
_STORES_LOCK = threading.Lock()


def neighbour_store(chunks_dir: Path) -> ChunkNeighbourStore:
    """One store per chunks directory, shared across requests."""

    key = str(chunks_dir.resolve())
    with _STORES_LOCK:
        store = _STORES.get(key)
        if store is None:
            store = ChunkNeighbourStore(chunks_dir)
            _STORES[key] = store
        _STORES.move_to_end(key)
        while len(_STORES) > 2:
            _STORES.popitem(last=False)
        return store
