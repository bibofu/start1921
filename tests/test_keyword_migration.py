from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from history_agent.retrieval.keyword_migration import (
    KeywordMigrationError,
    _chunks,
    _decode_docsize,
    _postings,
    _source,
    _source_manifest,
    migrate_keyword_index,
    verify_keyword_index,
)
from history_agent.retrieval.keyword_postgres import METADATA_COLUMNS


@pytest.fixture
def keyword_migration_url() -> Iterator[str]:
    target = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    if not target:
        pytest.skip("Set HISTORY_AGENT_TEST_POSTGRES_URL for real keyword migration tests.")
    schema = "test_keyword_migration_" + uuid4().hex
    parsed = urlsplit(target)
    parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
    parameters["options"] = (parameters.get("options", "") + f" -csearch_path={schema}").strip()
    isolated = urlunsplit(parsed._replace(query=urlencode(parameters)))
    with psycopg.connect(target, autocommit=True) as connection:
        connection.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )
        try:
            yield isolated
        finally:
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


def _fixture_source(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        metadata_ddl = ", ".join(
            f'"{name}" {"INTEGER" if name.startswith("pdf_page_") else "TEXT"}'
            for name in METADATA_COLUMNS
        )
        connection.execute(f"CREATE TABLE chunk_metadata ({metadata_ddl})")
        connection.execute(
            "CREATE VIRTUAL TABLE chunk_fts USING fts5("
            "chunk_id UNINDEXED,terms,tokenize='unicode61 remove_diacritics 2')"
        )
        for number, terms in enumerate(("中国 中国 token-abc 3.14", "中国 革命", ""), 1):
            metadata: dict[str, Any] = {
                "chunk_id": f"chunk-{number}", "document_id": "document",
                "title": "原始标题\u0000", "filename": "source.pdf", "volume": None,
                "source_type": "history", "verification_status": "verified",
                "creators_json": '["毛泽东"]', "pdf_page_start": number,
                "pdf_page_end": number, "section_path_json": '["Section %_\\\\"]',
                "text": f"原文 {number}\u0000", "year_mentions_json": "[1949, 1950]",
                "scope_status": "in_scope", "people_json": '["毛泽东"]',
                "extraction_methods_json": '["text_layer"]',
            }
            values = [number * 10, *(metadata[name] for name in METADATA_COLUMNS)]
            connection.execute(
                "INSERT INTO chunk_metadata(rowid,"
                + ",".join(METADATA_COLUMNS)
                + ") VALUES ("
                + ",".join("?" for _ in values)
                + ")",
                values,
            )
            connection.execute(
                "INSERT INTO chunk_fts(rowid,chunk_id,terms) VALUES (?,?,?)",
                (number * 3, f"chunk-{number}", terms),
            )
        connection.commit()


def test_docsize_varints_and_truncation() -> None:
    assert _decode_docsize(bytes.fromhex("008159")) == [0, 217]
    assert _decode_docsize(bytes.fromhex("007f8100")) == [0, 127, 128]
    assert _decode_docsize(bytes.fromhex("ffffffffffffffffff")) == [2**64 - 1]
    with pytest.raises(KeywordMigrationError, match="truncated"):
        _decode_docsize(b"\x81")


def test_source_reads_exact_fts_positions_and_both_rowids(work_path: Path) -> None:
    path = work_path / "keyword.db"
    _fixture_source(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with _source(path) as connection:
        chunks = _chunks(connection)
        postings = list(_postings(connection))
    assert [chunk.rowid for chunk in chunks] == [3, 6, 9]
    assert [chunk.metadata_rowid for chunk in chunks] == [10, 20, 30]
    assert [chunk.doc_length for chunk in chunks] == [6, 2, 0]
    assert ("中国", 3, [0, 1]) in postings
    assert ("token", 3, [2]) in postings
    assert ("abc", 3, [3]) in postings
    assert ("3", 3, [4]) in postings
    assert ("14", 3, [5]) in postings
    assert chunks[0].metadata[METADATA_COLUMNS.index("title")] == "原始标题\u0000"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_source_rejects_unmatched_fts_record(work_path: Path) -> None:
    path = work_path / "keyword.db"
    _fixture_source(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "INSERT INTO chunk_fts(chunk_id,terms) VALUES ('orphan','orphan')"
        )
        connection.commit()
    with _source(path) as connection, pytest.raises(KeywordMigrationError, match="disagree"):
        _chunks(connection)


def test_keyword_migration_preserves_source_and_all_fields(
    work_path: Path, keyword_migration_url: str
) -> None:
    source = work_path / "keyword.db"
    _fixture_source(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = migrate_keyword_index(
        source_index=source, target_url=keyword_migration_url,
        backup_dir=work_path / "backups", reports_dir=work_path / "reports",
        run_id="test",
    )
    assert report["status"] == "verified"
    assert report["artifact_verified"] is True
    assert Path(report["snapshot"]).is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert keyword_migration_url not in str(report)
    assert (work_path / "reports/keyword_index_latest.json").is_file()
    verified = verify_keyword_index(source_index=source, target_url=keyword_migration_url)
    assert verified["status"] == "verified"
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("UPDATE chunk_metadata SET text='changed' WHERE rowid=10")
        connection.commit()
    with pytest.raises(KeywordMigrationError, match="differ"):
        verify_keyword_index(source_index=source, target_url=keyword_migration_url)


def test_migration_refuses_missing_source_without_exposing_credentials(work_path: Path) -> None:
    with pytest.raises(KeywordMigrationError, match="does not exist") as failure:
        migrate_keyword_index(
            source_index=work_path / "missing.db",
            target_url="postgresql://private:password@localhost/test",
            backup_dir=work_path / "backups", reports_dir=work_path / "reports",
            run_id="test",
        )
    assert "password" not in str(failure.value)


def test_manifest_uses_artifact_hash_and_does_not_promote_stale_provenance(
    work_path: Path,
) -> None:
    path = work_path / "report.json"
    path.write_text(
        json.dumps({"manifest": {
            "index_artifact_sha256": "artifact-hash",
            "chunk_artifact_sha256": "chunks-hash",
            "chunking": {"version": "frozen-chunker"},
            "git_commit": "source-code",
        }}),
        encoding="utf-8",
    )
    manifest = _source_manifest(
        path, actual_source_hash="raw-file-hash", snapshot_hash="snapshot-hash",
        source_artifact_hash="artifact-hash",
    )
    assert manifest["source_report_verified"] is True
    assert manifest["chunk_artifact_sha256"] == "chunks-hash"
    assert manifest["source_index_sha256"] == "raw-file-hash"
    stale = _source_manifest(
        path, actual_source_hash="raw-file-hash", snapshot_hash="snapshot-hash",
        source_artifact_hash="different-artifact-hash",
    )
    assert stale["source_report_verified"] is False
    assert "chunking" not in stale
    assert "chunk_artifact_sha256" not in stale
    assert "git_commit" not in stale
