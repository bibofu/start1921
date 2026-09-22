from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from history_agent.errors import RetrievalError
from history_agent.retrieval.hybrid import search_hybrid_index
from history_agent.retrieval.models import (
    RetrievalPlan,
    RetrievalStageTrace,
    SearchHit,
    SearchResponse,
)


def _hit(chunk_id: str, rank: int, *, page: int, source: str = "history") -> SearchHit:
    return SearchHit(
        rank=rank, chunk_id=chunk_id, document_id="doc", title="史料", filename="doc.pdf",
        source_type=source, verification_status="verified", pdf_page_start=page,
        pdf_page_end=page, section_path=[], text=f"第{page}页的历史事件记录。",
        year_mentions=[], people=[], extraction_methods=["text_layer"],
        score=10.0 / rank, matched_terms=[],
    )


def _response(query: str, hits: list[SearchHit], **updates: Any) -> SearchResponse:
    response = SearchResponse(
        query=query, query_intent="general", query_terms=[], query_years=[],
        query_year_range=[], query_people=[], document_filters=[],
        include_out_of_scope=False, hits=hits,
    )
    return response.model_copy(update=updates)


def _search(**kwargs: Any) -> SearchResponse:
    return search_hybrid_index(
        keyword_index_path=Path("unused.db"), vector_index_path=Path("unused-vector"),
        model_cache_dir=Path("unused-models"), aliases_path=Path("unused-aliases.json"),
        **kwargs,
    )


def _stage(response: SearchResponse, name: str, query: str | None = None) -> RetrievalStageTrace:
    matches = [
        item for item in response.trace or []
        if item.stage == name and (query is None or item.query == query)
    ]
    assert len(matches) == 1
    return matches[0]


def _ids(stage: RetrievalStageTrace) -> list[str]:
    return [hit.chunk_id for hit in stage.hits]


def test_trace_observes_real_ranking_and_drops_without_changing_default_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits = [
        _hit("history", 1, page=1),
        _hit("chronology", 2, page=2, source="chronology"),
        _hit("same-page", 3, page=2, source="chronology"),
    ]
    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_keyword_index",
        lambda **kw: _response(kw["query"], hits, query_intent="timeline"),
    )
    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_vector_index",
        lambda **kw: _response(kw["query"], [], query_intent="timeline"),
    )

    default = _search(query="主要经历", top_k=1)
    traced = _search(query="主要经历", top_k=1, capture_trace=True)

    assert default.trace is None
    assert default.model_dump(exclude={"trace"}) == traced.model_dump(exclude={"trace"})
    assert [hit.chunk_id for hit in default.hits] == ["chronology"]
    assert _ids(_stage(traced, "keyword_candidates")) == ["history", "chronology", "same-page"]
    assert _ids(_stage(traced, "rrf_fusion")) == ["history", "chronology", "same-page"]
    assert _ids(_stage(traced, "rule_ranking")) == ["chronology", "same-page", "history"]
    assert _ids(_stage(traced, "page_deduplication")) == ["chronology", "history"]
    drops = _stage(traced, "page_deduplication").dropped
    assert [(drop.chunk_id, drop.reason) for drop in drops] == [
        ("same-page", "same_document_pdf_page")
    ]
    assert _stage(traced, "final").dropped[0].chunk_id == "history"
    assert _stage(traced, "final").hits == traced.hits
    assert all(
        stage.elapsed_ms is not None and stage.elapsed_ms >= 0 for stage in traced.trace or []
    )
    assert "not a model reranker" in " ".join(_stage(traced, "rule_ranking").notes)
    # Later final-answer mutations cannot rewrite earlier stage evidence/ranks.
    traced.hits[0].text = "changed after retrieval"
    traced.hits[0].rank = 99
    assert _stage(traced, "rule_ranking").hits[0].rank == 1
    assert _stage(traced, "keyword_candidates").hits[1].rank == 2
    assert _stage(traced, "final").hits[0].text != "changed after retrieval"
    assert hits[1].rank == 2


def test_fixed_candidate_budget_is_independent_of_final_top_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def backend(branch: str, **kwargs: Any) -> SearchResponse:
        calls.append((branch, kwargs["top_k"]))
        return _response(kwargs["query"], [
            _hit(f"hit-{i}", i, page=i) for i in range(1, kwargs["top_k"] + 1)
        ])

    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_keyword_index", lambda **kw: backend("keyword", **kw)
    )
    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_vector_index", lambda **kw: backend("vector", **kw)
    )
    smaller = _search(query="历史事件", top_k=10, candidate_k=30, capture_trace=True)
    larger = _search(query="历史事件", top_k=20, candidate_k=30, capture_trace=True)
    assert sorted(calls) == [("keyword", 30), ("keyword", 30), ("vector", 30), ("vector", 30)]
    assert len(smaller.hits) == 10 and len(larger.hits) == 20
    for branch in ["keyword", "vector"]:
        assert _stage(smaller, f"{branch}_candidates").hits == (
            _stage(larger, f"{branch}_candidates").hits
        )
    calls.clear()
    _search(query="历史事件", top_k=10)
    _search(query="历史事件", top_k=20)
    assert sorted(calls) == [("keyword", 40), ("keyword", 80), ("vector", 40), ("vector", 80)]


@pytest.mark.parametrize("candidate_k", [0, -1, 101, 9, 30.5, True])
def test_invalid_candidate_budget_fails_before_backend_calls(
    monkeypatch: pytest.MonkeyPatch, candidate_k: Any,
) -> None:
    def unexpected(**kwargs: Any) -> SearchResponse:
        raise AssertionError("backend must not run for an invalid budget")

    monkeypatch.setattr("history_agent.retrieval.hybrid.search_keyword_index", unexpected)
    monkeypatch.setattr("history_agent.retrieval.hybrid.search_vector_index", unexpected)
    with pytest.raises(RetrievalError, match="candidate_k"):
        _search(query="历史事件", top_k=10, candidate_k=candidate_k)


def test_congress_expansion_records_extra_budget_and_caps_augmented_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def keyword(**kwargs: Any) -> SearchResponse:
        calls.append((kwargs["query"], kwargs["top_k"]))
        section = kwargs.get("section_path_contains")
        if section:
            hit = _hit(section, 1, page=10 if "第一" in section else 20)
            hit.section_path = [section]
            hit.text = f"中国共产党{section}召开。"
            return _response(kwargs["query"], [hit])
        return _response(kwargs["query"], [_hit(f"generic-{i}", i, page=i) for i in range(1, 4)])

    monkeypatch.setattr("history_agent.retrieval.hybrid.search_keyword_index", keyword)
    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_vector_index",
        lambda **kw: _response(kw["query"], []),
    )
    first = _search(query="比较中共一大和中共二大", top_k=1, candidate_k=3, capture_trace=True)
    first_calls = calls.copy()
    calls.clear()
    second = _search(query="比较中共一大和中共二大", top_k=2, candidate_k=3, capture_trace=True)
    assert calls == first_calls
    assert len(calls) == 3 and all(k == 3 for _, k in calls)
    targeted = [
        stage for stage in second.trace or [] if stage.stage == "keyword_targeted_candidates"
    ]
    assert len(targeted) == 2
    assert targeted[0].query != targeted[1].query
    assert all("Additional congress lookup" in " ".join(stage.notes) for stage in targeted)
    augmented = _stage(second, "keyword_candidates_augmented")
    assert len(augmented.hits) == 3 and augmented.input_count == 5
    assert {drop.chunk_id for drop in augmented.dropped} == {"generic-2", "generic-3"}
    assert augmented.hits == _stage(first, "keyword_candidates_augmented").hits
    assert "does not cap the sum" in " ".join(augmented.notes)


def test_vector_trace_discloses_native_exact_year_overfetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def backend(**kw: Any) -> SearchResponse:
        return _response(
            kw["query"], [_hit("year", 1, page=1)], query_intent="timeline",
            query_years=[1956], query_year_range=[1956, 1956],
        )

    monkeypatch.setattr("history_agent.retrieval.hybrid.search_keyword_index", backend)
    monkeypatch.setattr("history_agent.retrieval.hybrid.search_vector_index", backend)
    response = _search(query="周恩来1956年经历", top_k=20, candidate_k=30, capture_trace=True)
    notes = " ".join(_stage(response, "vector_candidates").notes)
    assert "500 points" in notes and "internal ranking is unobserved" in notes


def test_degraded_trace_does_not_invent_fusion_or_page_deduplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "history_agent.retrieval.hybrid.search_keyword_index",
        lambda **kw: _response(kw["query"], [_hit("a", 1, page=1), _hit("b", 2, page=1)]),
    )

    def unavailable(**kwargs: Any) -> SearchResponse:
        raise RuntimeError("backend is offline")

    monkeypatch.setattr("history_agent.retrieval.hybrid.search_vector_index", unavailable)
    default = _search(query="事件", top_k=2)
    traced = _search(query="事件", top_k=2, capture_trace=True)
    assert default.model_dump(exclude={"trace"}) == traced.model_dump(exclude={"trace"})
    assert _stage(traced, "vector_candidates").status == "failed"
    assert _stage(traced, "vector_candidates").hits == []
    assert [hit.chunk_id for hit in traced.hits] == ["a", "b"]
    assert not {"rrf_fusion", "page_deduplication"} & {s.stage for s in traced.trace or []}


@pytest.mark.parametrize("with_plan", [False, True])
def test_query_variants_retain_subquery_traces_and_one_actual_overall_final(
    monkeypatch: pytest.MonkeyPatch, with_plan: bool,
) -> None:
    queries = ["原问题", "子问题甲", "子问题乙"]

    def backend(**kw: Any) -> SearchResponse:
        return _response(kw["query"], [_hit(kw["query"], 1, page=queries.index(kw["query"]) + 1)])

    monkeypatch.setattr("history_agent.retrieval.hybrid.search_keyword_index", backend)
    monkeypatch.setattr("history_agent.retrieval.hybrid.search_vector_index", backend)
    plan = RetrievalPlan(query_intent="comparison", coverage="per_item") if with_plan else None
    args = dict(query=queries[0], additional_queries=queries[1:], top_k=2, candidate_k=3, plan=plan)
    default = _search(**args)
    response = _search(**args, capture_trace=True)
    assert default.model_dump(exclude={"trace"}) == response.model_dump(exclude={"trace"})
    assert {
        stage.query for stage in response.trace or [] if stage.stage == "query_final"
    } == set(queries)
    assert _stage(response, "final").hits == response.hits
    if with_plan:
        assert _ids(_stage(response, "variants_rrf_fusion")) == queries
        assert [hit.chunk_id for hit in response.hits] == queries[1:]
    else:
        assert [hit.chunk_id for hit in response.hits] == [queries[0]]
        assert "were not merged" in " ".join(_stage(response, "final").notes)
