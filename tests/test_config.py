from datetime import date
from pathlib import Path

import pytest
from history_agent.config import QdrantServiceTarget, Settings


def test_settings_resolve_paths(work_path: Path) -> None:
    settings = Settings(
        project_root=work_path,
        _env_file=None,
        database_url="postgresql://localhost/history",
        conversation_database_url=None,
        keyword_database_url=None,
    )

    assert settings.docs_dir == (work_path / "docs").resolve()
    assert settings.data_dir == (work_path / "data").resolve()
    assert settings.relation_types_path == (work_path / "config" / "relation_types.json").resolve()
    assert settings.research_start == date(1921, 1, 1)
    assert settings.research_end == date(1978, 12, 31)
    assert settings.environment == "development"
    assert settings.llm_max_tokens == 5000
    assert settings.llm_query_planning is True
    assert settings.llm_query_planner_model == "deepseek-v4-flash"
    assert settings.llm_query_planner_timeout_seconds == 20
    assert settings.llm_retrieval_reflection is True
    assert settings.llm_query_planner_max_tokens == 2000
    assert settings.llm_retrieval_reflection_max_queries == 3
    assert settings.visitor_daily_questions == 100
    assert settings.context_max_tokens == 8000
    assert settings.database_target == "postgresql://localhost/history"
    assert settings.conversation_database_target == settings.database_target
    assert settings.database_backend == "postgresql"
    assert settings.keyword_index_target == settings.database_target
    assert settings.keyword_database_backend == "postgresql"


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
    settings = Settings(
        _env_file=None, project_root=work_path, database_url=main_url,
        conversation_database_url=None,
    )

    assert settings.database_target == main_url
    assert settings.conversation_database_target == main_url
    assert settings.database_backend == "postgresql"
    assert settings.conversation_database_backend == "postgresql"
    snapshot = settings.public_snapshot()
    assert "database_url" not in snapshot
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


def test_postgres_url_environment_and_missing_target_rejected(monkeypatch, work_path: Path) -> None:
    monkeypatch.setenv("HISTORY_AGENT_DATABASE_URL", "postgresql://localhost/history")
    settings = Settings(_env_file=None, project_root=work_path)
    assert settings.database_target == "postgresql://localhost/history"

    missing = Settings(
        _env_file=None, project_root=work_path, database_url=" ",
        conversation_database_url=None, keyword_database_url=None,
    )
    for attribute in ("database_target", "conversation_database_target", "keyword_index_target"):
        with pytest.raises(ValueError, match="HISTORY_AGENT_"):
            getattr(missing, attribute)
    with pytest.raises(ValueError, match="PostgreSQL connection URL"):
        Settings(_env_file=None, database_url="mysql://localhost/history")


def test_keyword_postgres_target_inherits_main_or_uses_explicit_secret(work_path: Path) -> None:
    main_url = "postgresql://main:main-password@localhost/history"
    keyword_url = "postgresql://keyword:keyword-password@localhost/keyword"
    default = Settings(
        _env_file=None, project_root=work_path, database_url=main_url,
        keyword_database_url=None,
    )
    assert default.keyword_index_target == main_url
    settings = Settings(
        _env_file=None, project_root=work_path, database_url=main_url,
        keyword_database_url=keyword_url,
    )
    assert settings.keyword_index_target == keyword_url
    assert settings.keyword_database_backend == "postgresql"
    assert settings.public_snapshot()["keyword_database_backend"] == "postgresql"
    assert "keyword-password" not in str(settings.public_snapshot())
    assert keyword_url not in repr(settings)


def test_keyword_database_url_environment_and_validation(monkeypatch, work_path: Path) -> None:
    monkeypatch.setenv("HISTORY_AGENT_KEYWORD_DATABASE_URL", "postgresql://localhost/keyword")
    settings = Settings(_env_file=None, project_root=work_path)
    assert settings.keyword_index_target == "postgresql://localhost/keyword"
    fallback = Settings(_env_file=None, project_root=work_path, keyword_database_url=" ")
    assert fallback.keyword_index_target == fallback.database_target
    with pytest.raises(ValueError, match="keyword_database_url"):
        Settings(_env_file=None, keyword_database_url="file:///keyword.db")


def test_qdrant_requires_service_url_and_preserves_secret_settings(work_path: Path) -> None:
    missing = Settings(_env_file=None, project_root=work_path, qdrant_url=None)
    with pytest.raises(ValueError, match="HISTORY_AGENT_QDRANT_URL"):
        _ = missing.vector_index_target

    settings = Settings(
        _env_file=None, project_root=work_path, qdrant_url="http://localhost:6333/",
        qdrant_api_key="private-api-key", qdrant_timeout_seconds=45,
    )
    target = settings.vector_index_target
    assert isinstance(target, QdrantServiceTarget)
    assert target.url == "http://localhost:6333"
    assert target.api_key == "private-api-key"
    assert target.timeout_seconds == 45
    assert settings.vector_database_backend == "qdrant-service"
    assert "private-api-key" not in repr(settings)
    assert "private-api-key" not in repr(target)
    assert "private-api-key" not in str(settings.public_snapshot())
