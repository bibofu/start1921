from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import case_definition
from history_agent.evaluation.pilot_process_reviews import (
    evaluate_process_reviews,
    prepare_process_reviews,
)


def _inputs() -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    cases = [
        {"id": "p1", "question": "1952年他担任什么职务？", "human_review": {"status": "pending"}},
        {"id": "p2", "question": "他曾在哪里工作？", "human_review": {"status": "pending"}},
    ]
    raw_cases = []
    for case in cases:
        plan = {
            "intent": "event_overview",
            "normalized_question": case["question"],
            "retrieval_route": "hybrid",
            "start_year": 1952,
        }
        raw_cases.append(
            {
                "case_id": case["id"],
                "question": case["question"],
                "case_definition_sha256": fingerprint(case_definition(case)),
                "answer": {"query_plan": plan},
                "production_stages": [
                    {"stage": "production_1_keyword", "query": case["question"]},
                    {"stage": "production_1_vector", "query": case["question"]},
                ],
                "llm_calls": [
                    {
                        "call_index": 1,
                        "response_summary": {
                            "choices": [{"message": {"content": json.dumps(plan)}}]
                        },
                    }
                ],
            }
        )
    dataset_hash = fingerprint(cases)
    return cases, {"cases": raw_cases, "dataset_sha256": dataset_hash}, dataset_hash


def _reviewed(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    for row, status in zip(result["cases"], ("pass", "fail"), strict=True):
        row.update(
            status=status,
            basis="agent_review",
            reviewer="test-agent",
            reviewed_at="2026-10-11T09:00:00+08:00",
            reason="核对执行计划与约束后的明确判断",
        )
    return result


def _protocol_file(work_path: Path, cases: list[dict[str, Any]]) -> Path:
    path = work_path / "protocols.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": case["id"],
                        "case_definition_sha256": fingerprint(case_definition(case)),
                        "stages": {
                            "query_understanding": {
                                "criterion": "保留显式时间与人物约束",
                                "denominator": 1,
                            }
                        },
                    }
                    for case in cases
                ]
            }
        ),
        encoding="utf8",
    )
    return path


def test_template_binds_trace_but_never_invents_approval() -> None:
    cases, capture, sha = _inputs()
    template = prepare_process_reviews(cases, capture, sha)
    assert template["schema_version"] == 2
    assert template["capture_sha256"] == fingerprint(capture)
    assert all(row["status"] == "unknown" for row in template["cases"])
    assert all(row["basis"] is None and row["reviewer"] is None for row in template["cases"])
    assert template["cases"][0]["observed_query_variants"] == [cases[0]["question"]]
    assert template["cases"][0]["raw_planner_call_index"] == 1
    result = evaluate_process_reviews(template, cases, capture, sha)
    assert result["provisional_aggregate"]["value"] is None
    assert result["provisional_aggregate"]["denominator"] == 0
    assert result["approved_aggregate"]["denominator"] == 0


def test_absent_review_is_na_not_zero() -> None:
    cases, capture, sha = _inputs()
    result = evaluate_process_reviews(None, cases, capture, sha)
    aggregate = result["provisional_aggregate"]
    assert aggregate["value"] is None
    assert aggregate["numerator"] is None
    assert aggregate["denominator"] == 0
    assert aggregate["total_cases"] == 2
    assert set(aggregate["unevaluable_reasons"].values()) == {"process_not_reviewed"}


def test_legacy_aggregate_and_formal_fields_cannot_forge_scores() -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload["schema_version"] = 1
    payload.pop("rubric_version")
    payload["provisional_aggregate"] = {"value": 1, "numerator": 500, "denominator": 500}
    payload["formal_aggregate"] = {"value": 1, "evaluable": True}
    for row in payload["cases"]:
        row["formal"] = {"value": 1, "evaluable": True}
        row["value"] = int(row["status"] == "pass")
    result = evaluate_process_reviews(payload, cases, capture, sha)
    assert result["provisional_aggregate"]["value"] == 0.5
    assert result["provisional_aggregate"]["numerator"] == 1
    assert result["provisional_aggregate"]["denominator"] == 2
    assert result["approved_aggregate"]["value"] is None


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("capture_sha256", "a" * 64, "different capture"),
        ("dataset_sha256", "a" * 64, "different dataset"),
    ],
)
def test_wrong_packet_binding_rejected(field: str, value: str, match: str) -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload[field] = value
    with pytest.raises(ValueError, match=match):
        evaluate_process_reviews(payload, cases, capture, sha)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("case_id", "unknown", "unknown process reviewed case"),
        ("case_definition_sha256", "a" * 64, "case definition changed"),
        ("executed_query_plan", {"year": 1973}, "executed query plan changed"),
        ("observed_query_variants", ["wrong query"], "query variants changed"),
        ("raw_planner_call_index", 3, "planner call missing"),
        ("raw_planner_response_sha256", "a" * 64, "raw planner response changed"),
        ("raw_planner_plan", {"year": 1973}, "raw planner plan changed"),
        ("raw_to_executed_plan_changed", True, "comparison is inconsistent"),
        ("value", 0, "contradicts its explicit status"),
    ],
)
def test_wrong_case_snapshot_rejected(field: str, value: Any, match: str) -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload["cases"][0][field] = value
    with pytest.raises(ValueError, match=match):
        evaluate_process_reviews(payload, cases, capture, sha)


def test_duplicate_reviews_and_capture_cases_rejected() -> None:
    cases, capture, sha = _inputs()
    payload = prepare_process_reviews(cases, capture, sha)
    payload["cases"].append(deepcopy(payload["cases"][0]))
    with pytest.raises(ValueError, match="duplicate process review cases"):
        evaluate_process_reviews(payload, cases, capture, sha)
    capture["cases"].append(deepcopy(capture["cases"][0]))
    with pytest.raises(ValueError, match="duplicate dataset or capture"):
        prepare_process_reviews(cases, capture, sha)


@pytest.mark.parametrize("missing", ["basis", "reviewer", "reviewed_at"])
def test_human_scores_require_audit_fields(missing: str) -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload["cases"][0]["basis"] = "human_review"
    payload["cases"][0][missing] = None
    with pytest.raises(ValueError, match="process decisions require"):
        evaluate_process_reviews(payload, cases, capture, sha)


def test_approved_metric_requires_case_and_process_human_review() -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload["cases"][0]["basis"] = "human_review"
    assert (
        evaluate_process_reviews(payload, cases, capture, sha)["approved_aggregate"]["denominator"]
        == 0
    )
    cases[0]["human_review"] = {
        "status": "approved",
        "reviewed_by": "Human reviewer",
        "reviewed_at": "2026-10-11T09:00:00+08:00",
        "confirmations": {name: True for name in ("question", "evidence", "facts", "refusal")},
    }
    # Adding a case approval does not alter its question/evidence definition.
    sha = fingerprint(cases)
    payload["dataset_sha256"] = sha
    result = evaluate_process_reviews(payload, cases, capture, sha)
    assert result["approved_aggregate"]["value"] == 1
    assert result["approved_aggregate"]["denominator"] == 1


def test_partial_reviews_and_unknown_are_excluded_from_denominator() -> None:
    cases, capture, sha = _inputs()
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    payload["cases"] = payload["cases"][:1]
    result = evaluate_process_reviews(payload, cases, capture, sha)
    assert result["provisional_aggregate"]["value"] == 1
    assert result["provisional_aggregate"]["denominator"] == 1
    assert result["provisional_aggregate"]["unevaluable_reasons"] == {"p2": "process_not_reviewed"}
    payload["cases"][0]["status"] = "unknown"
    assert (
        evaluate_process_reviews(payload, cases, capture, sha)["provisional_aggregate"]["value"]
        is None
    )


def test_no_effective_trace_is_unscorable_even_if_review_claims_pass() -> None:
    cases, capture, sha = _inputs()
    for raw in capture["cases"]:
        raw["answer"] = {}
        raw["production_stages"] = []
    payload = _reviewed(prepare_process_reviews(cases, capture, sha))
    result = evaluate_process_reviews(payload, cases, capture, sha)
    assert result["provisional_aggregate"]["value"] is None
    assert set(result["provisional_aggregate"]["unevaluable_reasons"].values()) == {
        "query_understanding_trace_unavailable"
    }


def test_bound_protocol_must_be_explicit_and_match_bytes_and_criterion(work_path: Path) -> None:
    cases, capture, sha = _inputs()
    path = _protocol_file(work_path, cases)
    payload = _reviewed(prepare_process_reviews(cases, capture, sha, protocol_path=path))
    assert payload["protocol_file_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="bound protocol_path"):
        evaluate_process_reviews(payload, cases, capture, sha)
    assert (
        evaluate_process_reviews(payload, cases, capture, sha, protocol_path=path)[
            "provisional_aggregate"
        ]["denominator"]
        == 2
    )
    changed = deepcopy(payload)
    changed["cases"][0]["criterion"] = "改变评分要求"
    with pytest.raises(ValueError, match="criterion differs"):
        evaluate_process_reviews(changed, cases, capture, sha, protocol_path=path)
    path.write_text(path.read_text(encoding="utf8") + "\n", encoding="utf8")
    with pytest.raises(ValueError, match="protocol file hash differs"):
        evaluate_process_reviews(payload, cases, capture, sha, protocol_path=path)


def test_protocol_case_binding_is_verified(work_path: Path) -> None:
    cases, capture, sha = _inputs()
    path = _protocol_file(work_path, cases)
    protocol = json.loads(path.read_text(encoding="utf8"))
    protocol["cases"][0]["case_definition_sha256"] = "a" * 64
    path.write_text(json.dumps(protocol), encoding="utf8")
    with pytest.raises(ValueError, match="protocol missing or case definition changed"):
        prepare_process_reviews(cases, capture, sha, protocol_path=path)
