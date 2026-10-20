from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

_SERVICE_ENVIRONMENT = pytest.StashKey[pytest.MonkeyPatch]()


def _isolate_service_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "postgresql://test:test@127.0.0.1:1/isolated_test"
    for name in ("DATABASE_URL", "CONVERSATION_DATABASE_URL", "KEYWORD_DATABASE_URL"):
        monkeypatch.setenv(f"HISTORY_AGENT_{name}", target)
    monkeypatch.setenv("HISTORY_AGENT_QDRANT_URL", "http://127.0.0.1:1")


def pytest_configure(config: pytest.Config) -> None:
    """Isolate imports which construct the web application during collection."""
    environment = pytest.MonkeyPatch()
    _isolate_service_environment(environment)
    config.stash[_SERVICE_ENVIRONMENT] = environment


def pytest_unconfigure(config: pytest.Config) -> None:
    environment = config.stash.get(_SERVICE_ENVIRONMENT, None)
    if environment is not None:
        environment.undo()


@pytest.fixture(autouse=True)
def isolated_service_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Never let a test reuse service settings cached by collection or another test."""
    from history_agent.config import get_settings

    _isolate_service_environment(monkeypatch)
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture
def postgres_target() -> Iterator[str]:
    """Use a new schema in the explicitly configured PostgreSQL test database."""
    target = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    if not target:
        pytest.skip("Set HISTORY_AGENT_TEST_POSTGRES_URL to an isolated PostgreSQL test database")
    schema = f"test_history_{uuid4().hex}"
    with psycopg.connect(target, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    parsed = urlsplit(target)
    parameters = dict(parse_qsl(parsed.query))
    parameters["options"] = f"{parameters.get('options', '')} -csearch_path={schema}".strip()
    try:
        yield urlunsplit(parsed._replace(query=urlencode(parameters)))
    finally:
        with psycopg.connect(target, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def postgres_settings(
    postgres_target: str,
    isolated_service_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """Enable real storage only for tests which explicitly request this fixture."""
    for name in ("DATABASE_URL", "CONVERSATION_DATABASE_URL", "KEYWORD_DATABASE_URL"):
        monkeypatch.setenv(f"HISTORY_AGENT_{name}", postgres_target)
    return postgres_target


@pytest.fixture
def work_path(request: pytest.FixtureRequest) -> Iterator[Path]:
    """Use a workspace-local test directory without pytest's Windows chmod behavior."""

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", request.node.name)
    path = Path.cwd() / "data" / "test-work" / safe_name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    yield path
    if path.exists():
        shutil.rmtree(path)
