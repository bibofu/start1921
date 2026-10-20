"""PostgreSQL connections with bound qmark parameters and named row access."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from types import TracebackType
from typing import Any, TypeAlias, overload

import psycopg

DATABASE_ERRORS = (psycopg.Error,)
INTEGRITY_ERRORS = (psycopg.IntegrityError,)
DatabaseTarget: TypeAlias = str
PDF_METADATA_COLUMNS = frozenset({"pdf_title", "pdf_author"})

_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")


def _sql_parts(sql: str) -> Iterator[tuple[bool, str]]:
    """Yield executable SQL separately from quoted text and comments."""

    position = 0
    plain_start = 0
    length = len(sql)
    while position < length:
        start = position
        character = sql[position]
        if sql.startswith("--", position):
            end = sql.find("\n", position + 2)
            position = length if end < 0 else end + 1
        elif sql.startswith("/*", position):
            position += 2
            depth = 1
            while position < length and depth:
                if sql.startswith("/*", position):
                    depth += 1
                    position += 2
                elif sql.startswith("*/", position):
                    depth -= 1
                    position += 2
                else:
                    position += 1
        elif character in "'\"":
            closing_quote = character
            # Backslash only escapes inside PostgreSQL E'...' literals.
            # Ordinary literals use doubled quote characters.
            escape_literal = (
                character == "'"
                and position > 0
                and sql[position - 1] in "eE"
                and (position < 2 or not (sql[position - 2].isalnum() or sql[position - 2] == "_"))
            )
            position += 1
            while position < length:
                if escape_literal and sql[position] == "\\":
                    position = min(length, position + 2)
                elif sql[position] == closing_quote:
                    position += 1
                    if position < length and sql[position] == closing_quote:
                        position += 1
                    else:
                        break
                else:
                    position += 1
        elif character == "$" and (
            position == 0 or not (sql[position - 1].isalnum() or sql[position - 1] in "_$")
        ):
            match = _DOLLAR_QUOTE.match(sql, position)
            if match is None:
                position += 1
                continue
            delimiter = match.group()
            end = sql.find(delimiter, match.end())
            position = length if end < 0 else end + len(delimiter)
        else:
            position += 1
            continue
        if start > plain_start:
            yield True, sql[plain_start:start]
        yield False, sql[start:position]
        plain_start = position
    if plain_start < length:
        yield True, sql[plain_start:]


def qmark_to_pyformat(sql: str) -> str:
    """Convert bind markers without changing question marks in SQL text.

    psycopg parses percent signs before PostgreSQL parses literals and comments,
    so *all* original percent signs must be doubled when parameters are passed.
    """

    return "".join(
        part.replace("%", "%%").replace("?", "%s") if executable else part.replace("%", "%%")
        for executable, part in _sql_parts(sql)
    )


def encode_pdf_metadata(value: str | None) -> bytes | None:
    """Encode opaque PDF strings without stripping embedded NUL characters."""

    return value.encode("utf-8") if value is not None else None


class Record:
    """A PostgreSQL row supporting field names, positions and value iteration."""

    __slots__ = ("_columns", "_indices", "_values")

    def __init__(self, columns: Sequence[str], values: Sequence[Any]) -> None:
        self._columns = tuple(columns)
        self._values = tuple(
            value.decode("utf-8")
            if column in PDF_METADATA_COLUMNS and isinstance(value, bytes)
            else value
            for column, value in zip(columns, values, strict=True)
        )
        self._indices: dict[str, int] = {}
        for index, column in enumerate(columns):
            # Duplicate names resolve to the first column, ignoring ASCII case.
            self._indices.setdefault(column.lower() if column.isascii() else column, index)

    def keys(self) -> list[str]:
        return list(self._columns)

    @overload
    def __getitem__(self, key: int | str) -> Any: ...

    @overload
    def __getitem__(self, key: slice) -> tuple[Any, ...]: ...

    def __getitem__(self, key: int | str | slice) -> Any:
        if isinstance(key, str):
            index = self._indices.get(key.lower() if key.isascii() else key)
            if index is None:
                raise IndexError("No item with that key")
            return self._values[index]
        return self._values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _record_factory(cursor: psycopg.Cursor[Any]) -> Callable[[Sequence[Any]], Record]:
    columns = tuple(column.name for column in cursor.description or ())
    return lambda values: Record(columns, values)


class PostgresConnection:
    """A transactional PostgreSQL connection accepting qmark bind markers."""

    def __init__(self, connection: psycopg.Connection[Record]) -> None:
        self.raw_connection = connection

    def execute(
        self, sql: str, parameters: Sequence[Any] | None = None
    ) -> psycopg.Cursor[Record]:
        if parameters is None:
            return self.raw_connection.execute(sql)
        return self.raw_connection.execute(qmark_to_pyformat(sql), parameters)

    def executemany(
        self, sql: str, parameters: Iterable[Sequence[Any]]
    ) -> psycopg.Cursor[Record]:
        cursor = self.raw_connection.cursor()
        cursor.executemany(qmark_to_pyformat(sql), parameters)
        return cursor

    def executescript(self, script: str) -> psycopg.Cursor[Record]:
        # No parameters: psycopg's simple-query path supports multiple statements.
        # Keep all statements within the caller's transaction.
        return self.raw_connection.execute(script, prepare=False)

    def commit(self) -> None:
        self.raw_connection.commit()

    def rollback(self) -> None:
        self.raw_connection.rollback()

    def close(self) -> None:
        self.raw_connection.close()

    def __enter__(self) -> PostgresConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


Connection: TypeAlias = PostgresConnection
Row: TypeAlias = Record


def is_postgres_target(target: DatabaseTarget) -> bool:
    return isinstance(target, str) and target.lower().startswith(("postgresql://", "postgres://"))


def connect_database(target: DatabaseTarget, *, timeout: float = 5.0) -> Connection:
    """Open a connection. Callers must close it, or use database_connection."""

    if not is_postgres_target(target):
        raise ValueError("A PostgreSQL connection URL is required")
    return PostgresConnection(
        psycopg.connect(
            target,
            row_factory=_record_factory,
            connect_timeout=max(1, math.ceil(timeout)),
        )
    )


@contextmanager
def database_connection(target: DatabaseTarget) -> Iterator[Connection]:
    """Commit successful work, roll back failures, and always close."""

    connection = connect_database(target)
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
