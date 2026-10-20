"""Explicit offline import of the original FTS5 keyword artifact.

Only this migration module and the legacy comparison backend read SQLite. The
PostgreSQL keyword builder and searcher do not use SQLite as a tokenizer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from history_agent.db_backend import is_postgres_target
from history_agent.errors import HistoryAgentError
from history_agent.processing.chunks import index_artifact_sha256
from history_agent.retrieval.keyword_postgres import (
    METADATA_COLUMNS,
    IndexedChunk,
    fingerprint_keyword_data,
    keyword_generation_fingerprint,
    publish_keyword_generation,
)


class KeywordMigrationError(HistoryAgentError):
    """A sanitized, actionable failure without connection credentials."""


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def _source(path: Path) -> Iterator[sqlite3.Connection]:
    path = path.resolve()
    if not path.is_file():
        raise KeywordMigrationError(f"Keyword source does not exist: {path}")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise KeywordMigrationError("Keyword source failed SQLite integrity_check.")
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(chunk_metadata)")
        )
        if set(columns) != set(METADATA_COLUMNS):
            raise KeywordMigrationError("Keyword source metadata schema is incompatible.")
        connection.execute(
            "CREATE VIRTUAL TABLE temp.keyword_migration_vocab "
            "USING fts5vocab(main, chunk_fts, instance)"
        )
        yield connection


def _decode_docsize(blob: bytes) -> list[int]:
    """Decode FTS5's SQLite varints, including the nine-byte form."""
    result: list[int] = []
    value = 0
    width = 0
    for byte in blob:
        width += 1
        value = (value << (8 if width == 9 else 7)) | (
            byte if width == 9 else byte & 0x7F
        )
        if width == 9 or not byte & 0x80:
            result.append(value)
            value = 0
            width = 0
    if width:
        raise KeywordMigrationError("Keyword source has a truncated FTS document size.")
    return result


def _chunks(connection: sqlite3.Connection) -> list[IndexedChunk]:
    columns = ", ".join(f'm."{column}"' for column in METADATA_COLUMNS)
    result: list[IndexedChunk] = []
    for row in connection.execute(
        f"SELECT f.rowid, m.rowid, {columns}, f.terms, d.sz "
        "FROM chunk_fts f JOIN chunk_metadata m ON m.chunk_id = f.chunk_id "
        "JOIN chunk_fts_docsize d ON d.id = f.rowid ORDER BY f.rowid"
    ):
        sizes = _decode_docsize(row[-1])
        if len(sizes) != 2 or sizes[0] != 0 or not isinstance(row[-2], str):
            raise KeywordMigrationError("Keyword source has incompatible FTS columns.")
        result.append(
            IndexedChunk(
                rowid=row[0],
                metadata_rowid=row[1],
                metadata=tuple(row[2:-2]),
                terms=row[-2],
                doc_length=sizes[1],
            )
        )
    metadata_count = connection.execute("SELECT count(*) FROM chunk_metadata").fetchone()[0]
    fts_count = connection.execute("SELECT count(*) FROM chunk_fts").fetchone()[0]
    sizes_count = connection.execute("SELECT count(*) FROM chunk_fts_docsize").fetchone()[0]
    if not metadata_count == fts_count == sizes_count == len(result):
        raise KeywordMigrationError("Keyword metadata, FTS rows and document sizes disagree.")
    if len({chunk.rowid for chunk in result}) != len(result):
        raise KeywordMigrationError("Keyword source has duplicate FTS identities.")
    return result


def _postings(connection: sqlite3.Connection) -> Iterator[tuple[str, int, list[int]]]:
    previous: tuple[int, str] | None = None
    positions: list[int] = []
    for term, rowid, column, position in connection.execute(
        "SELECT term, doc, col, offset FROM temp.keyword_migration_vocab "
        "ORDER BY doc, term COLLATE BINARY, offset"
    ):
        if column != "terms" or not isinstance(position, int):
            raise KeywordMigrationError("Keyword source lacks complete term positions.")
        key = rowid, term
        if key != previous:
            if previous is not None:
                yield previous[1], previous[0], positions
            previous = key
            positions = []
        positions.append(position)
    if previous is not None:
        yield previous[1], previous[0], positions


def _source_manifest(
    path: Path | None, *, actual_source_hash: str, snapshot_hash: str,
    source_artifact_hash: str | None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    warnings: list[str] = []
    source_report_verified = False
    if path is not None and path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        old_manifest = payload.get("manifest")
        if isinstance(old_manifest, dict):
            warnings = list(old_manifest.get("warnings") or [])
            source_report_verified = (
                source_artifact_hash is not None
                and old_manifest.get("index_artifact_sha256") == source_artifact_hash
            )
            if source_report_verified:
                allowed = (
                    "chunking", "chunk_artifact_sha256", "chunk_build_run_id",
                    "embedding_model", "vector_index_version", "git_commit",
                )
                manifest = {key: old_manifest[key] for key in allowed if key in old_manifest}
            else:
                warnings.append("Source report index hash is stale; actual source was hashed.")
    else:
        warnings.append("Source keyword build report is unavailable.")
    manifest.update(
        source_index_sha256=actual_source_hash,
        source_index_artifact_sha256=source_artifact_hash,
        source_snapshot_sha256=snapshot_hash,
        source_report_verified=source_report_verified,
        migration_source="sqlite-fts5-cjk-bigram-v1",
        warnings=warnings,
    )
    return manifest


def migrate_keyword_index(
    *,
    source_index: Path,
    target_url: str,
    backup_dir: Path,
    reports_dir: Path,
    run_id: str,
    source_report: Path | None = None,
) -> dict[str, Any]:
    """Copy a consistent source snapshot and atomically publish a verified PG index."""
    if not is_postgres_target(target_url):
        raise KeywordMigrationError("Keyword target must be a PostgreSQL URL.")
    started_at = datetime.now(UTC).isoformat()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = backup_dir.resolve() / f"keyword-to-postgres-{stamp}-{uuid4().hex[:8]}"
    snapshot = snapshot_dir / "keyword_fts.db"
    try:
        source_index = source_index.resolve()
        if not source_index.is_file():
            raise KeywordMigrationError(f"Keyword source does not exist: {source_index}")
        source_hash = _file_hash(source_index)
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        with (
            closing(sqlite3.connect(source_index.as_uri() + "?mode=ro", uri=True)) as source,
            closing(sqlite3.connect(snapshot)) as destination,
        ):
            source.backup(destination)
        if _file_hash(source_index) != source_hash:
            raise KeywordMigrationError(
                "Keyword source changed during snapshot; stop index writers."
            )
        snapshot_hash = _file_hash(snapshot)
        manifest = _source_manifest(
            source_report, actual_source_hash=source_hash, snapshot_hash=snapshot_hash,
            source_artifact_hash=index_artifact_sha256(source_index),
        )
        with _source(snapshot) as connection:
            chunks = _chunks(connection)
            expected = fingerprint_keyword_data(chunks, _postings(connection))
            published = publish_keyword_generation(
                target_url=target_url,
                chunks=chunks,
                postings=_postings(connection),
                run_id=run_id,
                started_at=started_at,
                manifest=manifest,
                expected_fingerprint=expected,
            )
        result = {
            "status": "verified",
            "source_index": str(source_index),
            "source_sha256": source_hash,
            "backup_directory": str(snapshot_dir),
            "snapshot": str(snapshot),
            "snapshot_sha256": snapshot_hash,
            "target_backend": "postgresql",
            **published,
        }
    except KeywordMigrationError:
        raise
    except Exception as exc:
        raise KeywordMigrationError(
            f"Keyword migration failed ({type(exc).__name__}); source and snapshots retained."
        ) from None
    # Publication has committed. A report I/O failure must not be described as a rollback.
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"keyword_migration_{run_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rendered = json.dumps(published["summary"], ensure_ascii=False, indent=2)
        (reports_dir / f"keyword_index_{run_id}.json").write_text(rendered, encoding="utf-8")
        (reports_dir / "keyword_index_latest.json").write_text(rendered, encoding="utf-8")
    except OSError as exc:
        raise KeywordMigrationError(
            f"Keyword index was published, but report writing failed ({type(exc).__name__})."
        ) from None
    return result


def verify_keyword_index(
    *, source_index: Path, target_url: str, generation_id: int | None = None
) -> dict[str, Any]:
    """Read both stores and compare every metadata field and positional posting."""
    if not is_postgres_target(target_url):
        raise KeywordMigrationError("Keyword target must be a PostgreSQL URL.")
    try:
        with _source(source_index) as connection:
            expected = fingerprint_keyword_data(_chunks(connection), _postings(connection))
        actual = keyword_generation_fingerprint(
            target_url=target_url, generation_id=generation_id
        )
        if expected != actual:
            raise KeywordMigrationError("Keyword metadata or positional postings differ.")
        return {"status": "verified", "target_backend": "postgresql", "fingerprint": actual}
    except KeywordMigrationError:
        raise
    except Exception as exc:
        raise KeywordMigrationError(
            f"Keyword verification failed ({type(exc).__name__})."
        ) from None
