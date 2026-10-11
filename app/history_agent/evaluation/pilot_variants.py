"""Bind protocol execution inputs and isolate control-arm review artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from history_agent.answering.models import QuestionRequest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import case_definition
from history_agent.evaluation.pilot_protocols import EvaluationInputs, capture_contract


def _rows(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"capture {field} must be a list of case records")
    return value


def _input_key(row: dict[str, Any]) -> tuple[str, str]:
    case_id, variant_id = row.get("case_id"), row.get("input_variant_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("capture case ID is missing or invalid")
    if not isinstance(variant_id, str) or not variant_id.strip():
        raise ValueError(f"capture input variant ID is missing or invalid: {case_id}")
    return case_id, variant_id


def validate_protocol_capture(inputs: EvaluationInputs, capture: dict[str, Any]) -> None:
    """Reject incomplete runs and changed histories before scoring or preparing reviews.

    Legacy schema 1 captures remain readable against their legacy datasets. A
    protocol release can never inherit that compatibility escape hatch.
    """
    if "execution_contract" not in capture:
        if (
            inputs.is_protocol_release
            or type(capture.get("schema_version")) is not int
            or capture["schema_version"] != 1
        ):
            raise ValueError("capture requires a bound execution contract; recollect")
        if capture.get("control_cases"):
            raise ValueError("legacy captures cannot contain unbound control inputs")
        return
    if type(capture.get("schema_version")) is not int or capture["schema_version"] != 2:
        raise ValueError("protocol capture must use schema version 2")
    contract = capture.get("execution_contract")
    if not isinstance(contract, dict) or fingerprint(contract) != fingerprint(
        capture_contract(inputs)
    ):
        raise ValueError("capture execution contract differs from dataset/protocol inputs")
    if capture.get("dataset_sha256") != inputs.dataset_sha256:
        raise ValueError("capture dataset hash differs from execution inputs")

    config = capture.get("config")
    top_k = config.get("answer_top_k") if isinstance(config, dict) else None
    if type(top_k) is not int or not 1 <= top_k <= 12:
        raise ValueError("capture config.answer_top_k must be an integer from 1 through 12")
    cases = {case.id: case for case in inputs.dataset.cases}
    primary = {
        (case_id, variants[0]["id"]): variants[0] for case_id, variants in inputs.variants.items()
    }
    controls = {
        (case_id, variant["id"]): variant
        for case_id, variants in inputs.variants.items()
        for variant in variants[1:]
    }
    for field, expected in (("cases", primary), ("control_cases", controls)):
        records = _rows(capture.get(field, []), field)
        keys = [_input_key(row) for row in records]
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate capture {field} input IDs")
        if set(keys) != set(expected):
            raise ValueError(f"capture {field} inputs differ from the complete protocol")
        for raw, key in zip(records, keys, strict=True):
            case_id, _ = key
            variant = expected[key]
            definition_sha256 = fingerprint(case_definition(cases[case_id].model_dump(mode="json")))
            if raw.get("case_definition_sha256") != definition_sha256:
                raise ValueError(f"capture case definition changed: {case_id}")
            if raw.get("question") != variant["question"]:
                raise ValueError(f"capture question differs from input: {case_id}")
            request = QuestionRequest(
                question=variant["question"],
                history=variant["history"],
                top_k=top_k,
                session_id=None,
            ).model_dump(mode="json")
            if not isinstance(raw.get("request"), dict) or fingerprint(
                raw["request"]
            ) != fingerprint(request):
                raise ValueError(f"capture request/history differs from protocol input: {case_id}")
            expected_sha256 = fingerprint(
                {"question": variant["question"], "history": variant["history"]}
            )
            if raw.get("input_sha256") != expected_sha256:
                raise ValueError(f"capture input hash differs from protocol input: {case_id}")


def list_control_variants(capture: dict[str, Any]) -> list[str]:
    """Return control IDs in captured order without counting them as new questions."""
    variants: list[str] = []
    for row in _rows(capture.get("control_cases", []), "control_cases"):
        _, variant = _input_key(row)
        if variant not in variants:
            variants.append(variant)
    return variants


def project_control_capture(capture: dict[str, Any], variant_id: str) -> dict[str, Any]:
    """Create a separate review binding while preserving the full-run identity.

    Validate the complete source capture first. The projection intentionally has
    only the selected control cases and is not a complete protocol execution.
    """
    if variant_id not in list_control_variants(capture):
        raise ValueError(f"capture does not contain control variant: {variant_id}")
    records = [row for row in capture["control_cases"] if row["input_variant_id"] == variant_id]
    ids = [row["case_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate control case IDs: {variant_id}")
    projected = deepcopy(
        {key: value for key, value in capture.items() if key not in {"cases", "control_cases"}}
    )
    projected["cases"] = deepcopy(records)
    projected["component_candidate_fingerprints"] = {
        row["case_id"]: deepcopy(row.get("component_candidate_fingerprints", {})) for row in records
    }
    projected["parent_capture_sha256"] = fingerprint(capture)
    projected["control_variant_id"] = variant_id
    return projected
