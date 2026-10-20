from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from history_agent.answering.llamaindex_workflow import _search_kwargs
from history_agent.config import Settings
from history_agent.errors import RetrievalError
from history_agent.evaluation import answers, golden
from history_agent.web import app as web_module
from history_agent.web import readiness
from typer.testing import CliRunner


def _settings(work_path: Path) -> Settings:
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        keyword_database_url="postgresql://keyword:password@localhost/keyword",
    )
    settings.keyword_index_path.parent.mkdir(parents=True)
    settings.keyword_index_path.write_bytes(b"stale sqlite index must not mask postgres failure")
    settings.reports_dir.mkdir(parents=True)
    (settings.reports_dir / "keyword_index_latest.json").write_text(
        json.dumps({
            "index_version": "stale-sqlite-version",
            "chunks": 100,
            "manifest": {"index_artifact_sha256": "old-sqlite-hash"},
        }),
        encoding="utf-8",
    )
    return settings


def _metadata() -> dict[str, Any]:
    return {
        "summary": {"index_version": "postgres-keyword", "run_id": "build", "chunks": 17},
        "manifest": {
            "index_artifact_sha256": "actual-postgres-content",
            "chunk_artifact_sha256": "source-chunks",
        },
        "actual_index_artifact_sha256": "actual-postgres-content",
        "artifact_verified": True,
        "generation_id": "active-generation",
    }


def test_workflow_passes_the_keyword_database_target(work_path: Path) -> None:
    settings = _settings(work_path)
    arguments = _search_kwargs(settings, None)
    assert arguments["keyword_index_path"] == settings.keyword_index_target
    assert arguments["vector_index_path"] == settings.vector_index_path


def test_readiness_and_health_do_not_use_stale_sqlite_index(monkeypatch, work_path: Path) -> None:
    settings = _settings(work_path)
    targets: list[Path | str] = []

    def unavailable(*, index_path: Path | str, **kwargs: Any) -> Any:
        targets.append(index_path)
        raise RetrievalError("unavailable")

    monkeypatch.setattr(readiness, "search_keyword_index", unavailable)
    monkeypatch.setattr(readiness, "_database_ready", lambda target: True)
    monkeypatch.setattr(readiness, "search_vector_index", lambda **kwargs: None)
    snapshot = readiness.readiness_snapshot(settings)
    assert snapshot["components"]["keyword"] is False
    monkeypatch.setattr(web_module, "_database_ready", lambda target: True)
    response = TestClient(web_module.create_app(settings)).get("/api/health")
    assert response.json()["indexes"]["keyword"] is False
    assert response.json()["keyword_database_backend"] == "postgresql"
    assert targets == [settings.keyword_index_target, settings.keyword_index_target]
    assert "password" not in response.text


def test_golden_metadata_uses_verified_active_postgres_generation(
    monkeypatch, work_path: Path,
) -> None:
    settings = _settings(work_path)
    targets: list[str] = []

    def metadata(target: str) -> dict[str, Any]:
        targets.append(target)
        return _metadata()

    def reject_old_file(path: Path) -> str:
        raise AssertionError("the old SQLite artifact must not be read for PostgreSQL")

    monkeypatch.setattr(golden, "load_keyword_index_metadata", metadata)
    monkeypatch.setattr(golden, "index_artifact_sha256", reject_old_file)
    result = golden._load_index_metadata(settings)
    assert result["reports"]["keyword_index"] == _metadata()
    assert targets == [settings.keyword_index_target]
    assert "stale-sqlite-version" not in str(result)
    assert "password" not in str(result)


def test_metadata_failure_does_not_fall_back_to_stale_sqlite_report(
    monkeypatch, work_path: Path,
) -> None:
    settings = _settings(work_path)

    def unavailable(target: str) -> dict[str, Any]:
        raise RetrievalError("connection failed")

    monkeypatch.setattr(golden, "load_keyword_index_metadata", unavailable)
    monkeypatch.setattr(answers, "load_keyword_index_metadata", unavailable)
    result = golden._load_index_metadata(settings)
    assert result["reports"]["keyword_index"]["artifact_verified"] is False
    assert result["reports"]["keyword_index"]["manifest"] is None
    assert "stale-sqlite-version" not in str(result)
    versions = answers._index_versions(settings)
    assert versions["keyword_index"] == {"backend": "postgresql", "artifact_verified": False}


def test_answer_evaluation_records_active_generation(monkeypatch, work_path: Path) -> None:
    settings = _settings(work_path)
    monkeypatch.setattr(answers, "load_keyword_index_metadata", lambda target: _metadata())
    versions = answers._index_versions(settings)
    assert versions["keyword_index"]["index_version"] == "postgres-keyword"
    assert versions["keyword_index"]["generation_id"] == "active-generation"
    assert versions["keyword_index"]["artifact_verified"] is True


def test_keyword_migration_cli_uses_explicit_target_and_sqlite_source(
    monkeypatch, work_path: Path,
) -> None:
    from history_agent import cli
    from history_agent.retrieval import keyword_migration

    settings = _settings(work_path)
    captured: dict[str, Any] = {}

    def migrate(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"status": "verified", "generation_id": "new-generation"}

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(keyword_migration, "migrate_keyword_index", migrate)
    report = work_path / "migration-result.json"
    result = CliRunner().invoke(cli.app, [
        "index", "migrate-keyword-postgres",
        "--backup-dir", str(work_path / "backup"),
        "--report", str(report),
    ])
    assert result.exit_code == 0, result.output
    assert captured["source_index"] == settings.keyword_index_path
    assert captured["target_url"] == settings.keyword_index_target
    assert captured["source_report"] == settings.reports_dir / "keyword_index_latest.json"
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "verified"
    assert "password" not in result.output


def test_keyword_verification_cli_uses_requested_generation(monkeypatch, work_path: Path) -> None:
    from history_agent import cli
    from history_agent.retrieval import keyword_migration

    settings = _settings(work_path)
    captured: dict[str, Any] = {}

    def verify(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"status": "verified"}

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(keyword_migration, "verify_keyword_index", verify)
    result = CliRunner().invoke(cli.app, [
        "index", "verify-keyword-postgres", "--generation-id", "7",
    ])
    assert result.exit_code == 0, result.output
    assert captured == {
        "source_index": settings.keyword_index_path,
        "target_url": settings.keyword_index_target,
        "generation_id": 7,
    }
    assert "password" not in result.output
