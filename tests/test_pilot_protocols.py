from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import PilotCase, PilotDataset, case_definition
from history_agent.evaluation.pilot_protocols import (
    HISTORY_CASE_ID,
    HUNAN_CASE_ID,
    capture_contract,
    load_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "evals/golden/development_annotations_v3.json"
PROTOCOLS = ROOT / "evals/golden/development_protocols_v3.json"


def _write(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")
    return path


def _release(work_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf8"))
    protocols = json.loads(PROTOCOLS.read_text(encoding="utf8"))
    return annotations, protocols, work_path / "dataset.json", work_path / "protocols.json"


def _protocol(protocols: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in protocols["cases"] if case["case_id"] == case_id)


def _rebind(annotations: dict[str, Any], protocols: dict[str, Any]) -> None:
    protocols["annotation_sha256"] = fingerprint(annotations)
    for case in annotations["cases"]:
        definition = case_definition(PilotCase.model_validate(case).model_dump(mode="json"))
        _protocol(protocols, case["id"])["case_definition_sha256"] = fingerprint(definition)


def test_release_binds_20_independent_cases_and_21_inputs_without_editing_sources() -> None:
    before = (ANNOTATIONS.read_bytes(), PROTOCOLS.read_bytes())
    inputs = load_inputs(ANNOTATIONS, PROTOCOLS)
    contract = capture_contract(inputs)
    assert inputs.is_protocol_release
    assert len(inputs.dataset.cases) == contract["independent_case_count"] == 20
    assert contract["execution_input_count"] == 21
    assert sum(len(case.facts) for case in inputs.dataset.cases) == 85
    assert sum(len(case.evidence_groups) for case in inputs.dataset.cases) == 90
    assert inputs.dataset_sha256 == fingerprint(json.loads(before[0]))
    assert inputs.protocol_sha256 == fingerprint(json.loads(before[1]))
    assert inputs.protocol_file_sha256 == hashlib.sha256(before[1]).hexdigest()
    variants = contract["input_variants"][HISTORY_CASE_ID]
    assert variants[0]["id"] == "with_history"
    assert variants[0]["history"] == [
        {"role": "user", "content": "林彪在1930—1949年相继担任哪些职务？"}
    ]
    assert variants[1]["id"] == "without_history_control"
    assert variants[1]["history"] == []
    assert variants[0]["input_sha256"] == fingerprint(
        {
            "question": variants[0]["question"],
            "history": variants[0]["history"],
        }
    )
    assert variants[0]["input_sha256"] != variants[1]["input_sha256"]
    assert all(case.human_review.status == "pending" for case in inputs.dataset.cases)
    assert (ANNOTATIONS.read_bytes(), PROTOCOLS.read_bytes()) == before


def test_release_requires_explicit_protocol_and_full_package_hash(work_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit --protocols"):
        load_inputs(ANNOTATIONS)
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    annotations["description"] += " changed"
    with pytest.raises(ValueError, match="different annotation release"):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


@pytest.mark.parametrize(
    "mutation", ["case_hash", "facts", "groups", "stage", "duplicate", "missing"]
)
def test_stale_or_incomplete_protocols_rejected(work_path: Path, mutation: str) -> None:
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    row = protocols["cases"][0]
    if mutation == "case_hash":
        row["case_definition_sha256"] = "0" * 64
    elif mutation == "facts":
        row["required_fact_ids"] = []
    elif mutation == "groups":
        row["required_evidence_group_ids"] = []
    elif mutation == "stage":
        row["stages"]["retrieval"]["denominator"] = 99
    elif mutation == "duplicate":
        protocols["cases"].append(row)
    else:
        protocols["cases"].pop()
    with pytest.raises(ValueError):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


@pytest.mark.parametrize(
    "mutation",
    [
        "input_field",
        "question",
        "extra_history",
        "history_field",
        "missing_control",
        "replaced_history",
        "assistant_fabrication",
        "control_history",
        "independent_count",
        "conversation_mismatch",
    ],
)
def test_input_contract_never_drops_or_fabricates_history(work_path: Path, mutation: str) -> None:
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    row = _protocol(protocols, HISTORY_CASE_ID)
    variant = row["input_variants"][0]
    if mutation == "input_field":
        variant["document_filter"] = "secret evidence"
    elif mutation == "question":
        variant["question"] += " 请回答"
    elif mutation == "extra_history":
        protocols["cases"][0]["input_variants"][0]["history"] = variant["history"]
    elif mutation == "history_field":
        variant["history"][0]["source"] = "fabricated"
    elif mutation == "missing_control":
        row["input_variants"].pop()
    elif mutation == "replaced_history":
        variant["history"][0]["content"] = "请介绍另一场战役"
    elif mutation == "assistant_fabrication":
        variant["history"].append({"role": "assistant", "content": "捏造的历史回答"})
    elif mutation == "control_history":
        row["input_variants"][1]["history"] = variant["history"]
    elif mutation == "independent_count":
        row["independent_case_count"] = 2
    else:
        row["specialist_protocol"]["conversation_protocol"]["treatment"]["question"] = "changed"
    with pytest.raises(ValueError):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


@pytest.mark.parametrize(
    "mutation", ["missing_year", "wrong_fact", "duplicate_fact", "denominator"]
)
def test_hunan_year_partitions_have_fixed_and_complete_denominators(
    work_path: Path,
    mutation: str,
) -> None:
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    row = _protocol(protocols, HUNAN_CASE_ID)
    boundary = row["specialist_protocol"]["answer_boundary"]
    if mutation == "missing_year":
        boundary["years"].pop()
    elif mutation == "wrong_fact":
        boundary["years"][0]["required_fact_ids"][0] = "y1922_xiang_committee"
    elif mutation == "duplicate_fact":
        boundary["years"][0]["required_fact_ids"][0] = boundary["years"][0]["required_fact_ids"][1]
    else:
        row["year_coverage"]["denominator"] = 5
    with pytest.raises(ValueError, match="Hunan"):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


def test_development_selection_cannot_substitute_a_holdout(work_path: Path) -> None:
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    annotations["cases"][0]["id"] = "holdout_disguised_as_development"
    protocols["cases"][0]["case_id"] = "holdout_disguised_as_development"
    _rebind(annotations, protocols)
    with pytest.raises(ValueError, match="20 selected development cases"):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


def test_refusal_metadata_is_not_a_positive_retrieval_denominator(work_path: Path) -> None:
    inputs = load_inputs(ANNOTATIONS, PROTOCOLS)
    refusals = [case for case in inputs.dataset.cases if case.answerability == "unanswerable"]
    assert len(refusals) == 3
    assert all(not case.facts and not case.evidence_groups for case in refusals)
    annotations, protocols, dataset_path, protocol_path = _release(work_path)
    _protocol(protocols, "dev_refusal_source_year")["stages"]["retrieval"]["denominator"] = 4
    with pytest.raises(ValueError, match="no positive ranking denominator"):
        load_inputs(_write(dataset_path, annotations), _write(protocol_path, protocols))


def test_legacy_hash_and_optional_protocol_behavior_are_unchanged() -> None:
    path = ROOT / "evals/golden/development_v2.json"
    raw = json.loads(path.read_text(encoding="utf8"))
    inputs = load_inputs(path, PROTOCOLS)
    assert not inputs.is_protocol_release
    assert inputs.dataset_sha256 == fingerprint(
        PilotDataset.model_validate(raw).model_dump(mode="json")
    )
    assert len(inputs.dataset.cases) == 13
    assert all(
        len(variants) == 1 and variants[0]["history"] == [] for variants in inputs.variants.values()
    )
    assert capture_contract(inputs)["execution_input_count"] == 13
