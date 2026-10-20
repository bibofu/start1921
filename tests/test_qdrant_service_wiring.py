from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from history_agent import cli
from history_agent.answering.llamaindex_workflow import _search_kwargs
from history_agent.config import Settings
from history_agent.errors import RetrievalError
from history_agent.evaluation import answers, golden
from history_agent.retrieval.models import SearchResponse
from history_agent.web import app as web_module
from history_agent.web import readiness
from typer.testing import CliRunner


def _settings(work_path: Path) -> Settings:
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        qdrant_url="http://127.0.0.1:6333",
        qdrant_api_key="test-secret",
    )
    settings.vector_index_path.mkdir(parents=True)
    settings.reports_dir.mkdir(parents=True)
    (settings.reports_dir / "vector_index_latest.json").write_text(
        json.dumps({
            "index_version": "stale-local-index",
            "manifest": {"index_artifact_sha256": "stale-local-hash"},
        }),
        encoding="utf-8",
    )
    return settings


def test_workflow_and_cli_use_service_target(monkeypatch, work_path: Path) -> None:
    settings = _settings(work_path)
    assert _search_kwargs(settings, None)["vector_index_path"] == settings.vector_index_target
    captured: dict[str, Any] = {}

    def search(**kwargs: Any) -> SearchResponse:
        captured.update(kwargs)
        return SearchResponse(
            query=kwargs["query"], query_intent="general", query_terms=[],
            query_years=[], query_year_range=[], query_people=[], document_filters=[],
            include_out_of_scope=False, hits=[], retrieval_mode="vector",
        )

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "search_vector_index", search)
    result = CliRunner().invoke(cli.app, ["search-vector", "中国共产党", "--json"])
    assert result.exit_code == 0, result.output
    assert captured["index_path"] == settings.vector_index_target
    assert "test-secret" not in result.output


@pytest.mark.parametrize("available", [False, True])
def test_health_probes_service_even_with_local_directory(
    monkeypatch, work_path: Path, available: bool,
) -> None:
    settings = _settings(work_path)
    calls: list[object] = []

    class Client:
        def get_collection(self, name: str) -> None:
            calls.append(name)
            if not available:
                raise RetrievalError("unavailable")

        def close(self) -> None:
            calls.append("closed")

    def open_client(target: object) -> Client:
        assert target == settings.vector_index_target
        return Client()

    monkeypatch.setattr(readiness, "open_vector_client", open_client)
    monkeypatch.setattr(web_module, "_database_ready", lambda target: True)
    response = TestClient(web_module.create_app(settings)).get("/api/health")
    assert response.json()["indexes"]["vector"] is available
    assert response.json()["vector_database_backend"] == "qdrant-service"
    assert calls == ["history_chunks", "closed"]
    assert "test-secret" not in response.text


def test_readiness_searches_service_target(monkeypatch, work_path: Path) -> None:
    settings = _settings(work_path)
    captured: dict[str, Any] = {}

    def search(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(readiness, "_database_ready", lambda target: True)
    monkeypatch.setattr(readiness, "keyword_index_ready", lambda target: True)
    monkeypatch.setattr(readiness, "search_vector_index", search)
    result = readiness.readiness_snapshot(settings)
    assert result["components"]["vector"] is True
    assert captured["index_path"] == settings.vector_index_target


def test_service_metadata_never_reuses_local_hash(monkeypatch, work_path: Path) -> None:
    settings = _settings(work_path)

    def reject_local_hash(path: Path) -> str:
        raise AssertionError("the old local directory cannot identify a Qdrant service collection")

    monkeypatch.setattr(golden, "index_artifact_sha256", reject_local_hash)
    metadata = golden._load_index_metadata(settings)
    vector_metadata = metadata["reports"]["vector_index"]
    assert vector_metadata["artifact_verified"] is False
    assert vector_metadata["actual_index_artifact_sha256"] is None
    assert vector_metadata["manifest"] is None
    assert any("Qdrant service" in item for item in metadata["warnings"])
    assert answers._index_versions(settings)["vector_index"] == {
        "backend": "qdrant-service", "artifact_verified": False,
    }
    assert "stale-local" not in str(metadata)


def test_migration_cli_uses_explicit_backup_and_service(monkeypatch, work_path: Path) -> None:
    from history_agent.retrieval import vector_migration

    settings = _settings(work_path)
    captured: dict[str, Any] = {}
    backup = work_path / "qdrant-backup"
    backup.mkdir()

    def migrate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"status": "verified", "points": 3}

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(vector_migration, "migrate_qdrant_local", migrate)
    report = work_path / "migration.json"
    result = CliRunner().invoke(cli.app, [
        "index", "migrate-qdrant-service", "--source-index", str(backup),
        "--report", str(report),
    ])
    assert result.exit_code == 0, result.output
    assert captured["source_path"] == backup
    assert captured["target"] == settings.vector_index_target
    assert captured["source_report"] is None
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "verified"
    assert "test-secret" not in result.output
