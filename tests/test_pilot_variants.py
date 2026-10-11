from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.answering.models import QuestionRequest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import case_definition
from history_agent.evaluation.pilot_protocols import EvaluationInputs, capture_contract, load_inputs
from history_agent.evaluation.pilot_variants import (
    list_control_variants,
    project_control_capture,
    validate_protocol_capture,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORY_CASE = "dev_constraint_history_isolation"
CONTROL = "without_history_control"


@pytest.fixture(scope="module")
def inputs() -> EvaluationInputs:
    return load_inputs(
        ROOT / "evals/golden/development_annotations_v3.json",
        ROOT / "evals/golden/development_protocols_v3.json",
    )


@pytest.fixture
def capture(inputs: EvaluationInputs) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 2,
        "dataset_sha256": inputs.dataset_sha256,
        "execution_contract": capture_contract(inputs),
        "config": {"answer_top_k": 10},
        "cases": [],
        "control_cases": [],
    }
    for case in inputs.dataset.cases:
        for position, variant in enumerate(inputs.variants[case.id]):
            row = {
                "case_id": case.id,
                "case_definition_sha256": fingerprint(
                    case_definition(case.model_dump(mode="json"))
                ),
                "question": variant["question"],
                "input_variant_id": variant["id"],
                "input_sha256": fingerprint(
                    {"question": variant["question"], "history": variant["history"]}
                ),
                "request": QuestionRequest(
                    question=variant["question"], history=variant["history"], top_k=10
                ).model_dump(mode="json"),
                "answer": {"answer": "同样的答案", "citations": []},
                "component_candidate_fingerprints": {"keyword_candidates": variant["id"]},
            }
            result["cases" if position == 0 else "control_cases"].append(row)
    return result


def _history(capture: dict[str, Any]) -> dict[str, Any]:
    return next(row for row in capture["cases"] if row["case_id"] == HISTORY_CASE)


def test_twenty_questions_require_twenty_one_bound_inputs(
    inputs: EvaluationInputs, capture: dict[str, Any]
) -> None:
    validate_protocol_capture(inputs, capture)
    assert len(capture["cases"]) == 20
    assert len(capture["control_cases"]) == 1
    assert _history(capture)["request"]["history"] == [
        {"role": "user", "content": "林彪在1930—1949年相继担任哪些职务？"}
    ]
    assert capture["control_cases"][0]["request"]["history"] == []
    assert all(row["request"]["session_id"] is None for row in capture["cases"])


@pytest.mark.parametrize("field", ["cases", "control_cases"])
def test_missing_duplicate_or_wrong_arm_records_rejected(
    inputs: EvaluationInputs, capture: dict[str, Any], field: str
) -> None:
    missing = deepcopy(capture)
    missing[field].pop()
    with pytest.raises(ValueError, match="complete protocol"):
        validate_protocol_capture(inputs, missing)
    duplicate = deepcopy(capture)
    duplicate[field].append(deepcopy(duplicate[field][0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_protocol_capture(inputs, duplicate)
    wrong_arm = deepcopy(capture)
    target = "cases" if field == "control_cases" else "control_cases"
    wrong_arm[target].append(wrong_arm[field].pop())
    with pytest.raises(ValueError, match="complete protocol"):
        validate_protocol_capture(inputs, wrong_arm)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("case_definition_sha256", "old-labels"),
        ("question", "另一道题？"),
        ("input_variant_id", "single_turn"),
        ("input_sha256", "different-input"),
        ("request", {}),
    ],
)
def test_each_captured_input_is_checked_against_protocol(
    inputs: EvaluationInputs, capture: dict[str, Any], field: str, changed: Any
) -> None:
    _history(capture)[field] = changed
    with pytest.raises(ValueError):
        validate_protocol_capture(inputs, capture)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("question", "另一道题？"),
        ("history", []),
        ("history", [{"role": "assistant", "content": "虚构的回答"}]),
        ("top_k", 9),
        ("top_k", True),
        ("session_id", "shared-session-1234"),
        ("unexpected", "extra input"),
    ],
)
def test_request_cannot_change_or_fabricate_inputs_even_if_hash_is_recomputed(
    inputs: EvaluationInputs, capture: dict[str, Any], field: str, changed: Any
) -> None:
    row = _history(capture)
    row["request"][field] = changed
    row["input_sha256"] = fingerprint({key: row["request"][key] for key in ("question", "history")})
    with pytest.raises(ValueError, match="request/history"):
        validate_protocol_capture(inputs, capture)


def test_control_cannot_reuse_treatment_request(
    inputs: EvaluationInputs, capture: dict[str, Any]
) -> None:
    capture["control_cases"][0]["request"] = deepcopy(_history(capture)["request"])
    with pytest.raises(ValueError, match="request/history"):
        validate_protocol_capture(inputs, capture)


@pytest.mark.parametrize("top_k", [None, True, 0, 13, "10"])
def test_invalid_shared_request_budget_rejected(
    inputs: EvaluationInputs, capture: dict[str, Any], top_k: Any
) -> None:
    capture["config"]["answer_top_k"] = top_k
    with pytest.raises(ValueError, match="answer_top_k"):
        validate_protocol_capture(inputs, capture)


@pytest.mark.parametrize("field", ["protocol_sha256", "protocol_file_sha256", "dataset_sha256"])
def test_capture_contract_must_match_complete_input_package(
    inputs: EvaluationInputs, capture: dict[str, Any], field: str
) -> None:
    capture["execution_contract"][field] = "stale"
    with pytest.raises(ValueError, match="execution contract"):
        validate_protocol_capture(inputs, capture)


def test_unknown_execution_contract_field_and_top_level_dataset_hash_rejected(
    inputs: EvaluationInputs, capture: dict[str, Any]
) -> None:
    extra = deepcopy(capture)
    extra["execution_contract"]["unexpected"] = "field"
    with pytest.raises(ValueError, match="execution contract"):
        validate_protocol_capture(inputs, extra)
    capture["dataset_sha256"] = "old-release"
    with pytest.raises(ValueError, match="dataset hash"):
        validate_protocol_capture(inputs, capture)


def test_old_thirteen_case_capture_cannot_be_scored_as_twenty_case_release(
    inputs: EvaluationInputs, capture: dict[str, Any]
) -> None:
    capture["schema_version"] = 1
    capture.pop("execution_contract")
    capture["cases"] = capture["cases"][:13]
    with pytest.raises(ValueError, match="execution contract"):
        validate_protocol_capture(inputs, capture)


def test_legacy_capture_does_not_require_new_request_fields() -> None:
    legacy_inputs = load_inputs(ROOT / "evals/golden/observations/20261005/dataset.json")
    validate_protocol_capture(legacy_inputs, {"schema_version": 1, "cases": []})
    with pytest.raises(ValueError, match="execution contract"):
        validate_protocol_capture(legacy_inputs, {"schema_version": 2, "cases": []})


def test_control_projection_has_separate_binding_and_does_not_mutate_capture(
    inputs: EvaluationInputs, capture: dict[str, Any]
) -> None:
    validate_protocol_capture(inputs, capture)
    original = deepcopy(capture)
    projected = project_control_capture(capture, CONTROL)
    assert list_control_variants(capture) == [CONTROL]
    assert projected["control_variant_id"] == CONTROL
    assert projected["parent_capture_sha256"] == fingerprint(capture)
    assert projected["execution_contract"] == capture["execution_contract"]
    assert projected["component_candidate_fingerprints"] == {
        HISTORY_CASE: {"keyword_candidates": CONTROL}
    }
    assert [row["case_id"] for row in projected["cases"]] == [HISTORY_CASE]
    assert "control_cases" not in projected
    assert fingerprint(projected) != fingerprint(capture)
    projected["cases"][0]["answer"]["answer"] = "edited"
    projected["config"]["answer_top_k"] = 1
    assert capture == original


def test_control_review_binding_includes_source_run(capture: dict[str, Any]) -> None:
    first = project_control_capture(capture, CONTROL)
    _history(capture)["answer"]["answer"] = "different treatment answer"
    second = project_control_capture(capture, CONTROL)
    assert first["cases"] == second["cases"]
    assert fingerprint(first) != fingerprint(second)


def test_control_enumeration_order_and_validation(capture: dict[str, Any]) -> None:
    second = deepcopy(capture["control_cases"][0])
    second["case_id"] = "other"
    capture["control_cases"].append(second)
    third = deepcopy(second)
    third["input_variant_id"] = "second_control"
    capture["control_cases"].append(third)
    assert list_control_variants(capture) == [CONTROL, "second_control"]
    with pytest.raises(ValueError, match="does not contain"):
        project_control_capture(capture, "missing")
    capture["control_cases"].append(deepcopy(capture["control_cases"][0]))
    with pytest.raises(ValueError, match="duplicate control"):
        project_control_capture(capture, CONTROL)


@pytest.mark.parametrize("records", [None, True, {}, [None], [{"case_id": "x"}]])
def test_malformed_control_records_are_rejected(records: Any) -> None:
    with pytest.raises(ValueError):
        list_control_variants({"control_cases": records})
