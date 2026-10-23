from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class QdrantServiceTarget:
    """Connection settings whose representation never exposes service credentials."""

    url: str = field(repr=False)
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: int = 30

    def __str__(self) -> str:
        return "qdrant-service"


class Settings(BaseSettings):
    """Runtime settings resolved relative to the repository root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HISTORY_AGENT_",
        extra="ignore",
        populate_by_name=True,
    )

    project_root: Path = Field(default_factory=default_project_root)
    docs_dir: Path = Path("docs")
    data_dir: Path = Path("data")
    database_url: SecretStr | None = None
    conversation_database_url: SecretStr | None = None
    keyword_database_url: SecretStr | None = None
    qdrant_url: SecretStr | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_timeout_seconds: int = Field(default=30, ge=1, le=600)
    catalog_path: Path = Path("config/corpus_catalog.json")   # 文档数据
    person_aliases_path: Path = Path("config/person_aliases.json")
    relation_types_path: Path = Path("config/relation_types.json")
    log_level: str = "INFO"
    environment: Literal["development", "test", "production"] = "development"
    research_start: date = date(1921, 1, 1)
    research_end: date = date(1978, 12, 31)
    llm_provider: Literal["deepseek"] = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "llm_api_key",
            "HISTORY_AGENT_LLM_API_KEY",
            "DEEPSEEK_API_KEY",
        ),
    )
    llm_model: Literal["deepseek-v4-pro", "deepseek-v4-flash"] = "deepseek-v4-pro"
    llm_thinking: bool = False
    llm_reasoning_effort: Literal["low", "high", "max"] = "high"
    llm_max_tokens: int = Field(default=5000, ge=256, le=16000)
    llm_timeout_seconds: float = Field(default=120.0, ge=10.0, le=600.0)
    request_timeout_seconds: float = Field(default=90.0, ge=10.0, le=600.0)
    llm_max_concurrency: int = Field(default=4, ge=1, le=64)
    llm_query_planning: bool = True
    llm_query_planner_model: Literal["deepseek-v4-pro", "deepseek-v4-flash"] = "deepseek-v4-flash"
    llm_query_planner_max_tokens: int = Field(default=2000, ge=256, le=2000)
    llm_query_planner_timeout_seconds: float = Field(default=20.0, ge=5.0, le=120.0)
    llm_retrieval_reflection: bool = True
    llm_retrieval_reflection_max_queries: int = Field(default=3, ge=1, le=4)
    llm_retrieval_reflection_max_tokens: int = Field(default=450, ge=256, le=1000)
    llm_retrieval_reflection_timeout_seconds: float = Field(default=15.0, ge=5.0, le=60.0)
    context_max_messages: int = Field(default=12, ge=4, le=50)
    context_max_chars: int = Field(default=12_000, ge=1000, le=100_000)
    context_max_tokens: int = Field(default=8_000, ge=1_000, le=100_000)
    visitor_token_pepper: SecretStr = SecretStr("start1921-dev-visitor-pepper")
    visitor_cookie_name: str = "start1921_vid"
    visitor_cookie_secure: bool = False
    csrf_enabled: bool = False
    quota_enabled: bool = True
    visitor_daily_questions: int = Field(default=100, ge=1, le=10_000)
    visitor_daily_tokens: int = Field(default=200_000, ge=1_000, le=100_000_000)
    ip_daily_questions: int = Field(default=60, ge=1, le=100_000)
    ip_daily_tokens: int = Field(default=600_000, ge=1_000, le=1_000_000_000)
    global_daily_tokens: int = Field(default=5_000_000, ge=1_000, le=10_000_000_000)
    max_sessions_per_visitor: int = Field(default=50, ge=1, le=10_000)
    max_messages_per_session: int = Field(default=1000, ge=0, le=100_000)

    @model_validator(mode="after")
    def resolve_paths_and_validate_dates(self) -> Settings:
        self.project_root = self.project_root.resolve()
        for field_name in (
            "docs_dir",
            "data_dir",
            "catalog_path",
            "person_aliases_path",
            "relation_types_path",
        ):
            value = getattr(self, field_name)
            if not value.is_absolute():
                setattr(self, field_name, (self.project_root / value).resolve())
            else:
                setattr(self, field_name, value.resolve())
        if self.research_start > self.research_end:
            raise ValueError("research_start must be on or before research_end")
        for field_name in ("database_url", "conversation_database_url", "keyword_database_url"):
            secret = getattr(self, field_name)
            if secret is not None:
                value = secret.get_secret_value().strip()
                if not value:
                    setattr(self, field_name, None)
                elif not value.startswith(("postgresql://", "postgres://")):
                    raise ValueError(f"{field_name} must be a PostgreSQL connection URL")
                else:
                    setattr(self, field_name, SecretStr(value))
        if self.qdrant_url is not None:
            value = self.qdrant_url.get_secret_value().strip()
            if not value:
                self.qdrant_url = None
            else:
                parsed = urlsplit(value)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise ValueError("qdrant_url must be an HTTP or HTTPS service URL")
                if parsed.username or parsed.password or parsed.query or parsed.fragment:
                    raise ValueError("qdrant_url must not contain credentials, query or fragment")
                self.qdrant_url = SecretStr(value.rstrip("/"))
        if self.qdrant_api_key is not None:
            value = self.qdrant_api_key.get_secret_value().strip()
            self.qdrant_api_key = SecretStr(value) if value else None
        if self.environment == "production":
            if not self.visitor_cookie_secure:
                raise ValueError("visitor_cookie_secure must be true in production")
            if not self.visitor_cookie_name.startswith("__Host-"):
                raise ValueError("visitor_cookie_name must use the __Host- prefix in production")
            if not self.csrf_enabled:
                raise ValueError("csrf_enabled must be true in production")
            if self.visitor_token_pepper.get_secret_value() == "start1921-dev-visitor-pepper":
                raise ValueError("Configure HISTORY_AGENT_VISITOR_TOKEN_PEPPER in production")
        return self

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "processed" / "samples"

    @property
    def pages_dir(self) -> Path:
        return self.data_dir / "processed" / "pages"

    @property
    def ocr_dir(self) -> Path:
        return self.data_dir / "processed" / "ocr"

    @property
    def structure_dir(self) -> Path:
        return self.data_dir / "processed" / "structure"

    @property
    def chunks_dir(self) -> Path:
        return self.data_dir / "processed" / "chunks"

    @property
    def events_dir(self) -> Path:
        return self.data_dir / "processed" / "events"

    @property
    def keyword_index_target(self) -> str:
        secret = self.keyword_database_url or self.database_url
        if secret is None:
            raise ValueError(
                "Configure HISTORY_AGENT_KEYWORD_DATABASE_URL or HISTORY_AGENT_DATABASE_URL."
            )
        return secret.get_secret_value()

    @property
    def keyword_database_backend(self) -> str:
        return "postgresql"

    @property
    def vector_index_target(self) -> QdrantServiceTarget:
        if self.qdrant_url is None:
            raise ValueError("Configure HISTORY_AGENT_QDRANT_URL for the Qdrant service.")
        return QdrantServiceTarget(
            url=self.qdrant_url.get_secret_value(),
            api_key=self.qdrant_api_key.get_secret_value() if self.qdrant_api_key else None,
            timeout_seconds=self.qdrant_timeout_seconds,
        )

    @property
    def vector_database_backend(self) -> str:
        return "qdrant-service"

    @property
    def model_cache_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def database_target(self) -> str:
        if self.database_url is None:
            raise ValueError("Configure HISTORY_AGENT_DATABASE_URL for PostgreSQL.")
        return self.database_url.get_secret_value()

    @property
    def conversation_database_target(self) -> str:
        secret = self.conversation_database_url or self.database_url
        if secret is None:
            raise ValueError(
                "Configure HISTORY_AGENT_CONVERSATION_DATABASE_URL or HISTORY_AGENT_DATABASE_URL."
            )
        return secret.get_secret_value()

    @property
    def database_backend(self) -> str:
        return "postgresql"

    @property
    def conversation_database_backend(self) -> str:
        return "postgresql"

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.runs_dir,
            self.reports_dir,
            self.samples_dir,
            self.pages_dir,
            self.ocr_dir,
            self.structure_dir,
            self.chunks_dir,
            self.events_dir,
            self.model_cache_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())

    def public_snapshot(self) -> dict[str, Any]:
        return {
            "rag_framework": "llamaindex",
            "project_root": str(self.project_root),
            "docs_dir": str(self.docs_dir),
            "data_dir": str(self.data_dir),
            "database_backend": self.database_backend,
            "conversation_database_backend": self.conversation_database_backend,
            "keyword_database_backend": self.keyword_database_backend,
            "vector_database_backend": self.vector_database_backend,
            "catalog_path": str(self.catalog_path),
            "person_aliases_path": str(self.person_aliases_path),
            "relation_types_path": str(self.relation_types_path),
            "log_level": self.log_level,
            "environment": self.environment,
            "research_start": self.research_start.isoformat(),
            "research_end": self.research_end.isoformat(),
            "llm_enabled": self.llm_enabled,
            "llm_provider": self.llm_provider,
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_thinking": self.llm_thinking,
            "llm_reasoning_effort": self.llm_reasoning_effort,
            "llm_max_tokens": self.llm_max_tokens,
            "request_timeout_seconds": self.request_timeout_seconds,
            "llm_max_concurrency": self.llm_max_concurrency,
            "llm_query_planning": self.llm_query_planning,
            "llm_query_planner_model": self.llm_query_planner_model,
            "llm_query_planner_max_tokens": self.llm_query_planner_max_tokens,
            "llm_query_planner_timeout_seconds": self.llm_query_planner_timeout_seconds,
            "llm_retrieval_reflection": self.llm_retrieval_reflection,
            "llm_retrieval_reflection_max_queries": self.llm_retrieval_reflection_max_queries,
            "llm_retrieval_reflection_max_tokens": self.llm_retrieval_reflection_max_tokens,
            "llm_retrieval_reflection_timeout_seconds": (
                self.llm_retrieval_reflection_timeout_seconds
            ),
            "context_max_messages": self.context_max_messages,
            "context_max_chars": self.context_max_chars,
            "context_max_tokens": self.context_max_tokens,
            "visitor_cookie_name": self.visitor_cookie_name,
            "visitor_cookie_secure": self.visitor_cookie_secure,
            "csrf_enabled": self.csrf_enabled,
            "quota_enabled": self.quota_enabled,
            "visitor_daily_questions": self.visitor_daily_questions,
            "visitor_daily_tokens": self.visitor_daily_tokens,
            "ip_daily_questions": self.ip_daily_questions,
            "ip_daily_tokens": self.ip_daily_tokens,
            "global_daily_tokens": self.global_daily_tokens,
            "max_sessions_per_visitor": self.max_sessions_per_visitor,
            "max_messages_per_session": self.max_messages_per_session,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
