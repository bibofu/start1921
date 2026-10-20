"""Functional readiness probes for local storage and retrieval backends."""

from __future__ import annotations

from history_agent.config import Settings
from history_agent.db_backend import DATABASE_ERRORS, database_connection
from history_agent.retrieval.keyword import search_keyword_index
from history_agent.retrieval.vector import (
    COLLECTION_NAME,
    open_vector_client,
    search_vector_index,
)


def _database_ready(target: str) -> bool:
    with database_connection(target) as connection:
        connection.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
        connection.execute("SELECT person_id FROM persons LIMIT 1").fetchone()
    return True


def readiness_snapshot(settings: Settings) -> dict[str, object]:
    components: dict[str, bool] = {}
    try:
        components["database"] = _database_ready(settings.database_target)
    except (OSError, *DATABASE_ERRORS):
        components["database"] = False
    components["keyword"] = keyword_index_ready(settings)
    try:
        search_vector_index(
            index_path=settings.vector_index_target,
            model_cache_dir=settings.model_cache_dir / "fastembed",
            aliases_path=settings.person_aliases_path,
            query="中国共产党",
            top_k=1,
        )
        components["vector"] = True
    except Exception:
        components["vector"] = False
    ready = components["database"] and (components["keyword"] or components["vector"])
    return {
        "status": "ready" if ready else "not_ready",
        "components": components,
    }


def keyword_index_ready(settings: Settings) -> bool:
    """Probe the configured PostgreSQL keyword index."""
    try:
        search_keyword_index(
            index_path=settings.keyword_index_target,
            query="中国共产党",
            aliases_path=settings.person_aliases_path,
            top_k=1,
        )
        return True
    except Exception:
        return False


def vector_index_ready(settings: Settings) -> bool:
    """Check the configured service instead of a leftover local Qdrant directory."""
    target = settings.vector_index_target
    try:
        client = open_vector_client(target)
        try:
            client.get_collection(COLLECTION_NAME)
            return True
        finally:
            client.close()
    except Exception:
        return False
