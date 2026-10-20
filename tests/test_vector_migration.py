from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from history_agent.config import QdrantServiceTarget
from history_agent.processing.chunks import index_artifact_sha256
from history_agent.retrieval.vector import COLLECTION_NAME, VECTOR_SIZE
from history_agent.retrieval.vector_migration import (
    VectorMigrationError,
    migrate_qdrant_local,
)


def _fixture(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Any, list[Any], bytes]:
    qdrant = pytest.importorskip("qdrant_client")
    from qdrant_client import models

    source_path = work_path / "source"
    source = qdrant.QdrantClient(path=str(source_path))
    source.create_collection(
        COLLECTION_NAME,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )
    points = [
        models.PointStruct(
            id=number,
            vector=[float(number), 1.0, *([0.0] * (VECTOR_SIZE - 2))],
            payload={"document_id": "文献甲", "text": f"原文 {number}", "years": [1921, 1949]},
        )
        for number in range(1, 9)
    ]
    source.upsert(COLLECTION_NAME, points)
    source.close()
    storage = source_path / "collection" / COLLECTION_NAME / "storage.sqlite"
    source_hash = hashlib.sha256(storage.read_bytes()).digest()
    destination = qdrant.QdrantClient(":memory:")
    destination.create_collection(
        "retained",
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )
    destination.update_collection_aliases(
        [
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name="retained", alias_name=COLLECTION_NAME
                )
            )
        ]
    )

    def open_client(target: Any) -> Any:
        if isinstance(target, Path):
            return qdrant.QdrantClient(path=str(target))
        return destination

    monkeypatch.setattr(
        "history_agent.retrieval.vector_migration.open_vector_client", open_client
    )
    monkeypatch.setattr(destination, "close", lambda: None)
    return source_path, destination, points, source_hash


def test_migration_copies_vectors_and_publishes_alias_without_embedding(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path, destination, points, source_hash = _fixture(work_path, monkeypatch)

    def forbidden_embedding(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Existing vector migration must not invoke the embedding model.")

    monkeypatch.setattr("history_agent.retrieval.vector._embedding_model", forbidden_embedding)
    source_report = work_path / "source_report.json"
    source_report.write_text(
        json.dumps(
            {
                "model_name": "BAAI/bge-small-zh-v1.5",
                "vector_size": VECTOR_SIZE,
                "manifest": {
                    "index_artifact_sha256": index_artifact_sha256(source_path),
                    "chunk_artifact_sha256": "existing-chunks",
                    "build_run_id": "original",
                },
            }
        ),
        encoding="utf-8",
    )
    report = migrate_qdrant_local(
        source_path=source_path,
        target=QdrantServiceTarget("http://test.invalid", api_key="must-not-appear"),
        reports_dir=work_path / "reports",
        run_id="vector-test",
        batch_size=3,
        source_report=source_report,
    )
    assert report["copied_count"] == report["target_count"] == len(points)
    assert report["previous_collection"] == "retained"
    assert report["verification"]["sample_ids"] == [1, 2, 3, 6, 7, 8]
    assert report["verification"]["sample_payloads_equal"]
    assert report["verification"]["sample_vectors_equal_within_tolerance"]
    assert report["embeddings_recomputed"] is False
    manifest = report["summary"]["manifest"]
    assert manifest["source_manifest_verified"] is True
    assert manifest["index_artifact_sha256"] is None
    assert manifest["source_index_artifact_sha256"] == index_artifact_sha256(source_path)
    assert manifest["chunk_artifact_sha256"] == "existing-chunks"
    assert manifest["source_build_run_id"] == "original"
    assert destination.count(COLLECTION_NAME, exact=True).count == len(points)
    assert destination.collection_exists("retained")
    storage = source_path / "collection" / COLLECTION_NAME / "storage.sqlite"
    assert hashlib.sha256(storage.read_bytes()).digest() == source_hash
    rendered = (work_path / "reports/qdrant_migration_latest.json").read_text(encoding="utf-8")
    assert json.loads(rendered) == report
    assert "test.invalid" not in rendered
    assert "must-not-appear" not in rendered


def test_migration_does_not_publish_unverified_points(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path, destination, _, _ = _fixture(work_path, monkeypatch)
    retrieve = destination.retrieve

    def corrupt_sample(**kwargs: Any) -> Any:
        points = retrieve(**kwargs)
        points[0].payload = {"text": "altered"}
        return points

    monkeypatch.setattr(destination, "retrieve", corrupt_sample)
    with pytest.raises(VectorMigrationError, match="payload differs"):
        migrate_qdrant_local(
            source_path=source_path,
            target=QdrantServiceTarget("http://test.invalid"),
            reports_dir=work_path / "reports",
            run_id="vector-test",
        )
    aliases = destination.get_aliases().aliases
    assert [(alias.alias_name, alias.collection_name) for alias in aliases] == [
        (COLLECTION_NAME, "retained")
    ]
    assert len(destination.get_collections().collections) == 2


def test_migration_redacts_connection_errors(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path, _, _, _ = _fixture(work_path, monkeypatch)

    def connection_error(target: Any) -> None:
        raise RuntimeError("http://user:password@example.invalid/?api_key=secret")

    monkeypatch.setattr(
        "history_agent.retrieval.vector_migration.open_vector_client", connection_error
    )
    with pytest.raises(VectorMigrationError) as error:
        migrate_qdrant_local(
            source_path=source_path,
            target=QdrantServiceTarget("http://test.invalid"),
            reports_dir=work_path / "reports",
            run_id="vector-test",
        )
    assert "RuntimeError" in str(error.value)
    assert "password" not in str(error.value)
    assert "secret" not in str(error.value)
