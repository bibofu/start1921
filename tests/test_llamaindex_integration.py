from __future__ import annotations

from typing import Any

from history_agent.answering.llamaindex_workflow import (
    ResearchStartEvent,
)
from history_agent.answering.models import QuestionRequest
from history_agent.retrieval.llamaindex import (
    HistoryHybridRetriever,
    node_to_search_hit,
    retrieve_with_llamaindex,
)
from history_agent.retrieval.models import SearchHit, SearchResponse
from llama_index.core import QueryBundle
from llama_index.core.callbacks import CallbackManager
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore


def _hit(chunk_id: str, rank: int, text: str = "史料内容") -> SearchHit:
    return SearchHit(
        rank=rank,
        chunk_id=chunk_id,
        document_id="doc",
        title="测试文献",
        filename="test.pdf",
        source_type="chronology",
        verification_status="verified",
        pdf_page_start=rank,
        pdf_page_end=rank,
        section_path=["第一章"],
        text=text,
        year_mentions=[1935],
        people=["周恩来"],
        extraction_methods=["text"],
        score=1 / rank,
        matched_terms=["周恩来"],
        keyword_rank=rank,
        vector_rank=rank,
        rrf_score=0.03 / rank,
    )


def _response(query: str, hits: list[SearchHit]) -> SearchResponse:
    return SearchResponse(
        query=query,
        query_intent="event_overview",
        query_terms=query.split(),
        query_years=[],
        query_year_range=[],
        query_people=["周恩来"],
        document_filters=[],
        include_out_of_scope=False,
        hits=hits,
        retrieval_mode="hybrid",
    )


def test_custom_backend_is_exposed_as_llamaindex_retriever() -> None:
    captured: dict[str, Any] = {}

    def search(**kwargs: Any) -> SearchResponse:
        captured.update(kwargs)
        return _response(str(kwargs["query"]), [_hit("00000000-0000-0000-0000-000000000001", 1)])

    retriever = HistoryHybridRetriever(
        search_backend=search,
        search_kwargs={"top_k": 3, "plan": None},
        additional_queries=["会议前", "会议后"],
    )
    assert isinstance(retriever, BaseRetriever)
    nodes = retriever.retrieve(QueryBundle(query_str="遵义会议"))
    assert isinstance(nodes[0], NodeWithScore)
    assert nodes[0].node.node_id == "00000000-0000-0000-0000-000000000001"
    assert captured["additional_queries"] == ["会议前", "会议后"]
    assert node_to_search_hit(nodes[0], 1).document_id == "doc"


def test_llamaindex_pipeline_round_trips_domain_metadata() -> None:
    def search(**kwargs: Any) -> SearchResponse:
        return _response(
            str(kwargs["query"]),
            [
                _hit("00000000-0000-0000-0000-000000000001", 1),
                _hit("00000000-0000-0000-0000-000000000001", 2),
            ],
        )

    result = retrieve_with_llamaindex(
        search_backend=search,
        query="遵义会议",
        additional_queries=[],
        top_k=3,
        search_kwargs={"plan": None},
    )
    assert result.rag_framework == "llamaindex"
    assert len(result.hits) == 1
    assert result.hits[0].rank == 1


def test_retriever_uses_supplied_callback_manager() -> None:
    manager = CallbackManager()
    retriever = HistoryHybridRetriever(
        search_backend=lambda **kwargs: _response(str(kwargs["query"]), []),
        search_kwargs={"top_k": 1},
        callback_manager=manager,
    )
    assert retriever.callback_manager is manager


def test_workflow_start_event_is_json_serializable() -> None:
    event = ResearchStartEvent(
        request=QuestionRequest(question="周恩来在遵义会议前后做了什么"),
    )
    payload = event.model_dump_json()
    assert "周恩来在遵义会议前后做了什么" in payload
    assert "search_backend" not in payload
