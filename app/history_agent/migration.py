"""Explicit, verified SQLite-to-PostgreSQL migration of application records.

The keyword and vector indexes are deliberately outside this migration. Stop
application writers before migrating: each SQLite backup is consistent, but two
separate SQLite files cannot share a single atomic snapshot.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from history_agent.answering.context import CONVERSATION_SCHEMA, ConversationStore
from history_agent.db import SCHEMA, Database
from history_agent.db_backend import is_postgres_target
from history_agent.errors import HistoryAgentError


class MigrationError(HistoryAgentError):
    """Migration could not safely copy or verify all application records."""


@dataclass(frozen=True)
class _Table:
    name: str
    columns: tuple[str, ...]
    identity: str | None
    source: str


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _tables(schema: str, source: str) -> list[_Table]:
    names = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema)
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.executescript(schema)
        result = []
        for name in names:
            columns = tuple(
                row[1] for row in connection.execute(f"PRAGMA table_info({_quoted(name)})")
            )
            ddl = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
            ).fetchone()[0]
            identity = re.search(r"(\w+)\s+INTEGER PRIMARY KEY AUTOINCREMENT", ddl)
            result.append(_Table(name, columns, identity[1] if identity else None, source))
        return result


def _all_tables() -> list[_Table]:
    return [*_tables(SCHEMA, "main"), *_tables(CONVERSATION_SCHEMA, "conversations")]


@contextmanager
def _readonly(path: Path) -> Iterator[sqlite3.Connection]:
    path = path.resolve()
    if not path.is_file():
        raise MigrationError(f"SQLite source does not exist: {path}")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


def _validate_source(connection: sqlite3.Connection, tables: list[_Table]) -> None:
    checks = connection.execute("PRAGMA integrity_check").fetchall()
    if checks != [("ok",)]:
        raise MigrationError("SQLite source failed integrity_check.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise MigrationError("SQLite source failed foreign_key_check.")
    source_tables = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if not str(row[0]).startswith("sqlite_")
    }
    if source_tables - {table.name for table in tables}:
        raise MigrationError("SQLite source contains unsupported application tables.")
    for table in tables:
        columns = tuple(
            row[1] for row in connection.execute(f"PRAGMA table_info({_quoted(table.name)})")
        )
        # Historical SQLite upgrades append columns with ALTER TABLE, so their
        # physical order can differ from fresh DDL. Copy/hash uses explicit order.
        if set(columns) != set(table.columns):
            raise MigrationError(f"SQLite source schema does not match table {table.name}.")


def _snapshot(source: Path, destination: Path) -> None:
    # Exclusive creation also prevents accidentally overwriting any source file.
    with destination.open("xb"):
        pass
    with _readonly(source) as original:
        backup = sqlite3.connect(destination)
        try:
            original.backup(backup)
        finally:
            backup.close()


def _cell(value: Any) -> list[Any]:
    if value is None:
        return ["null"]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MigrationError("A source or target contains a non-finite numeric value.")
        return ["real", value.hex()]
    if isinstance(value, str):
        return ["text", value]
    if isinstance(value, bytes):
        return ["blob", value.hex()]
    raise MigrationError("A source or target contains an unsupported field type.")


def _summary(connection: Any | None, table: _Table) -> dict[str, Any]:
    """Hash all fields, independent of database collation and returned row order."""
    row_hashes: list[bytes] = []
    if connection is not None:
        columns = ", ".join(_quoted(column) for column in table.columns)
        cursor = connection.execute(f"SELECT {columns} FROM {_quoted(table.name)}")
        while rows := cursor.fetchmany(1000):
            for row in rows:
                encoded = json.dumps(
                    [_cell(row[index]) for index in range(len(table.columns))],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                row_hashes.append(hashlib.sha256(encoded).digest())
    digest = hashlib.sha256()
    digest.update(json.dumps(table.columns, separators=(",", ":")).encode("utf-8"))
    for row_hash in sorted(row_hashes):
        digest.update(row_hash)
    return {"count": len(row_hashes), "sha256": digest.hexdigest()}


def _compare(
    sources: dict[str, sqlite3.Connection | None],
    target: Any,
    tables: list[_Table],
) -> list[dict[str, Any]]:
    results = []
    for table in tables:
        source_summary = _summary(sources[table.source], table)
        target_summary = _summary(target, table)
        if source_summary != target_summary:
            raise MigrationError(f"Source/target count or full-field hash mismatch: {table.name}.")
        results.append(
            {
                "source": table.source,
                "table": table.name,
                "source_count": source_summary["count"],
                "target_count": target_summary["count"],
                "source_sha256": source_summary["sha256"],
                "target_sha256": target_summary["sha256"],
            }
        )
    return results


def _reset_identity(target: Any, source: sqlite3.Connection | None, table: _Table) -> None:
    if table.identity is None:
        return
    sequence = target.execute(
        "SELECT n.nspname, c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.oid = pg_get_serial_sequence(?, ?)::regclass",
        (table.name, table.identity),
    ).fetchone()
    if sequence is None:
        raise MigrationError(f"PostgreSQL identity sequence is missing: {table.name}.")
    maximum = target.execute(
        f"SELECT COALESCE(MAX({_quoted(table.identity)}), 0) FROM {_quoted(table.name)}"
    ).fetchone()[0]
    high_water = 0
    if source is not None:
        row = source.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = ?", (table.name,)
        ).fetchone()
        high_water = int(row[0]) if row else 0
    next_id = max(int(maximum), high_water, 0) + 1
    qualified = f"{_quoted(sequence[0])}.{_quoted(sequence[1])}"
    # ALTER SEQUENCE RESTART is transactional; setval() would escape rollback.
    target.execute(f"ALTER SEQUENCE {qualified} RESTART WITH {next_id}")


def migrate_sqlite_to_postgres(
    *,
    source_database: Path,
    source_conversations: Path | None,
    target_url: str,
    backup_dir: Path,
) -> dict[str, Any]:
    """Back up and import both stores into one empty PostgreSQL database.

    Returns only paths, table names, counts and hashes; connection credentials and
    record contents never enter the report. Existing destination rows are refused.
    Schema creation is idempotent; all copied rows and sequence resets share one
    transaction. Backups are retained if validation or import fails.
    """
    if not is_postgres_target(target_url):
        raise MigrationError("Migration target must be a PostgreSQL URL.")
    tables = _all_tables()
    originals = {"main": source_database, "conversations": source_conversations}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = backup_dir.resolve() / f"sqlite-to-postgres-{stamp}-{uuid4().hex[:8]}"
    snapshots: dict[str, Path | None] = {"main": None, "conversations": None}
    try:
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        for name, path in originals.items():
            if path is not None:
                destination = snapshot_dir / f"{name}.sqlite"
                _snapshot(path, destination)
                snapshots[name] = destination
        with ExitStack() as stack:
            sources: dict[str, sqlite3.Connection | None] = {}
            for name, path in snapshots.items():
                source = stack.enter_context(_readonly(path)) if path is not None else None
                sources[name] = source
                if source is not None:
                    _validate_source(source, [table for table in tables if table.source == name])
            Database(target_url).initialize()
            ConversationStore(target_url).initialize()
            with Database(target_url).connect() as target:
                names = ", ".join(_quoted(table.name) for table in tables)
                target.execute(f"LOCK TABLE {names} IN ACCESS EXCLUSIVE MODE")
                for table in tables:
                    target_columns = tuple(
                        row[0]
                        for row in target.execute(
                            "SELECT attname FROM pg_attribute "
                            "WHERE attrelid = ?::regclass AND attnum > 0 AND NOT attisdropped "
                            "ORDER BY attnum",
                            (table.name,),
                        ).fetchall()
                    )
                    if set(target_columns) != set(table.columns):
                        raise MigrationError(
                            f"PostgreSQL target schema does not match table {table.name}."
                        )
                    count_row = target.execute(
                        f"SELECT COUNT(*) FROM {_quoted(table.name)}"
                    ).fetchone()
                    if count_row is None:
                        raise MigrationError(f"Could not inspect target table: {table.name}.")
                    if count_row[0]:
                        raise MigrationError(f"PostgreSQL target table is not empty: {table.name}.")
                target.execute("SET CONSTRAINTS ALL DEFERRED")
                for table in tables:
                    source = sources[table.source]
                    if source is None:
                        continue
                    columns = ", ".join(_quoted(column) for column in table.columns)
                    placeholders = ", ".join("?" for _ in table.columns)
                    cursor = source.execute(f"SELECT {columns} FROM {_quoted(table.name)}")
                    while rows := cursor.fetchmany(1000):
                        if table.name == "document_files":
                            # PDF metadata may contain NUL characters. PostgreSQL
                            # stores these two fields as UTF-8 BYTEA; its row
                            # adapter restores the original strings for hashing.
                            rows = [
                                tuple(
                                    value.encode("utf-8")
                                    if column in {"pdf_title", "pdf_author"}
                                    and isinstance(value, str)
                                    else value
                                    for column, value in zip(table.columns, row, strict=True)
                                )
                                for row in rows
                            ]
                        target.executemany(
                            f"INSERT INTO {_quoted(table.name)} ({columns}) "
                            f"VALUES ({placeholders})",
                            rows,
                        )
                results = _compare(sources, target, tables)
                target.execute("SET CONSTRAINTS ALL IMMEDIATE")
                for table in tables:
                    _reset_identity(target, sources[table.source], table)
        return {
            "status": "verified",
            "target_backend": "postgresql",
            "backup_directory": str(snapshot_dir),
            "sources": {
                name: str(path.resolve()) if path is not None else None
                for name, path in originals.items()
            },
            "backups": {
                name: str(path) if path is not None else None for name, path in snapshots.items()
            },
            "tables": results,
        }
    except MigrationError:
        raise
    except Exception as exc:
        # Driver exception details may contain a URL or an offending chat value.
        raise MigrationError(
            f"PostgreSQL migration failed ({type(exc).__name__}); "
            "no imported rows were committed. Backups, if created, were retained."
        ) from None


def verify_sqlite_to_postgres(
    *,
    source_database: Path,
    source_conversations: Path | None,
    target_url: str,
) -> dict[str, Any]:
    """Read-only full-field verification, suitable for checking saved backups."""
    if not is_postgres_target(target_url):
        raise MigrationError("Verification target must be a PostgreSQL URL.")
    tables = _all_tables()
    paths = {"main": source_database, "conversations": source_conversations}
    try:
        with ExitStack() as stack:
            sources: dict[str, sqlite3.Connection | None] = {}
            for name, path in paths.items():
                source = stack.enter_context(_readonly(path)) if path is not None else None
                sources[name] = source
                if source is not None:
                    source.execute("BEGIN")
                    _validate_source(source, [table for table in tables if table.source == name])
            with Database(target_url).connect() as target:
                target.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                results = _compare(sources, target, tables)
        return {"status": "verified", "target_backend": "postgresql", "tables": results}
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError(f"PostgreSQL verification failed ({type(exc).__name__}).") from None
