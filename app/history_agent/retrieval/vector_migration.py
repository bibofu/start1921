"""One-time import of a preserved local Qdrant snapshot into the service."""

from __future__ import annotations

import json
import math
import re
import uuid
from collections import deque
from contextlib import suppress
from importlib.metadata import version
from pathlib import Path
from typing import Any

from history_agent.config import QdrantServiceTarget
from history_agent.errors import HistoryAgentError
from history_agent.processing.chunks import index_artifact_sha256
from history_agent.retrieval.models import VectorIndexSummary
from history_agent.retrieval.vector import (
    COLLECTION_NAME,
    MODEL_NAME,
    SERVICE_INDEX_VERSION,
    VECTOR_SIZE,
    open_vector_client,
    publish_vector_collection,
    utc_now,
)


class VectorMigrationError(HistoryAgentError):
    """A vector import could not be safely completed."""


def _source_manifest(source_path: Path, source_report: Path | None) -> dict[str, Any]:
    source_hash = index_artifact_sha256(source_path)
    manifest: dict[str, Any] = {}
    verified = False
    if source_report is not None:
        payload = json.loads(source_report.read_text(encoding="utf-8"))
        original = payload.get("manifest")
        if isinstance(original, dict) and original.get("index_artifact_sha256") == source_hash:
            if payload.get("model_name") != MODEL_NAME or payload.get("vector_size") != VECTOR_SIZE:
                raise VectorMigrationError("Source report has an incompatible embedding model.")
            manifest = dict(original)
            verified = True
    warnings = list(manifest.get("warnings") or [])
    if not verified:
        warnings.append(
            "Source report provenance could not be verified against the local snapshot."
        )
    warnings.append(
        "Service import was checked by exact count and six boundary point samples; "
        "no full service artifact hash was computed."
    )
    warnings.append("Service storage size is not reported; summary size_bytes is 0.")
    manifest.update(
        {
            "source_index_artifact_sha256": source_hash,
            "source_manifest_verified": verified,
            "source_build_run_id": manifest.get("build_run_id"),
            "source_vector_index_version": manifest.get("vector_index_version"),
            "index_artifact_sha256": None,
            "embedding_model": MODEL_NAME,
            "warnings": warnings,
        }
    )
    return manifest


def _check_sample(expected: Any, actual: Any) -> float:
    if expected.id != actual.id or expected.payload != actual.payload:
        raise VectorMigrationError("Vector sample ID or payload differs after import.")
    before, after = expected.vector, actual.vector
    if (
        not isinstance(before, list)
        or not isinstance(after, list)
        or len(before) != VECTOR_SIZE
        or len(after) != VECTOR_SIZE
    ):
        raise VectorMigrationError("Vector sample dimensions differ after import.")
    if not all(math.isfinite(value) for value in [*before, *after]):
        raise VectorMigrationError("Vector sample contains non-finite values.")
    # Qdrant service normalizes Cosine vectors; older local snapshots can retain
    # their original length. Compare directions after applying the same operation.
    before_norm = math.sqrt(sum(value * value for value in before)) or 1.0
    after_norm = math.sqrt(sum(value * value for value in after)) or 1.0
    maximum_error = 0.0
    for left, right in zip(before, after, strict=True):
        left, right = left / before_norm, right / after_norm
        if not math.isclose(left, right, rel_tol=1e-5, abs_tol=1e-6):
            raise VectorMigrationError("Vector sample values differ after import.")
        maximum_error = max(maximum_error, abs(left - right))
    return maximum_error


def migrate_qdrant_local(
    *,
    source_path: Path,
    target: QdrantServiceTarget,
    reports_dir: Path,
    run_id: str,
    batch_size: int = 256,
    source_report: Path | None = None,
) -> dict[str, Any]:
    """Copy existing vectors without embedding, verify, then atomically publish.

    ``source_path`` must be a consistent directory snapshot made while the
    original local client is closed. This importer never deletes either store.
    Failed imports retain the unpublished physical collection for inspection.
    """

    if not isinstance(target, QdrantServiceTarget):
        raise VectorMigrationError("Vector migration target must be a Qdrant service.")
    if not source_path.is_dir() or not (source_path / "meta.json").is_file():
        raise VectorMigrationError("A preserved local Qdrant snapshot is required.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", run_id):
        raise VectorMigrationError("Migration run ID must use letters, digits, '-' or '_'.")
    if batch_size < 1 or batch_size > 1024:
        raise VectorMigrationError("Migration batch size must be between 1 and 1024.")

    started_at = utc_now()
    physical_collection = f"{COLLECTION_NAME}_import_{uuid.uuid4().hex}"
    source = destination = None
    published = False
    try:
        from qdrant_client import models

        manifest = _source_manifest(source_path, source_report)
        source = open_vector_client(source_path)
        source_info = source.get_collection(COLLECTION_NAME)
        vectors_config = source_info.config.params.vectors
        if (
            not isinstance(vectors_config, models.VectorParams)
            or vectors_config.size != VECTOR_SIZE
            or vectors_config.distance != models.Distance.COSINE
        ):
            raise VectorMigrationError("Source must have unnamed 512-dimensional Cosine vectors.")
        expected_count = source.count(collection_name=COLLECTION_NAME, exact=True).count
        if expected_count == 0:
            raise VectorMigrationError("Source vector collection is empty.")

        destination = open_vector_client(target)
        previous_alias = next(
            (
                alias.collection_name
                for alias in destination.get_aliases().aliases
                if alias.alias_name == COLLECTION_NAME
            ),
            None,
        )
        if previous_alias is None and destination.collection_exists(COLLECTION_NAME):
            raise VectorMigrationError(
                "The serving name is an existing physical collection; "
                "preserve it and choose a separate service before importing."
            )
        destination.create_collection(
            collection_name=physical_collection, vectors_config=vectors_config
        )
        copied = 0
        documents: set[str] = set()
        first: list[Any] = []
        last: deque[Any] = deque(maxlen=3)
        offset = None
        while True:
            points, next_offset = source.scroll(
                collection_name=COLLECTION_NAME,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not points:
                if next_offset is not None:
                    raise VectorMigrationError("Source scrolling stopped before its final page.")
                break
            destination.upsert(
                collection_name=physical_collection,
                points=[
                    models.PointStruct(id=point.id, payload=point.payload, vector=point.vector)
                    for point in points
                ],
                wait=True,
            )
            for point in points:
                if len(first) < 3:
                    first.append(point)
                last.append(point)
                if point.payload and isinstance(point.payload.get("document_id"), str):
                    documents.add(point.payload["document_id"])
            copied += len(points)
            if next_offset is None:
                break
            if next_offset == offset:
                raise VectorMigrationError("Source scrolling repeated an offset.")
            offset = next_offset

        target_count = destination.count(
            collection_name=physical_collection, exact=True
        ).count
        final_source_count = source.count(collection_name=COLLECTION_NAME, exact=True).count
        if not copied == expected_count == final_source_count == target_count:
            raise VectorMigrationError(
                f"Vector counts disagree: source={expected_count}, copied={copied}, "
                f"source_after={final_source_count}, destination={target_count}."
            )
        samples = {point.id: point for point in [*first, *last]}
        received = destination.retrieve(
            collection_name=physical_collection,
            ids=list(samples),
            with_payload=True,
            with_vectors=True,
        )
        actual_samples = {point.id: point for point in received}
        if samples.keys() != actual_samples.keys():
            raise VectorMigrationError("Destination is missing sampled vector IDs.")
        maximum_error = max(
            _check_sample(expected, actual_samples[point_id])
            for point_id, expected in samples.items()
        )
        index_version = f"{SERVICE_INDEX_VERSION}; qdrant={version('qdrant-client')}"
        manifest.update(
            {
                "build_run_id": run_id,
                "vector_index_version": index_version,
                "physical_collection": physical_collection,
            }
        )
        summary = VectorIndexSummary(
            run_id=run_id,
            started_at=started_at,
            finished_at=utc_now(),
            index_version=index_version,
            model_name=MODEL_NAME,
            vector_size=VECTOR_SIZE,
            documents=len(documents),
            chunks=copied,
            collection_name=COLLECTION_NAME,
            index_path=f"qdrant-service:{COLLECTION_NAME}",
            size_bytes=0,
            manifest=manifest,
        )
        publish_vector_collection(destination, physical_collection)
        published = True
        result = {
            "status": "verified",
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": utc_now(),
            "source_snapshot": str(source_path.resolve()),
            "source_collection": COLLECTION_NAME,
            "target_backend": "qdrant-service",
            "collection_alias": COLLECTION_NAME,
            "physical_collection": physical_collection,
            "previous_collection": previous_alias,
            "embedding_model": MODEL_NAME,
            "embeddings_recomputed": False,
            "vector_size": VECTOR_SIZE,
            "distance": "Cosine",
            "documents": len(documents),
            "source_count": expected_count,
            "copied_count": copied,
            "target_count": target_count,
            "summary": summary.model_dump(mode="json"),
            "verification": {
                "counts_equal": True,
                "sample_ids": list(samples),
                "sample_payloads_equal": True,
                "sample_vectors_equal_within_tolerance": True,
                "sample_vectors_comparison": "cosine-normalized",
                "vector_absolute_tolerance": 1e-6,
                "vector_relative_tolerance": 1e-5,
                "maximum_sample_vector_absolute_error": maximum_error,
            },
        }
    except VectorMigrationError:
        raise
    except Exception as exc:
        raise VectorMigrationError(
            f"Vector migration failed ({type(exc).__name__}); "
            f"source and destination collections retained. "
            f"Unpublished import collection: {physical_collection}."
        ) from None
    finally:
        for client in (source, destination):
            if client is not None:
                # Closing an HTTP transport cannot undo a published alias.
                with suppress(Exception):
                    client.close()

    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        (reports_dir / f"qdrant_migration_{run_id}.json").write_text(
            rendered, encoding="utf-8"
        )
        (reports_dir / "qdrant_migration_latest.json").write_text(rendered, encoding="utf-8")
        rendered_summary = summary.model_dump_json(indent=2)
        (reports_dir / f"vector_index_{run_id}.json").write_text(
            rendered_summary, encoding="utf-8"
        )
        (reports_dir / "vector_index_latest.json").write_text(
            rendered_summary, encoding="utf-8"
        )
    except OSError as exc:
        raise VectorMigrationError(
            f"Vector alias was published={published}, but writing its migration report failed "
            f"({type(exc).__name__})."
        ) from None
    return result
