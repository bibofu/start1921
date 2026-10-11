import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import PilotCase, case_definition
from history_agent.evaluation.pilot_process import BRANCH_UNION
from history_agent.evaluation.pilot_specialist import (
    evaluate_specialist_reviews,
    prepare_specialist_reviews,
)

ROOT = Path(__file__).resolve().parents[1]
PAIRED = "dev_constraint_history_isolation"
YEARLY = "dev_multi_mao_hunan"


def _inputs() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dataset = json.loads(
        (ROOT / "evals/golden/development_annotations_v3.json").read_text(encoding="utf8")
    )
    cases = [PilotCase.model_validate(case).model_dump(mode="json") for case in dataset["cases"]]
    protocols = json.loads(
        (ROOT / "evals/golden/development_protocols_v3.json").read_text(encoding="utf8")
    )
    by_protocol = {row["case_id"]: row for row in protocols["cases"]}
    capture: dict[str, Any] = {"cases": [], "control_cases": []}
    for case in cases:
        for index, variant in enumerate(by_protocol[case["id"]]["input_variants"]):
            request = {
                "question": variant["question"],
                "history": variant["history"],
                "top_k": 10,
                "session_id": None,
            }
            capture["cases" if index == 0 else "control_cases"].append(
                {
                    "case_id": case["id"],
                    "case_definition_sha256": fingerprint(case_definition(case)),
                    "input_variant_id": variant["id"],
                    "request": request,
                    "input_sha256": fingerprint(
                        {field: request[field] for field in ("question", "history")}
                    ),
                    "answer": {
                        "answer": "captured answer",
                        "query_plan": {"normalized_question": case["question"]},
                    },
                    "production_stages": [
                        {
                            "stage": "production_1_final",
                            "status": "ok",
                            "query": case["question"],
                            "hits": [],
                        }
                    ],
                }
            )
    return cases, protocols, capture


def _decide(row: dict[str, Any], status: str = "pass", basis: str = "agent_review") -> None:
    row.update(basis=basis, reviewer="test reviewer", reviewed_at="2026-10-11T10:00:00+08:00")
    for dimension in row["dimensions"].values():
        for check in dimension["checks"]:
            check.update(status=status, reason="Checked recorded observations and original source.")


def _year_report(cases: list[dict[str, Any]], protocols: dict[str, Any]) -> dict[str, Any]:
    case = next(case for case in cases if case["id"] == YEARLY)
    years = next(row for row in protocols["cases"] if row["case_id"] == YEARLY)[
        "specialist_protocol"
    ]["answer_boundary"]["years"]
    selected = next(year for year in years if year["year"] == 1925)["required_evidence_group_ids"]
    metric = {"evaluable": True, "value": 5 / 14, "numerator": 5, "denominator": 14, "reason": None}
    assessment = {
        "metrics": {"required_fact_recall": {"evaluable": True, "reason": None}},
        "fact_statuses": {fact["id"]: "covered" for fact in case["facts"]},
    }
    unavailable = {"evaluable": False, "value": None, "reason": "case_human_review_not_approved"}
    return {
        "cases": [
            {
                "case_id": YEARLY,
                "stages": [
                    {
                        "stage": "final",
                        "scope": "component",
                        "provisional": {
                            "metrics": {"required_group_recall@5": metric},
                            "diagnostics": {"at_k": {"5": {"matched_groups": selected}}},
                        },
                        "approved": {
                            "metrics": {"required_group_recall@5": unavailable},
                            "diagnostics": {"at_k": {"5": {"matched_groups": selected}}},
                        },
                    }
                ],
                "generation_assessment": {
                    "provisional": assessment,
                    "approved": {
                        "metrics": {"required_fact_recall": unavailable},
                        "fact_statuses": {},
                    },
                },
            }
        ],
        "process_summary": {
            "per_case": [
                {
                    "case_id": YEARLY,
                    "production_phase_union_diagnostics": {
                        "provisional": {BRANCH_UNION: {**metric, "matched_groups": selected}},
                        "approved": {BRANCH_UNION: {**unavailable, "matched_groups": selected}},
                    },
                }
            ]
        },
    }


def test_real_protocol_templates_preserve_checks_denominators_and_independent_cases() -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    assert len(capture["cases"]) == 20
    assert len(capture["control_cases"]) == 1
    paired_rows = [row for row in packet["cases"] if row["case_id"] == PAIRED]
    assert {row["input_variant_id"] for row in paired_rows} == {
        "with_history",
        "without_history_control",
    }
    hunan = next(row for row in packet["cases"] if row["case_id"] == YEARLY)
    assert hunan["dimensions"]["stage_criteria.query_understanding"]["denominator"] == 4
    assert hunan["dimensions"]["stage_criteria.routing"]["denominator"] == 1
    refusal = next(row for row in packet["cases"] if row["case_id"] == "dev_refusal_einstein")
    assert refusal["dimensions"]["stages.understanding_and_routing"]["denominator"] == 6
    assert (
        refusal["dimensions"]["stages.understanding_and_routing.routing_validity"]["denominator"]
        == 1
    )
    assert packet["paired_isolation"][0]["dimensions"]["history_isolation"]["denominator"] == 4
    for row in packet["cases"] + packet["paired_isolation"]:
        assert row["basis"] is None
        assert all(
            check["status"] == "unknown"
            for dimension in row["dimensions"].values()
            for check in dimension["checks"]
        )
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["independent_case_count"] == 1
    assert result["paired_cases"][0]["isolation"]["provisional"]["value"] is None


@pytest.mark.parametrize("field", ["capture_sha256", "protocols_sha256"])
def test_reviews_cannot_move_to_a_different_capture_or_protocol(field: str) -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    packet[field] = "f" * 64
    with pytest.raises(ValueError, match="binding differs"):
        evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})


def test_cannot_edit_rubric_denominator_or_input_binding() -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    packet["cases"][0]["input_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="binding differs"):
        evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    packet = prepare_specialist_reviews(cases, protocols, capture)
    first = next(iter(packet["cases"][0]["dimensions"].values()))
    first["denominator"] = 50
    with pytest.raises(ValueError, match="denominator or checks"):
        evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})


@pytest.mark.parametrize("mutation", ["basis", "reviewer", "reviewed_at"])
def test_decisions_require_auditable_identity(mutation: str) -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    _decide(packet["cases"][0])
    packet["cases"][0][mutation] = None
    with pytest.raises(ValueError, match="require reviewer"):
        evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})


def test_both_arms_require_explicit_review_and_approval_is_separate() -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    _decide(packet["paired_isolation"][0])
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    isolation = result["paired_cases"][0]["isolation"]
    assert isolation["provisional"]["value"] == 1
    assert isolation["provisional"]["denominator"] == 4
    assert isolation["approved"]["value"] is None
    treatment = next(
        row
        for row in result["cases"]
        if row["case_id"] == PAIRED and row["input_variant_id"] == "with_history"
    )
    assert treatment["dimensions"]["dimensions.query_understanding"]["provisional"]["value"] is None


@pytest.mark.parametrize("missing", ["control", "plan", "production"])
def test_pair_without_either_arm_or_trace_is_not_scored(missing: str) -> None:
    cases, protocols, capture = _inputs()
    if missing == "control":
        capture["control_cases"] = []
    elif missing == "plan":
        capture["control_cases"][0]["answer"]["query_plan"] = None
    else:
        capture["control_cases"][0]["production_stages"] = []
    packet = prepare_specialist_reviews(cases, protocols, capture)
    _decide(packet["paired_isolation"][0])
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["isolation"]["provisional"]["value"] is None


def test_explicit_partial_fail_is_not_unknown_or_a_zeroed_whole_case() -> None:
    cases, protocols, capture = _inputs()
    packet = prepare_specialist_reviews(cases, protocols, capture)
    row = packet["paired_isolation"][0]
    _decide(row)
    row["dimensions"]["history_isolation"]["checks"][0]["status"] = "fail"
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["isolation"]["provisional"]["value"] == 0.75
    row["dimensions"]["history_isolation"]["checks"][1]["status"] = "unknown"
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["isolation"]["provisional"]["value"] is None


def test_year_diagnostics_use_six_years_not_fact_weighted_average() -> None:
    cases, protocols, capture = _inputs()
    report = _year_report(cases, protocols)
    statuses = report["cases"][0]["generation_assessment"]["provisional"]["fact_statuses"]
    statuses["y1924_return_for_convalescence"] = "missing"
    result = evaluate_specialist_reviews(None, cases, protocols, capture, report, {})
    years = result["yearly_cases"][0]
    stage = next(row for row in years["stage_metrics"] if row["mode"] == "provisional")
    assert stage["year_hit_rate"]["value"] == pytest.approx(1 / 6)
    assert stage["year_macro_recall"]["value"] == pytest.approx(1 / 6)
    assert (
        next(row for row in stage["years"] if row["year"] == 1925)["required_group_recall"][
            "denominator"
        ]
        == 5
    )
    answer = years["answer_metrics"]["provisional"]
    assert answer["complete_years"]["numerator"] == 5
    assert answer["complete_years"]["denominator"] == 6
    assert answer["year_macro_fact_recall"]["value"] == pytest.approx(5 / 6)
    assert years["answer_metrics"]["approved"]["year_macro_fact_recall"]["value"] is None
    assert (
        next(row for row in years["stage_metrics"] if row["mode"] == "approved")["year_hit_rate"][
            "value"
        ]
        is None
    )


def test_unknown_year_preserves_known_years_and_invalidates_fixed_six_year_score() -> None:
    cases, protocols, capture = _inputs()
    report = _year_report(cases, protocols)
    assessment = report["cases"][0]["generation_assessment"]["provisional"]
    assessment["fact_statuses"]["y1924_return_for_convalescence"] = "unknown"
    assessment["metrics"]["required_fact_recall"]["reason"] = "unknown_fact_judgments"
    result = evaluate_specialist_reviews(None, cases, protocols, capture, report, {})
    answer = result["yearly_cases"][0]["answer_metrics"]["provisional"]
    assert answer["year_macro_fact_recall"]["value"] is None
    assert answer["complete_years"]["value"] is None
    by_year = {row["year"]: row["required_fact_recall"] for row in answer["years"]}
    assert by_year[1924]["value"] is None
    assert by_year[1925]["value"] == 1


def test_paired_quality_uses_separate_denominators_and_does_not_decide_isolation() -> None:
    cases, protocols, capture = _inputs()
    left = {"evaluable": True, "value": 0.5, "numerator": 5, "denominator": 10}
    right = {"evaluable": True, "value": 0.8, "numerator": 8, "denominator": 10}
    main = {
        "cases": [
            {
                "case_id": PAIRED,
                "generation_assessment": {
                    "provisional": {"metrics": {"required_fact_recall": left}}
                },
            }
        ]
    }
    control = deepcopy(main)
    control["cases"][0]["generation_assessment"]["provisional"]["metrics"][
        "required_fact_recall"
    ] = right
    result = evaluate_specialist_reviews(
        None, cases, protocols, capture, main, {"without_history_control": control}
    )
    pair = result["paired_cases"][0]
    delta = pair["quality"]["provisional"]["required_fact_recall"]
    assert delta["difference_with_minus_without"] == pytest.approx(-0.3)
    assert pair["isolation"]["provisional"]["value"] is None
    right["denominator"] = 9
    result = evaluate_specialist_reviews(
        None, cases, protocols, capture, main, {"without_history_control": control}
    )
    assert (
        result["paired_cases"][0]["quality"]["provisional"]["required_fact_recall"][
            "difference_with_minus_without"
        ]
        is None
    )


def test_dataset_protocol_denominator_drift_is_rejected() -> None:
    cases, protocols, capture = _inputs()
    protocol = next(row for row in protocols["cases"] if row["case_id"] == YEARLY)
    protocol["specialist_protocol"]["stage_criteria"]["query_understanding"]["denominator"] = 3
    with pytest.raises(ValueError, match="denominator mismatch"):
        prepare_specialist_reviews(cases, protocols, capture)


def test_input_history_must_match_bound_protocol_even_with_a_recomputed_hash() -> None:
    cases, protocols, capture = _inputs()
    raw = next(row for row in capture["cases"] if row["case_id"] == PAIRED)
    raw["request"]["history"] = [{"role": "user", "content": "a different conversation"}]
    raw["input_sha256"] = fingerprint(
        {field: raw["request"][field] for field in ("question", "history")}
    )
    with pytest.raises(ValueError, match="input differs from protocol"):
        prepare_specialist_reviews(cases, protocols, capture)


def test_formal_pair_requires_both_case_approval_and_human_review() -> None:
    cases, protocols, capture = _inputs()
    case = next(row for row in cases if row["id"] == PAIRED)
    case["human_review"] = {
        "status": "approved",
        "reviewed_by": "human reviewer",
        "reviewed_at": "2026-10-11T10:00:00+08:00",
        "confirmations": {name: True for name in ("question", "evidence", "facts", "refusal")},
    }
    packet = prepare_specialist_reviews(cases, protocols, capture)
    _decide(packet["paired_isolation"][0])
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["isolation"]["approved"]["value"] is None
    _decide(packet["paired_isolation"][0], basis="human_review")
    result = evaluate_specialist_reviews(packet, cases, protocols, capture, {}, {})
    assert result["paired_cases"][0]["isolation"]["approved"]["value"] == 1
