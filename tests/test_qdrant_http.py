from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from history_agent.config import QdrantServiceTarget
from history_agent.errors import RetrievalError
from history_agent.retrieval import qdrant_http


def test_http_client_preserves_service_request_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "test-secret"
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.raw_path.decode(), body))
        path = request.url.path
        result: Any = True
        if path.endswith("/exists"):
            result = {"exists": True}
        elif path == "/aliases":
            result = {"aliases": [{"alias_name": "history_chunks", "collection_name": "v1"}]}
        elif path.endswith("/count"):
            result = {"count": 1}
        elif path.endswith("/query"):
            result = {"points": [{"score": 0.875, "payload": {"chunk_id": "chunk"}}]}
        return httpx.Response(200, json={"result": result})

    client_type = httpx.Client
    monkeypatch.setattr(
        qdrant_http.httpx, "Client",
        lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(handler)),
    )
    client = qdrant_http.QdrantServiceClient(
        QdrantServiceTarget("http://qdrant.test", "test-secret")
    )
    filters = {"must": [{"key": "people", "match": {"value": "毛泽东"}}]}
    vectors = {"size": 512, "distance": "Cosine"}
    points = [{"id": "point", "vector": [0.25, 0.75], "payload": {"chunk_id": "chunk"}}]
    aliases = [{"create_alias": {"collection_name": "v2", "alias_name": "history_chunks"}}]
    try:
        assert client.collection_exists("v1")
        assert client.get_aliases().aliases[0].collection_name == "v1"
        client.create_collection(collection_name="v2", vectors_config=vectors)
        client.upsert(collection_name="v2", points=points, wait=True)
        assert client.count(collection_name="v2", exact=True).count == 1
        client.update_collection_aliases(change_aliases_operations=aliases)
        result = client.query_points(
            collection_name="history_chunks", query=[0.25, 0.75], query_filter=filters,
            limit=12, with_payload=True, search_params={"exact": True},
        )
        assert result.points[0].score == 0.875
        assert result.points[0].payload == {"chunk_id": "chunk"}
    finally:
        client.close()
    assert client._http.is_closed
    assert requests[2:] == [
        ("PUT", "/collections/v2", {"vectors": vectors}),
        ("PUT", "/collections/v2/points?wait=true", {"points": points}),
        ("POST", "/collections/v2/points/count", {"exact": True}),
        ("POST", "/collections/aliases", {"actions": aliases}),
        ("POST", "/collections/history_chunks/points/query", {
            "query": [0.25, 0.75], "filter": filters, "limit": 12,
            "with_payload": True, "params": {"exact": True},
        }),
    ]


@pytest.mark.parametrize("status_code", [401, 500])
def test_http_client_error_does_not_expose_service_secret(
    monkeypatch: pytest.MonkeyPatch, status_code: int,
) -> None:
    client_type = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, text="server details test-secret")
    )
    monkeypatch.setattr(
        qdrant_http.httpx, "Client", lambda **kwargs: client_type(**kwargs, transport=transport),
    )
    client = qdrant_http.QdrantServiceClient(
        QdrantServiceTarget("http://private-service.test", "test-secret")
    )
    try:
        with pytest.raises(RetrievalError) as failure:
            client.get_collection("history_chunks")
        assert str(status_code) in str(failure.value)
        assert "test-secret" not in str(failure.value)
        assert "private-service" not in str(failure.value)
    finally:
        client.close()
