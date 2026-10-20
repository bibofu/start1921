from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest
from history_agent import migration
from history_agent.answering.context import ConversationStore
from history_agent.db import SCHEMA, Database
from history_agent.migration import (
    MigrationError,
    migrate_sqlite_to_postgres,
    verify_sqlite_to_postgres,
)


@pytest.fixture
def postgres_url() -> Iterator[str]:
    """Only touch a uniquely created schema in an explicitly provided test DB."""
    url = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set HISTORY_AGENT_TEST_POSTGRES_URL for isolated PostgreSQL migration tests.")
    psycopg = pytest.importorskip("psycopg")
    schema = "test_migration_" + uuid4().hex
    parsed = urlsplit(url)
    parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
    parameters["options"] = (parameters.get("options", "") + f" -csearch_path={schema}").strip()
    isolated = urlunsplit(parsed._replace(query=urlencode(parameters)))
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )
        try:
            yield isolated
        finally:
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


def _insert(connection: Any, table: str, values: dict[str, Any]) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())
    )


def _sources(work_path: Path, *, legacy_column_order: bool = False) -> tuple[Path, Path]:
    main = work_path / "source-main.sqlite"
    conversations = work_path / "source-conversations.sqlite"
    database = Database(main)
    if legacy_column_order:
        schema = SCHEMA.replace("    subject_mention_text TEXT NOT NULL,\n", "").replace(
            "    object_mention_text TEXT,\n", ""
        )
        with closing(sqlite3.connect(main)) as connection:
            connection.executescript(schema)
            connection.execute(
                "ALTER TABLE person_relationships ADD COLUMN object_mention_text TEXT"
            )
            connection.execute(
                "ALTER TABLE person_relationships ADD COLUMN subject_mention_text TEXT NOT NULL"
            )
            connection.commit()
    database.initialize()
    stamp = "2026-10-20T01:02:03.456789+00:00"
    with database.connect() as connection:
        connection.execute("BEGIN")
        connection.execute("PRAGMA defer_foreign_keys = ON")
        _insert(
            connection,
            "documents",
            {
                "document_id": "doc_sample",
                "title": "迁移史料",
                "creators_json": '["甲", "乙"]',
                "source_type": "chronology",
                "source_series_json": "[]",
                "verification_status": "verified",
                "enabled": 1,
                "ocr_strategy": "auto",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        file = {
            "file_id": 41,
            "document_id": "doc_sample",
            "relative_path": "sample.pdf",
            "filename": "sample.pdf",
            "sha256": "a" * 64,
            "size_bytes": 2**40,
            "page_count": 10,
            "modified_at": stamp,
            "pdf_title": "原始\x00PDF标题",
            "pdf_author": "\x00作者甲\x00",
            "is_encrypted": 0,
            "first_seen_at": stamp,
            "last_seen_at": stamp,
        }
        _insert(connection, "document_files", file)
        _insert(connection, "document_files", {**file, "file_id": 99, "sha256": "b" * 64})
        connection.execute("DELETE FROM document_files WHERE file_id = 99")
        for person_id, target in (("person_a", "person_z"), ("person_z", None)):
            _insert(
                connection,
                "persons",
                {
                    "person_id": person_id,
                    "canonical_name": person_id,
                    "normalized_name": person_id,
                    "status": "merged" if target else "active",
                    "merged_into_person_id": target,
                    "created_at": stamp,
                    "updated_at": stamp,
                },
            )
        _insert(
            connection,
            "person_aliases",
            {
                "alias_id": 7,
                "person_id": "person_z",
                "alias_text": "某人",
                "normalized_alias": "某人",
                "alias_type": "name",
                "source": "manual",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        _insert(
            connection,
            "historical_events",
            {
                "event_id": "event_sample",
                "name": "月精度事件",
                "event_type": "meeting",
                "start_value": "1921-07",
                "start_precision": "month",
                "start_certainty": "exact",
                "start_original_text": "一九二一年七月",
                "organization_names_json": '["组织甲", "组织乙"]',
                "description": "带有Unicode的原文",
                "extraction_method": "manual",
                "extraction_confidence": 0.1234567890123456,
                "review_status": "unreviewed",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
        _insert(
            connection,
            "relation_types",
            {
                "relation_type": "held_position",
                "label": "任职",
                "object_kind": "organization",
                "extraction_policy": "allowed",
                "requires_human_review": 0,
                "requires_event": 0,
                "description": "迁移关系样例",
                "updated_at": stamp,
            },
        )
        _insert(
            connection,
            "person_relationships",
            {
                "relationship_id": "relationship_sample",
                "relation_type": "held_position",
                "subject_person_id": "person_z",
                "subject_mention_text": "某人",
                "object_mention_text": "组织甲",
                "organization_name": "组织甲",
                "role_title": "成员",
                "start_value": "1921",
                "start_precision": "year",
                "start_certainty": "approximate",
                "extraction_method": "manual",
                "extraction_confidence": 0.9876543210987654,
                "review_status": "unreviewed",
                "created_at": stamp,
                "updated_at": stamp,
            },
        )
    ConversationStore(conversations).append_exchange(
        "migration-session-1234", "私有聊天问题", "私有聊天回答。[E1]"
    )
    with closing(sqlite3.connect(conversations)) as connection:
        connection.execute(
            "INSERT INTO conversation_messages(message_id,session_id,role,content,created_at) "
            "VALUES (40,'migration-session-1234','assistant','deleted',?)",
            (stamp,),
        )
        connection.execute("DELETE FROM conversation_messages WHERE message_id = 40")
        connection.commit()
    return main, conversations


def test_sqlite_backup_includes_wal_without_changing_source(work_path: Path) -> None:
    source = work_path / "wal.sqlite"
    snapshot = work_path / "snapshot.sqlite"
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE example(value TEXT)")
        connection.execute("INSERT INTO example VALUES ('committed WAL row')")
        connection.commit()
        before = source.read_bytes()
        migration._snapshot(source, snapshot)
        assert source.read_bytes() == before
        with closing(sqlite3.connect(snapshot)) as copied:
            assert copied.execute("SELECT value FROM example").fetchone()[0] == "committed WAL row"
        with pytest.raises(FileExistsError):
            migration._snapshot(source, snapshot)


def test_migration_rejects_invalid_source_before_connecting(work_path: Path) -> None:
    main, conversations = _sources(work_path)
    with closing(sqlite3.connect(main)) as connection:
        connection.execute("UPDATE person_aliases SET person_id = 'missing_person'")
        connection.commit()
    with pytest.raises(MigrationError, match="foreign_key_check"):
        migrate_sqlite_to_postgres(
            source_database=main,
            source_conversations=conversations,
            target_url="postgresql://unused:secret@127.0.0.1:1/unused",
            backup_dir=work_path / "backups",
        )
    assert len(list((work_path / "backups").glob("*/main.sqlite"))) == 1


def test_migration_accepts_appended_columns_but_rejects_unknown_source_tables(
    work_path: Path,
) -> None:
    main, conversations = _sources(work_path, legacy_column_order=True)
    main_tables = migration._tables(SCHEMA, "main")
    with migration._readonly(main) as connection:
        migration._validate_source(connection, main_tables)
        actual = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(person_relationships)")
        )
    expected = next(table.columns for table in main_tables if table.name == "person_relationships")
    assert actual != expected
    assert set(actual) == set(expected)
    for path, tables in (
        (main, main_tables),
        (conversations, migration._tables(migration.CONVERSATION_SCHEMA, "conversations")),
    ):
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE unexpected_records(value TEXT)")
            connection.commit()
        with (
            migration._readonly(path) as connection,
            pytest.raises(MigrationError, match="unsupported application tables"),
        ):
            migration._validate_source(connection, tables)


def test_postgres_migration_preserves_every_field_and_identity(
    work_path: Path,
    postgres_url: str,
) -> None:
    main, conversations = _sources(work_path, legacy_column_order=True)
    original_hashes = [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in (main, conversations)
    ]
    report = migrate_sqlite_to_postgres(
        source_database=main,
        source_conversations=conversations,
        target_url=postgres_url,
        backup_dir=work_path / "backups",
    )
    assert report["status"] == "verified"
    assert len(report["tables"]) == len(migration._all_tables())
    assert all(row["source_sha256"] == row["target_sha256"] for row in report["tables"])
    assert all(row["source_count"] == row["target_count"] for row in report["tables"])
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in (main, conversations)] == (
        original_hashes
    )
    rendered = str(report)
    assert postgres_url not in rendered
    assert "私有聊天" not in rendered
    assert (
        verify_sqlite_to_postgres(
            source_database=Path(report["backups"]["main"]),
            source_conversations=Path(report["backups"]["conversations"]),
            target_url=postgres_url,
        )["status"]
        == "verified"
    )
    with Database(postgres_url).connect() as connection:
        event = connection.execute("SELECT * FROM historical_events").fetchone()
        assert event["start_value"] == "1921-07"
        assert event["extraction_confidence"] == 0.1234567890123456
        assert event["organization_names_json"] == '["组织甲", "组织乙"]'
        assert connection.execute("SELECT size_bytes FROM document_files").fetchone()[0] == 2**40
        metadata = connection.execute("SELECT pdf_title, pdf_author FROM document_files").fetchone()
        assert metadata["pdf_title"] == "原始\x00PDF标题"
        assert metadata["pdf_author"] == "\x00作者甲\x00"
        assert (
            connection.execute(
                "SELECT nextval(pg_get_serial_sequence('document_files', 'file_id'))"
            ).fetchone()[0]
            == 100
        )
        assert (
            connection.execute(
                "SELECT nextval(pg_get_serial_sequence('person_aliases', 'alias_id'))"
            ).fetchone()[0]
            == 8
        )
    ConversationStore(postgres_url).append_exchange("migration-session-1234", "下一问", "下一答")
    with Database(postgres_url).connect() as connection:
        assert (
            connection.execute("SELECT MAX(message_id) FROM conversation_messages").fetchone()[0]
            == 42
        )


def test_postgres_migration_refuses_existing_rows_and_verification_detects_changes(
    work_path: Path,
    postgres_url: str,
) -> None:
    main, conversations = _sources(work_path)
    arguments = {
        "source_database": main,
        "source_conversations": conversations,
        "target_url": postgres_url,
        "backup_dir": work_path / "backups",
    }
    migrate_sqlite_to_postgres(**arguments)
    with pytest.raises(MigrationError, match="not empty"):
        migrate_sqlite_to_postgres(**arguments)
    assert (
        verify_sqlite_to_postgres(
            source_database=main,
            source_conversations=conversations,
            target_url=postgres_url,
        )["status"]
        == "verified"
    )
    with Database(postgres_url).connect() as connection:
        connection.execute(
            "UPDATE conversation_messages SET content = ? WHERE message_id = 1",
            ("changed private content",),
        )
    with pytest.raises(MigrationError, match="conversation_messages") as error:
        verify_sqlite_to_postgres(
            source_database=main,
            source_conversations=conversations,
            target_url=postgres_url,
        )
    assert "private content" not in str(error.value)


def test_postgres_migration_failure_rolls_back_rows_and_sequence_restarts(
    work_path: Path,
    postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, conversations = _sources(work_path)
    reset = migration._reset_identity

    def fail_after_first_reset(target: Any, source: Any, table: Any) -> None:
        reset(target, source, table)
        if table.name == "document_files":
            raise MigrationError("Injected failure after transactional identity restart.")

    monkeypatch.setattr(migration, "_reset_identity", fail_after_first_reset)
    with pytest.raises(MigrationError, match="Injected failure"):
        migrate_sqlite_to_postgres(
            source_database=main,
            source_conversations=conversations,
            target_url=postgres_url,
            backup_dir=work_path / "backups",
        )
    with Database(postgres_url).connect() as connection:
        for table in migration._all_tables():
            assert connection.execute(f'SELECT COUNT(*) FROM "{table.name}"').fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT nextval(pg_get_serial_sequence('document_files', 'file_id'))"
            ).fetchone()[0]
            == 1
        )
