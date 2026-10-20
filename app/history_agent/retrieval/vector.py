from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from history_agent.config import QdrantServiceTarget
from history_agent.errors import IndexBuildError, RetrievalError
from history_agent.processing.chunks import index_artifact_manifest, load_person_aliases
from history_agent.processing.models import ChunkRecord
from history_agent.retrieval.keyword import (
    YEAR,
    hard_filter_people,
    has_explicit_year_range,
    infer_query_intent,
    infer_year_range,
    load_chunks,
)
from history_agent.retrieval.models import (
    RetrievalPlan,
    SearchHit,
    SearchResponse,
    VectorIndexSummary,
)
from history_agent.retrieval.qdrant_http import QdrantServiceClient

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
VECTOR_SIZE = 512
COLLECTION_NAME = "history_chunks"
INDEX_VERSION = "qdrant-service-fastembed-v1"
VectorIndexTarget = QdrantServiceTarget


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def open_vector_client(target: VectorIndexTarget) -> QdrantServiceClient:
    """Connect only to the configured Qdrant HTTP service."""
    if not isinstance(target, QdrantServiceTarget):
        raise RetrievalError("Vector storage requires a Qdrant service target.")
    return QdrantServiceClient(target)


def publish_vector_collection(client: Any, collection_name: str) -> None:
    """Switch the serving alias in one operation; retain the previous collection."""

    aliases = client.get_aliases().aliases
    operations: list[dict[str, Any]] = []
    if any(alias.alias_name == COLLECTION_NAME for alias in aliases):
        operations.append({"delete_alias": {"alias_name": COLLECTION_NAME}})
    elif client.collection_exists(COLLECTION_NAME):
        raise IndexBuildError(
            "The serving name is a physical Qdrant collection. Preserve it and migrate "
            "to a versioned collection plus alias before rebuilding."
        )
    operations.append({
        "create_alias": {"collection_name": collection_name, "alias_name": COLLECTION_NAME}
    })
    client.update_collection_aliases(change_aliases_operations=operations)


@lru_cache(maxsize=2)
def _embedding_model(model_cache_dir: Path) -> Any:
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise IndexBuildError(
            "Embedding dependencies are missing. Run: uv sync --extra vector --group dev"
        ) from exc
    model_cache_dir.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(
        model_name=MODEL_NAME,
        cache_dir=str(model_cache_dir),
        threads=max(1, min(8, os.cpu_count() or 1)),
    )


def _embedding_text(record: ChunkRecord) -> str:
    section = " > ".join(record.section_path)
    return f"{record.title}\n{section}\n{record.text}".strip()


def _payload(record: ChunkRecord) -> dict[str, Any]:
    return {
        "chunk_id": record.chunk_id,
        "document_id": record.document_id,
        "title": record.title,
        "filename": record.filename,
        "volume": record.volume,
        "source_type": record.source_type,
        "verification_status": record.verification_status,
        "creators": record.creators,
        "pdf_page_start": record.pdf_page_start,
        "pdf_page_end": record.pdf_page_end,
        "section_path": record.section_path,
        "text": record.text,
        "year_mentions": record.year_mentions,
        "scope_status": record.scope_status,
        "people": record.people,
        "extraction_methods": record.extraction_methods,
    }


def build_vector_index(
    *,
    chunks_dir: Path,
    index_path: VectorIndexTarget,
    model_cache_dir: Path,
    reports_dir: Path,
    run_id: str,
    batch_size: int = 64,
    project_root: Path | None = None,
) -> VectorIndexSummary:
    started_at = utc_now()
    records = load_chunks(chunks_dir)
    if not records:
        raise IndexBuildError("No chunks are available for vector indexing.")
    embedding_model = _embedding_model(model_cache_dir)
    collection_name = f"{COLLECTION_NAME}_{uuid.uuid4().hex}"
    client = open_vector_client(index_path)
    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={"size": VECTOR_SIZE, "distance": "Cosine"},
        )
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            vectors = list(
                embedding_model.embed(
                    [_embedding_text(record) for record in batch],
                    batch_size=batch_size,
                )
            )
            points = [
                {
                    "id": str(uuid.UUID(record.chunk_id)),
                    "vector": vector.tolist(),
                    "payload": _payload(record),
                }
                for record, vector in zip(batch, vectors, strict=True)
            ]
            client.upsert(collection_name=collection_name, points=points, wait=True)
        count = client.count(collection_name=collection_name, exact=True).count
        if count != len(records):
            raise IndexBuildError(
                f"Vector index count mismatch: expected {len(records)}, found {count}."
            )
        publish_vector_collection(client, collection_name)
    finally:
        client.close()
    try:
        fastembed_version = version("fastembed")
    except PackageNotFoundError:
        fastembed_version = "unknown"
    index_version = f"{INDEX_VERSION}; fastembed={fastembed_version}; transport=http"
    manifest = index_artifact_manifest(
        chunks_dir=chunks_dir,
        reports_dir=reports_dir,
        project_root=project_root or reports_dir.parents[1],
        run_id=run_id,
        vector_index_version=index_version,
        embedding_model=MODEL_NAME,
    )
    manifest.update(
        vector_storage_backend="qdrant-service",
        vector_collection=collection_name,
    )
    summary = VectorIndexSummary(
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now(),
        index_version=index_version,
        model_name=MODEL_NAME,
        vector_size=VECTOR_SIZE,
        documents=len({record.document_id for record in records}),
        chunks=len(records),
        collection_name=COLLECTION_NAME,
        index_path=str(index_path),
        size_bytes=0,
        manifest=manifest,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    rendered = summary.model_dump_json(indent=2)
    (reports_dir / f"vector_index_{run_id}.json").write_text(rendered, encoding="utf-8")
    (reports_dir / "vector_index_latest.json").write_text(rendered, encoding="utf-8")
    return summary


def _query_filter(
    *,
    document_ids: list[str] | None,
    query_people: list[str],
    query_year_range: list[int],
    include_out_of_scope: bool,
) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    must_not: list[dict[str, Any]] = []
    if document_ids:
        must.append({"key": "document_id", "match": {"any": document_ids}})
    for person in query_people:
        must.append({"key": "people", "match": {"value": person}})
    if query_year_range:
        must.append({
            "key": "year_mentions",
            "range": {"gte": query_year_range[0], "lte": query_year_range[1]},
        })
    if not include_out_of_scope:
        must_not.append({"key": "scope_status", "match": {"value": "out_of_scope"}})
    return {"must": must or None, "must_not": must_not or None}


def search_vector_index(
    *,
    index_path: VectorIndexTarget,
    model_cache_dir: Path,
    aliases_path: Path,
    query: str,
    top_k: int = 10,
    document_ids: list[str] | None = None,
    include_out_of_scope: bool = False,
    plan: RetrievalPlan | None = None,
) -> SearchResponse:
    aliases = load_person_aliases(aliases_path)
    query_people = (
        plan.query_people
        if plan is not None
        else sorted(
            person
            for person, names in aliases.items()
            if person in query or any(alias in query for alias in names)
        )
    )
    query_intent = plan.query_intent if plan is not None else infer_query_intent(query)
    filter_people = hard_filter_people(query_people, query_intent)
    query_years = (
        plan.query_years
        if plan is not None
        else sorted({int(match.group(1)) for match in YEAR.finditer(query)})
    )
    query_year_range = (
        plan.query_year_range if plan is not None else infer_year_range(query, query_years)
    )
    explicit_year_range = bool(plan and plan.query_year_range) or has_explicit_year_range(query)
    embedding_model = _embedding_model(model_cache_dir)
    query_vector = next(iter(embedding_model.query_embed(query)))
    # Chronologies often mention nearby years in the body. Fetch a wider candidate
    # pool for exact-year timeline questions, then prefer the year heading in the
    # recovered document structure over incidental year mentions.
    candidate_limit = top_k
    prefer_section_year = bool(
        query_years and not explicit_year_range and query_intent == "timeline"
    )
    if prefer_section_year:
        candidate_limit = min(500, max(100, top_k * 20))
    client = open_vector_client(index_path)
    try:
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector.tolist(),
            query_filter=_query_filter(
                document_ids=document_ids,
                query_people=filter_people,
                query_year_range=query_year_range,
                include_out_of_scope=include_out_of_scope,
            ),
            limit=candidate_limit,
            with_payload=True,
            # Preserve the established exact nearest-neighbor scan.
            search_params={"exact": True},
        )
    finally:
        client.close()
    points = list(response.points)
    if prefer_section_year:
        section_matches: list[Any] = []
        other_matches: list[Any] = []
        expected = set(query_years)
        for point in points:
            payload = point.payload or {}
            section_path = [str(item) for item in payload.get("section_path", [])]
            section_years = {
                int(match.group(1)) for section in section_path for match in YEAR.finditer(section)
            }
            target = section_matches if expected.intersection(section_years) else other_matches
            target.append(point)
        points = [*section_matches, *other_matches]
    hits: list[SearchHit] = []
    for rank, point in enumerate(points[:top_k], start=1):
        payload = point.payload or {}
        hits.append(
            SearchHit(
                rank=rank,
                chunk_id=str(payload["chunk_id"]),
                document_id=str(payload["document_id"]),
                title=str(payload["title"]),
                filename=str(payload["filename"]),
                volume=payload.get("volume"),
                source_type=str(payload["source_type"]),
                verification_status=str(payload["verification_status"]),
                pdf_page_start=int(payload["pdf_page_start"]),
                pdf_page_end=int(payload["pdf_page_end"]),
                section_path=list(payload.get("section_path", [])),
                text=str(payload["text"]),
                year_mentions=list(payload.get("year_mentions", [])),
                people=list(payload.get("people", [])),
                extraction_methods=list(payload.get("extraction_methods", [])),
                score=round(float(point.score), 6),
                matched_terms=[],
            )
        )
    return SearchResponse(
        query=query,
        query_intent=query_intent,
        query_terms=[],
        query_years=query_years,
        query_year_range=query_year_range,
        query_people=query_people,
        document_filters=document_ids or [],
        include_out_of_scope=include_out_of_scope,
        hits=hits,
        retrieval_mode="vector",
    )
