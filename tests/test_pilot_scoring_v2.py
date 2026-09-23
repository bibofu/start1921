import asyncio
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from history_agent.answering.runtime import LLMRuntime
from history_agent.evaluation.pilot import compare, digest, score
from history_agent.evaluation.pilot_answers import DIMENSIONS, answer_fingerprint
from history_agent.evaluation.pilot_metrics import evidence_unit
from history_agent.evaluation.pilot_models import (
    PilotDataset,
    case_definition,
    seal_ranking_pool,
)
from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime

PDF_HASH = "a" * 64


def _write(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _scoring_inputs(root: Path) -> dict[str, Path]:
    hits = [
        {"document_id": "doc", "pdf_page_start": 3, "pdf_page_end": 3, "text": "无关天气。"},
        {"document_id": "doc", "pdf_page_start": 10, "pdf_page_end": 10, "text": "他出任总理。"},
    ]
    units = [evidence_unit(hit, {"doc": PDF_HASH}) for hit in hits]
    dataset = PilotDataset.model_validate(
        {
            "schema_version": 1,
            "version": "integration-v2",
            "description": "Artificial integration fixture, no live corpus.",
            "cases": [
                {
                    "id": "p1",
                    "question": "他担任什么职务？",
                    "category": "exact_fact",
                    "answerability": "answerable",
                    "split": "development",
                    "topic_group": "appointment",
                    "human_review": {"status": "pending"},
                    "evidence_groups": [
                        {
                            "id": "g1",
                            "description": "任职",
                            "alternatives": [
                                {
                                    "document_id": "doc",
                                    "pdf_page": 10,
                                    "file_sha256": PDF_HASH,
                                    "quote": "出任总理",
                                }
                            ],
                        }
                    ],
                    "facts": [
                        {"id": "f1", "claim": "出任总理", "evidence_group_ids": ["g1"]}
                    ],
                    "judgments": [
                        {
                            "unit_id": unit["unit_id"],
                            "relevance": index * 2,
                            "reason": "原文任职证据" if index else "无关天气内容",
                            "reviewer": "test-agent",
                            "reviewed_at": "2026-09-23T00:00:00Z",
                            "basis": "agent_review",
                            "supported_groups": ["g1"] if index else [],
                        }
                        for index, unit in enumerate(units)
                    ],
                }
            ],
        }
    ).model_dump(mode="json")
    case_hash = digest(case_definition(dataset["cases"][0]))
    answer = {"answer": "他出任总理。[E1]", "citations": [{"evidence_id": "E1"}]}
    capture = {
        "run_name": "synthetic-v2",
        "corpus": {"sha256": "corpus", "documents": [{"document_id": "doc", "sha256": PDF_HASH}]},
        "git": {"commit": "fixture", "dirty": False},
        "source_sha256": "source",
        "index_metadata": {},
        "config": {"top_k": 2, "candidate_k": 2, "with_llm": False},
        "index_attribution": {"attribution_safe": True},
        "component_candidate_fingerprints": {"p1": {"keyword_candidates": "same"}},
        "cases": [
            {
                "case_id": "p1",
                "case_definition_sha256": case_hash,
                "stages": [
                    {
                        "stage": "final",
                        "query": "他担任什么职务？",
                        "status": "ok",
                        "elapsed_ms": 1,
                        "hits": hits,
                    }
                ],
                "generation_contexts": [],
                "answer": answer,
                "retrieval_ms": 1,
                "answer_ms": 1,
            }
        ],
    }
    pool = seal_ranking_pool(
        {
            "pool_id": "p1-fixed-pool",
            "case_id": "p1",
            "selection_policy": "Both synthetic candidate spans, frozen before scoring.",
            "unit_ids": [unit["unit_id"] for unit in units],
            "unit_identity_records": units,
            "basis": "agent_review",
            "reviewer": "test-agent",
            "reviewed_at": "2026-09-23T00:00:00Z",
        }
    )
    assessments = {
        "schema_version": 1,
        "rubric_version": "explicit-answer-review-v1",
        "capture_sha256": digest(capture),
        "cases": [
            {
                "case_id": "p1",
                "case_definition_sha256": case_hash,
                "answer_sha256": answer_fingerprint(answer),
                "basis": "agent_review",
                "reviewer": "test-agent",
                "reviewed_at": "2026-09-23T00:00:00Z",
                "facts": [
                    {
                        "fact_id": "f1",
                        "status": "covered",
                        "reason": "答案与任职证据相符",
                        "answer_excerpt": "他出任总理。",
                        "cited_evidence_ids": ["E1"],
                        "support_status": "supported",
                    }
                ],
                "dimensions": {
                    dimension: {
                        "status": "pass"
                        if dimension in {"citation_support", "routing"}
                        else "not_applicable",
                        "reason": "合成夹具中的明确判断",
                    }
                    for dimension in DIMENSIONS
                },
            }
        ],
    }
    return {
        "dataset": _write(root / "dataset.json", dataset),
        "capture": _write(root / "capture.json", capture),
        "pools": _write(root / "pools.json", {"schema_version": 1, "pools": [pool]}),
        "assessments": _write(root / "assessments.json", assessments),
        "output": root / "report.json",
    }


def _score(paths: dict[str, Path], *, with_reviews: bool = True) -> dict[str, Any]:
    return score(
        paths["dataset"],
        paths["capture"],
        paths["output"],
        (1, 2),
        ranking_pools_path=paths["pools"],
        assessments_path=paths["assessments"] if with_reviews else None,
    )


def test_score_integrates_sealed_pool_and_bound_answer_reviews(work_path: Path) -> None:
    paths = _scoring_inputs(work_path)
    result = _score(paths)
    metrics = result["cases"][0]["stages"][0]["provisional"]["metrics"]
    assert metrics["required_group_recall@1"]["value"] == 0
    assert metrics["required_group_recall@2"]["value"] == 1
    assert metrics["precision@2"]["value"] == 0.5
    assert metrics["mrr@2"]["value"] == 0.5
    assert metrics["pool_ndcg@2"]["value"] == pytest.approx(1 / math.log2(3))
    aggregate = result["provisional_aggregate"]["final.pool_ndcg@2"]
    assert aggregate["pool_fingerprints"] == {"p1": metrics["pool_ndcg@2"]["pool_fingerprint"]}
    answer = result["provisional_answer_aggregate"]["required_fact_recall"]
    assert answer["value"] == 1
    assert answer["denominator"] == 1
    assert answer["evaluable_unit_ids"] == ["p1:f1"]
    assert answer["review_bases"] == {"p1": "agent_review"}
    assert result["provisional_answer_aggregate"]["answer_pass"]["value"] == 1
    assert result["approved_answer_aggregate"]["required_fact_recall"]["value"] is None
    assert result["approved_aggregate"]["final.pool_ndcg@2"]["value"] is None
    assert json.loads(paths["output"].read_text(encoding="utf-8")) == result
    assert "固定池 nDCG" in paths["output"].with_suffix(".md").read_text(encoding="utf-8")


def test_score_without_answer_reviews_keeps_unknown_separate_from_zero(work_path: Path) -> None:
    result = _score(_scoring_inputs(work_path), with_reviews=False)
    assert result["answer_rubric_version"] is None
    metric = result["cases"][0]["generation_assessment"]["provisional"]["metrics"][
        "required_fact_recall"
    ]
    assert metric["value"] is None and metric["reason"] == "answer_not_reviewed"
    assert result["provisional_answer_aggregate"]["required_fact_recall"]["denominator"] == 0


@pytest.mark.parametrize("change", ["seal", "duplicate", "capture_binding"])
def test_score_rejects_unbound_pool_or_answer_review(work_path: Path, change: str) -> None:
    paths = _scoring_inputs(work_path)
    if change == "capture_binding":
        value = json.loads(paths["assessments"].read_text(encoding="utf-8"))
        value["capture_sha256"] = "b" * 64
        _write(paths["assessments"], value)
        expected = "different capture"
    else:
        value = json.loads(paths["pools"].read_text(encoding="utf-8"))
        if change == "seal":
            value["pools"][0]["selection_policy"] = "Changed after freezing"
            expected = "seal mismatch"
        else:
            value["pools"].append(deepcopy(value["pools"][0]))
            expected = "duplicate ranking pool"
        _write(paths["pools"], value)
    with pytest.raises(ValueError, match=expected):
        _score(paths)


def _runtime_record(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, *, asynchronous: bool
) -> dict[str, Any]:
    def fake_post(self: LLMRuntime, url: str, **kwargs: Any) -> httpx.Response:
        return response

    async def fake_apost(self: LLMRuntime, url: str, **kwargs: Any) -> httpx.Response:
        return response

    monkeypatch.setattr(LLMRuntime, "post", fake_post)
    monkeypatch.setattr(LLMRuntime, "apost", fake_apost)

    async def run() -> dict[str, Any]:
        runtime = RecordedLLMRuntime(1)
        try:
            kwargs: dict[str, Any] = {
                "timeout": 1.0,
                "headers": {"Authorization": "Bearer transport-secret"},
                "json": {"model": "planner", "messages": [{"role": "user", "content": "问题"}]},
            }
            actual = (
                await runtime.apost("https://private-endpoint.invalid", **kwargs)
                if asynchronous
                else runtime.post("https://private-endpoint.invalid", **kwargs)
            )
            assert actual is response
            assert len(runtime.calls) == 1
            return runtime.calls[0]
        finally:
            await runtime.aclose()

    return asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_runtime_retains_planner_output_and_only_allowlisted_usage(
    monkeypatch: pytest.MonkeyPatch, asynchronous: bool
) -> None:
    planner = '{"route":"retrieval","year_start":1973}'
    response = httpx.Response(
        200,
        headers={"x-secret": "response-header-secret"},
        json={
            "model": "planner-model",
            "headers": {"Authorization": "body-header-secret"},
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": planner,
                        "reasoning_content": "hidden-reasoning-secret",
                        "tool_calls": [{"secret": "tool-secret"}],
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 30,
                "completion_tokens": 12,
                "total_tokens": 42,
                "prompt_cache_hit_tokens": True,
                "prompt_cache_miss_tokens": -1,
                "completion_tokens_details": {"reasoning_tokens": 100},
                "private": "usage-secret",
            },
        },
    )
    record = _runtime_record(monkeypatch, response, asynchronous=asynchronous)
    summary = record["response_summary"]
    assert summary["model"] == "planner-model"
    assert summary["choices"][0]["message"] == {"role": "assistant", "content": planner}
    assert summary["usage"] == {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42}
    serialized = json.dumps(record)
    assert "secret" not in serialized
    assert "reasoning_content" not in serialized
    assert "Authorization" not in serialized
    assert "private-endpoint" not in serialized


@pytest.mark.parametrize("choices", [None, {}, "unexpected", 9, [None, {}, {"message": 2}]])
def test_runtime_unexpected_choices_cannot_break_successful_http_return(
    monkeypatch: pytest.MonkeyPatch, choices: Any
) -> None:
    response = httpx.Response(200, json={"choices": choices, "usage": []})
    record = _runtime_record(monkeypatch, response, asynchronous=False)
    assert record["status"] == "response"
    assert record["response_summary"]["choices"] == []
    assert record["response_summary"]["usage"] == {}


@pytest.mark.parametrize("status", [201, 400, 503])
def test_runtime_non_200_response_never_saves_error_body(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    response = httpx.Response(status, json={"error": "Authorization Bearer body-secret"})
    record = _runtime_record(monkeypatch, response, asynchronous=True)
    assert record["http_status"] == status
    assert "response_summary" not in record
    assert "body-secret" not in json.dumps(record)


@pytest.mark.parametrize(
    ("body", "expected"), [(b"not-json", "invalid_json"), (b"[]", "unexpected_shape")]
)
def test_runtime_non_object_or_non_json_body_is_still_returned(
    monkeypatch: pytest.MonkeyPatch, body: bytes, expected: str
) -> None:
    record = _runtime_record(monkeypatch, httpx.Response(200, content=body), asynchronous=False)
    assert record["response_capture_status"] == expected
    assert "response_summary" not in record


def _comparison_report() -> dict[str, Any]:
    return {
        "evaluator_version": "v2",
        "dataset_sha256": "dataset",
        "corpus_sha256": "corpus",
        "source_sha256": "source",
        "k_values": [2],
        "cases": [{"case_id": "p1"}],
        "config": {"top_k": 2, "candidate_k": 30},
        "index_attribution": {"attribution_safe": True},
        "component_candidate_fingerprints": {"p1": {"keyword_candidates": "same"}},
        "answer_rubric_version": "explicit-answer-review-v1",
        "provisional_aggregate": {
            "final.pool_ndcg@2": {
                "value": 0.5,
                "evaluable_case_ids": ["p1"],
                "pool_fingerprints": {"p1": "pool-v1"},
            }
        },
        "provisional_answer_aggregate": {
            "required_fact_recall": {
                "value": 0.5,
                "evaluable_case_ids": ["p1"],
                "evaluable_unit_ids": ["p1:f1", "p1:f2"],
                "review_bases": {"p1": "agent_review"},
            }
        },
    }


@pytest.mark.parametrize("changed", [{"p1": "other-pool"}, None, {"p1": None}])
def test_compare_pool_ndcg_requires_same_known_pool_fingerprints(changed: Any) -> None:
    left, right = _comparison_report(), _comparison_report()
    right["provisional_aggregate"]["final.pool_ndcg@2"]["pool_fingerprints"] = changed
    if changed == {"p1": None}:
        left["provisional_aggregate"]["final.pool_ndcg@2"]["pool_fingerprints"] = changed
    result = compare(left, right)
    assert result["compatible"]
    assert not result["metrics"]["final.pool_ndcg@2"]["comparable"]
    assert result["metrics"]["final.pool_ndcg@2"]["delta"] is None


def test_compare_answer_metric_allows_identical_rubric_units_and_review_basis() -> None:
    left, right = _comparison_report(), _comparison_report()
    right["provisional_answer_aggregate"]["required_fact_recall"]["value"] = 1
    result = compare(left, right)
    assert result["answer_metrics"]["required_fact_recall"]["comparable"]
    assert result["answer_metrics"]["required_fact_recall"]["delta"] == 0.5
    assert result["metrics"]["final.pool_ndcg@2"]["comparable"]


@pytest.mark.parametrize("changed", ["rubric", "units", "basis", "unknown"])
def test_compare_answer_metric_rejects_different_scoring_basis(changed: str) -> None:
    left, right = _comparison_report(), _comparison_report()
    metric = right["provisional_answer_aggregate"]["required_fact_recall"]
    if changed == "rubric":
        right["answer_rubric_version"] = "different-rubric"
    elif changed == "units":
        metric["evaluable_unit_ids"] = ["p1:f1", "p1:f3"]
    elif changed == "basis":
        metric["review_bases"] = {"p1": "human_review"}
    else:
        metric["value"] = None
    result = compare(left, right)
    assert result["compatible"]
    assert not result["answer_metrics"]["required_fact_recall"]["comparable"]
    assert result["answer_metrics"]["required_fact_recall"]["delta"] is None


@pytest.mark.parametrize("missing", ["rubric", "units", "basis_field", "basis_value"])
def test_compare_answer_metric_requires_known_nonempty_scoring_basis(missing: str) -> None:
    left, right = _comparison_report(), _comparison_report()
    for report in (left, right):
        metric = report["provisional_answer_aggregate"]["required_fact_recall"]
        if missing == "rubric":
            report.pop("answer_rubric_version")
        elif missing == "units":
            metric["evaluable_unit_ids"] = []
        elif missing == "basis_field":
            metric.pop("review_bases")
        else:
            metric["review_bases"] = {"p1": None}
    result = compare(left, right)
    assert result["compatible"]
    assert not result["answer_metrics"]["required_fact_recall"]["comparable"]
    assert result["answer_metrics"]["required_fact_recall"]["delta"] is None
