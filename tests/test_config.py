from datetime import date
from pathlib import Path

import pytest
from history_agent.config import Settings


def test_settings_resolve_paths(work_path: Path) -> None:
    settings = Settings(project_root=work_path, _env_file=None)

    assert settings.docs_dir == (work_path / "docs").resolve()
    assert settings.database_path == (work_path / "data" / "history_agent.db").resolve()
    assert settings.relation_types_path == (work_path / "config" / "relation_types.json").resolve()
    assert settings.research_start == date(1921, 1, 1)
    assert settings.research_end == date(1978, 12, 31)
    assert settings.environment == "development"
    assert settings.llm_max_tokens == 5000
    assert settings.llm_query_planning is True
    assert settings.llm_query_planner_model == "deepseek-v4-flash"
    assert settings.llm_query_planner_timeout_seconds == 20
    assert settings.llm_retrieval_reflection is True
    assert settings.llm_retrieval_reflection_max_rounds == 1
    assert settings.llm_retrieval_reflection_max_queries == 3
    assert settings.database_target == settings.database_path
    assert settings.conversation_database_target == settings.conversation_database_path
    assert settings.database_backend == "sqlite"


def test_invalid_research_range_is_rejected(work_path: Path) -> None:
    with pytest.raises(ValueError, match="research_start"):
        Settings(
            _env_file=None,
            project_root=work_path,
            research_start=date(1979, 1, 1),
            research_end=date(1978, 12, 31),
        )


def test_standard_deepseek_key_environment_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    settings = Settings(_env_file=None)

    assert settings.llm_enabled is True
    assert settings.llm_model == "deepseek-v4-pro"
    assert settings.llm_thinking is False
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "sk-test"


def test_postgres_targets_and_public_snapshot_do_not_expose_credentials(work_path: Path) -> None:
    main_url = "postgresql://research:secret-password@localhost/history"
    conversation_url = "postgresql://conversation:other-password@localhost/chat"
    settings = Settings(_env_file=None, project_root=work_path, database_url=main_url)

    assert settings.database_target == main_url
    assert settings.conversation_database_target == main_url
    assert settings.database_backend == "postgresql"
    assert settings.conversation_database_backend == "postgresql"
    snapshot = settings.public_snapshot()
    assert snapshot["database_path"] is None
    assert "secret-password" not in str(snapshot)
    assert main_url not in repr(settings)

    separate = Settings(
        _env_file=None,
        project_root=work_path,
        database_url=main_url,
        conversation_database_url=conversation_url,
    )
    assert separate.database_target == main_url
    assert separate.conversation_database_target == conversation_url
    assert "other-password" not in str(separate.public_snapshot())


def test_postgres_url_environment_and_empty_fallback(monkeypatch, work_path: Path) -> None:
    monkeypatch.setenv("HISTORY_AGENT_DATABASE_URL", "postgresql://localhost/history")
    settings = Settings(_env_file=None, project_root=work_path)
    assert settings.database_target == "postgresql://localhost/history"

    fallback = Settings(_env_file=None, project_root=work_path, database_url=" ")
    assert fallback.database_target == fallback.database_path
    with pytest.raises(ValueError, match="PostgreSQL connection URL"):
        Settings(_env_file=None, database_url="mysql://localhost/history")
