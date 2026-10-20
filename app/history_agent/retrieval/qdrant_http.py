"""The service REST operations used by this project, without a local backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from history_agent.config import QdrantServiceTarget
from history_agent.errors import RetrievalError


@dataclass
class ScoredPoint:
    score: float
    payload: dict[str, Any] | None


@dataclass
class QueryResult:
    points: list[ScoredPoint]


@dataclass
class CountResult:
    count: int


@dataclass
class CollectionAlias:
    alias_name: str
    collection_name: str


@dataclass
class AliasResult:
    aliases: list[CollectionAlias]


class QdrantServiceClient:
    def __init__(self, target: QdrantServiceTarget) -> None:
        headers = {"api-key": target.api_key} if target.api_key else {}
        self._http = httpx.Client(
            base_url=target.url.rstrip("/") + "/",
            headers=headers,
            timeout=target.timeout_seconds,
            trust_env=False,
        )

    def _request(
        self, method: str, path: str, *, body: dict[str, Any] | None = None
    ) -> Any:
        try:
            response = self._http.request(method, path, json=body)
            response.raise_for_status()
            return response.json()["result"]
        except httpx.HTTPStatusError as exc:
            raise RetrievalError(
                f"Qdrant service returned HTTP {exc.response.status_code}."
            ) from None
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise RetrievalError(
                f"Qdrant service request failed ({type(exc).__name__})."
            ) from None

    @staticmethod
    def _collection(name: str) -> str:
        return "collections/" + quote(name, safe="")

    def get_collection(self, collection_name: str) -> Any:
        return self._request("GET", self._collection(collection_name))

    def collection_exists(self, collection_name: str) -> bool:
        result = self._request("GET", self._collection(collection_name) + "/exists")
        return bool(result["exists"])

    def get_aliases(self) -> AliasResult:
        result = self._request("GET", "aliases")
        return AliasResult(
            [CollectionAlias(**item) for item in result["aliases"]]
        )

    def update_collection_aliases(
        self, *, change_aliases_operations: list[dict[str, Any]]
    ) -> None:
        self._request(
            "POST", "collections/aliases", body={"actions": change_aliases_operations}
        )

    def create_collection(
        self, *, collection_name: str, vectors_config: dict[str, Any]
    ) -> None:
        self._request(
            "PUT", self._collection(collection_name), body={"vectors": vectors_config}
        )

    def upsert(
        self, *, collection_name: str, points: list[dict[str, Any]], wait: bool
    ) -> None:
        self._request(
            "PUT",
            self._collection(collection_name) + f"/points?wait={str(wait).lower()}",
            body={"points": points},
        )

    def count(self, *, collection_name: str, exact: bool) -> CountResult:
        result = self._request(
            "POST", self._collection(collection_name) + "/points/count",
            body={"exact": exact},
        )
        return CountResult(count=int(result["count"]))

    def query_points(
        self, *, collection_name: str, query: list[float],
        query_filter: dict[str, Any], limit: int, with_payload: bool,
        search_params: dict[str, Any],
    ) -> QueryResult:
        result = self._request(
            "POST", self._collection(collection_name) + "/points/query",
            body={
                "query": query,
                "filter": query_filter,
                "limit": limit,
                "with_payload": with_payload,
                "params": search_params,
            },
        )
        return QueryResult([
            ScoredPoint(score=float(item["score"]), payload=item.get("payload"))
            for item in result["points"]
        ])

    def close(self) -> None:
        self._http.close()
