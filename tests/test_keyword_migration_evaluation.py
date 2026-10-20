from __future__ import annotations

import copy
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest
from history_agent.errors import RetrievalError
from history_agent.evaluation import keyword_migration as evaluation
from history_agent.retrieval import keyword_legacy


def test_expected_empty_query_error_is_captured_but_unexpected_errors_propagate() -> None:
    def invalid_query(**_: Any) -> None:
        raise RetrievalError("no searchable terms")

    metadata, hits = evaluation.observed_response(invalid_query, {})
    assert metadata["error"] == {"type": "RetrievalError", "message": "no searchable terms"}
    assert hits == []

    def broken_backend(**_: Any) -> None:
        raise RuntimeError("backend broke")

    with pytest.raises(RuntimeError):
        evaluation.observed_response(broken_backend, {})


def test_complete_synthetic_metrics_have_actual_denominators() -> None:
    grades = {"irrelevant": 0, "first": 2, "second": 2}
    result = evaluation.synthetic_metrics(["irrelevant", "first", "second"], grades, 3)
    assert result["recall"] == {"value": 1, "numerator": 2, "denominator": 2}
    assert result["precision"] == {"value": 2 / 3, "numerator": 2, "denominator": 3}
    assert result["mrr"]["value"] == 0.5
    assert 0 < result["ndcg"]["value"] < 1
    assert evaluation.synthetic_metrics([], {"negative": 0}, 1)["recall"]["value"] is None
    assert evaluation.synthetic_metrics([], {"positive": 2}, 1)["mrr"]["value"] == 0
    with pytest.raises(ValueError, match="Unjudged"):
        evaluation.synthetic_metrics(["unknown"], grades, 3)
    with pytest.raises(ValueError, match="unique"):
        evaluation.synthetic_metrics(["first", "first"], grades, 3)


def test_missing_human_labels_do_not_enter_macro_as_zero() -> None:
    records = [
        {
            "case_id": "approved",
            "metrics": {
                "recall": {
                    "value": 0.5,
                    "evaluable": True,
                    "denominator": 2,
                    "reason": None,
                }
            },
        },
        {
            "case_id": "pending",
            "metrics": {
                "recall": {
                    "value": None,
                    "evaluable": False,
                    "denominator": None,
                    "reason": "pending",
                }
            },
        },
    ]
    report = evaluation.strict_aggregate(records)["recall"]
    assert report["value"] == 0.5
    assert report["evaluable_cases"] == 1
    assert report["total_cases"] == 2
    assert report["unevaluable_reasons"] == {"pending": "pending"}


def _capture() -> dict[str, Any]:
    hits = [
        {"chunk_id": "a", "score": 1, "fields_sha256": "a"},
        {"chunk_id": "b", "score": 1, "fields_sha256": "b"},
    ]
    return {
        "protocol_sha256": "protocol",
        "oracle_identity_sha256": "oracle",
        "dataset_sha256": "dataset",
        "corpus_sha256": "corpus",
        "aliases_sha256": "aliases",
        "baseline_inventory_sha256": "inventory",
        "k_values": [1],
        "exhaustive_k": 2,
        "workload_count": 1,
        "strict_human_aggregate": {},
        "queries": [
            {
                "input": {"id": "query"},
                "input_sha256": "input",
                "hits": hits,
                "metadata": {"query": "example"},
                "human_metrics": None,
                "all_results_ms": 1,
                "at_k": {
                    "1": {"hits": hits[:1], "metadata": {"query": "example"}, "elapsed_ms": 1}
                },
            }
        ],
    }


def test_compatibility_detects_tie_order_score_and_identity_changes() -> None:
    before = _capture()
    after = copy.deepcopy(before)
    assert evaluation.compare_keyword(before, after)["passed"]
    after["queries"][0]["hits"].reverse()
    report = evaluation.compare_keyword(before, after)
    assert not report["passed"]
    assert report["queries"][0]["tie_only_order_change"]
    after = copy.deepcopy(before)
    after["queries"][0]["hits"][0]["score"] = 2
    assert evaluation.compare_keyword(before, after)["queries"][0]["changed_hit_ids"] == ["a"]
    after["corpus_sha256"] = "different"
    with pytest.raises(ValueError, match="corpus_sha256"):
        evaluation.compare_keyword(before, after)


def test_end_to_end_compares_answers_and_all_stages_excluding_latency() -> None:
    item = {
        "case_id": "case",
        "input_variant_id": "single",
        "input_sha256": "input",
        "request": {},
        "retrieval": {"elapsed_ms": 1},
        "stages": [],
        "production_stages": [],
        "generation_contexts": [],
        "answer": {"text": "answer"},
    }
    before = {
        "dataset_sha256": "dataset",
        "execution_contract": {},
        "corpus": {},
        "config": {"with_llm": False},
        "cases": [item],
    }
    after = copy.deepcopy(before)
    after["cases"][0]["retrieval"]["elapsed_ms"] = 2
    assert evaluation.compare_e2e(before, after)["passed"]
    after["cases"][0]["answer"]["text"] = "changed"
    report = evaluation.compare_e2e(before, after)
    assert not report["passed"]
    assert report["cases"][0]["checks"]["answer"] is False
    assert report["semantic_answer_quality"] is None


@pytest.fixture
def postgres_url() -> Iterator[str]:
    url = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set HISTORY_AGENT_TEST_POSTGRES_URL for an isolated PostgreSQL schema.")
    psycopg = pytest.importorskip("psycopg")
    schema = "test_keyword_evaluation_" + uuid4().hex
    parsed = urlsplit(url)
    parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
    parameters["options"] = (parameters.get("options", "") + f" -csearch_path={schema}").strip()
    isolated = urlunsplit(parsed._replace(query=urlencode(parameters)))
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )
        try:
            yield isolated
        finally:
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema))
            )


def test_actual_synthetic_retrieval_has_complete_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluation, "load_contract", lambda _: {})
    monkeypatch.setattr(evaluation, "legacy_module", lambda *_: keyword_legacy)
    report = evaluation.capture_synthetic(
        tmp_path / "result.json",
        backend="legacy",
        work_dir=tmp_path / "run",
        target=tmp_path / "index.sqlite",
        root=Path(__file__).resolve().parents[1],
    )
    default = report["queries"][0]["at_k"]["10"]["metrics"]
    assert default["recall"]["value"] == 1
    assert default["precision"]["value"] == 0.4
    assert default["mrr"]["value"] is not None
    assert len(report["queries"]) == 10
    with pytest.raises(FileExistsError):
        evaluation.capture_synthetic(
            tmp_path / "result.json",
            backend="legacy",
            work_dir=tmp_path / "run",
            target=tmp_path / "index.sqlite",
            root=Path(__file__).resolve().parents[1],
        )


def test_actual_postgres_synthetic_matches_frozen_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    postgres_url: str,
) -> None:
    monkeypatch.setattr(evaluation, "load_contract", lambda _: {})
    monkeypatch.setattr(evaluation, "legacy_module", lambda *_: keyword_legacy)
    root = Path(__file__).resolve().parents[1]
    before = evaluation.capture_synthetic(
        tmp_path / "before.json",
        backend="legacy",
        work_dir=tmp_path / "legacy",
        target=tmp_path / "index.sqlite",
        root=root,
    )
    after = evaluation.capture_synthetic(
        tmp_path / "after.json",
        backend="candidate",
        work_dir=tmp_path / "pg",
        target=postgres_url,
        root=root,
    )
    assert before["fixture_sha256"] == after["fixture_sha256"]
    assert before["queries"] == after["queries"]
