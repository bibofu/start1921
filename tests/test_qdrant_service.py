from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from history_agent.config import QdrantServiceTarget, Settings
from history_agent.errors import IndexBuildError, RetrievalError
from history_agent.retrieval import vector
from history_agent.retrieval.models import RetrievalPlan


def test_service_settings_select_explicit_target_and_hide_credentials(work_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        project_root=work_path,
        qdrant_url=" http://127.0.0.1:6333/ ",
        qdrant_api_key=" service-secret ",
        qdrant_timeout_seconds=12,
    )
    target = settings.vector_index_target
    assert isinstance(target, QdrantServiceTarget)
    assert target.url == "http://127.0.0.1:6333"
    assert target.api_key == "service-secret"
    assert target.timeout_seconds == 12
    assert settings.vector_database_backend == "qdrant-service"
    for public in (repr(settings), repr(target), str(target), str(settings.public_snapshot())):
        assert "service-secret" not in public
        assert "http://127.0.0.1:6333" not in public
    missing = Settings(_env_file=None, project_root=work_path, qdrant_url=" ")
    with pytest.raises(ValueError, match="HISTORY_AGENT_QDRANT_URL"):
        _ = missing.vector_index_target


@pytest.mark.parametrize(
    "url", ["file:///storage", "http://", "http://user:password@host", "http://host?key=secret"]
)
def test_service_url_rejects_nonservice_or_embedded_credentials(url: str) -> None:
    with pytest.raises(ValueError, match="qdrant_url"):
        Settings(_env_file=None, qdrant_url=url)


def test_service_client_never_opens_local_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[QdrantServiceTarget] = []
    sentinel = object()

    def client_factory(target: QdrantServiceTarget) -> object:
        received.append(target)
        return sentinel

    monkeypatch.setattr(vector, "QdrantServiceClient", client_factory)
    target = QdrantServiceTarget("http://localhost:6333", "test-key", 9)
    assert vector.open_vector_client(target) is sentinel
    assert received == [target]
    with pytest.raises(RetrievalError, match="requires a Qdrant service target"):
        vector.open_vector_client(Path("archived-data"))  # type: ignore[arg-type]
    assert received == [target]


def test_service_search_preserves_filters_and_section_year_order(
    monkeypatch: pytest.MonkeyPatch, work_path: Path
) -> None:
    aliases = work_path / "aliases.json"
    aliases.write_text(json.dumps({"people": []}), encoding="utf-8")
    captured: dict[str, Any] = {}
    closed: list[bool] = []

    def point(chunk_id: str, section: str, score: float) -> SimpleNamespace:
        return SimpleNamespace(
            score=score,
            payload={
                "chunk_id": chunk_id, "document_id": "doc", "title": "标题",
                "filename": "source.pdf", "source_type": "chronology",
                "verification_status": "verified", "pdf_page_start": 1, "pdf_page_end": 1,
                "section_path": [section], "text": "原文",
            },
        )

    def query_points(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(points=[point("nearby", "1934年", .91), point("year", "1935年", .8)])

    client = SimpleNamespace(query_points=query_points, close=lambda: closed.append(True))
    embedding = SimpleNamespace(
        query_embed=lambda query: [SimpleNamespace(tolist=lambda: [0.25, 0.75])]
    )
    monkeypatch.setattr(vector, "open_vector_client", lambda target: client)
    monkeypatch.setattr(vector, "_embedding_model", lambda path: embedding)
    response = vector.search_vector_index(
        index_path=QdrantServiceTarget("http://127.0.0.1:6333"),
        model_cache_dir=work_path / "models",
        aliases_path=aliases,
        query="1935年经历",
        top_k=2,
        document_ids=["doc"],
        plan=RetrievalPlan(query_intent="timeline", query_years=[1935]),
    )
    assert captured["query"] == [0.25, 0.75]
    assert captured["limit"] == 100
    assert captured["search_params"] == {"exact": True}
    assert captured["query_filter"]["must"][0]["match"]["any"] == ["doc"]
    assert captured["query_filter"]["must_not"][0]["match"]["value"] == "out_of_scope"
    assert [hit.chunk_id for hit in response.hits] == ["year", "nearby"]
    assert [hit.score for hit in response.hits] == [0.8, 0.91]
    assert closed == [True]


def test_collection_publish_changes_alias_atomically_without_deleting_data() -> None:
    operations: list[Any] = []
    client = SimpleNamespace(
        get_aliases=lambda: SimpleNamespace(
            aliases=[SimpleNamespace(alias_name=vector.COLLECTION_NAME)]
        ),
        update_collection_aliases=lambda **kwargs: operations.append(
            kwargs["change_aliases_operations"]
        ),
    )
    vector.publish_vector_collection(client, "history_chunks_new")
    assert len(operations) == 1
    assert operations[0] == [
        {"delete_alias": {"alias_name": vector.COLLECTION_NAME}},
        {"create_alias": {
            "collection_name": "history_chunks_new", "alias_name": vector.COLLECTION_NAME,
        }},
    ]


def test_collection_publish_refuses_to_overwrite_physical_serving_collection() -> None:
    client = SimpleNamespace(
        get_aliases=lambda: SimpleNamespace(aliases=[]), collection_exists=lambda name: True
    )
    with pytest.raises(IndexBuildError, match="physical Qdrant collection"):
        vector.publish_vector_collection(client, "history_chunks_new")
