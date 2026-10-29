from __future__ import annotations

import hashlib
import json
from pathlib import Path

from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import PilotCase, case_definition
from history_agent.evaluation.pilot_protocols import capture_contract, load_inputs

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_V6 = ROOT / "evals/golden/development_annotations_v6.json"
PROTOCOLS_V6 = ROOT / "evals/golden/development_protocols_v6.json"
ANNOTATIONS_V5 = ROOT / "evals/golden/development_annotations_v5.json"
PROTOCOLS_V5 = ROOT / "evals/golden/development_protocols_v5.json"
REQUIREMENTS = ROOT / "REQUIREMENTS.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def test_v6_release_loads_with_the_frozen_denominators() -> None:
    inputs = load_inputs(ANNOTATIONS_V6, PROTOCOLS_V6)
    contract = capture_contract(inputs)
    assert inputs.is_protocol_release
    assert len(inputs.dataset.cases) == contract["independent_case_count"] == 20
    assert contract["execution_input_count"] == 21
    assert sum(len(case.facts) for case in inputs.dataset.cases) == 85
    assert sum(len(case.evidence_groups) for case in inputs.dataset.cases) == 90
    assert sum(len(case.judgments) for case in inputs.dataset.cases) == 196
    approved = [case for case in inputs.dataset.cases if case.human_review.status == "approved"]
    assert len(approved) == 8
    assert sum(case.answerability == "unanswerable" for case in inputs.dataset.cases) == 3


def test_v6_refusal_basis_matches_the_current_project_requirement() -> None:
    dataset = _load(ANNOTATIONS_V6)
    current = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    text = REQUIREMENTS.read_text(encoding="utf8")
    rebound = 0
    for case in dataset["cases"]:
        basis = (case.get("refusal_basis") or {}).get("project_basis")
        if not basis:
            continue
        rebound += 1
        assert basis["path"] == "REQUIREMENTS.md"
        assert basis["file_sha256"] == current
        assert basis["rules"]
        assert all(rule["quote"] in text for rule in basis["rules"])
    assert rebound == 2


def test_v6_protocol_binds_dataset_and_every_case_definition() -> None:
    dataset = _load(ANNOTATIONS_V6)
    protocols = _load(PROTOCOLS_V6)
    assert protocols["dataset_file"] == "evals/golden/development_annotations_v6.json"
    assert protocols["annotation_sha256"] == fingerprint(dataset)
    by_id = {row["case_id"]: row for row in protocols["cases"]}
    assert set(by_id) == {case["id"] for case in dataset["cases"]}
    for case in dataset["cases"]:
        definition = case_definition(PilotCase.model_validate(case).model_dump(mode="json"))
        assert by_id[case["id"]]["case_definition_sha256"] == fingerprint(definition)


def test_v6_does_not_rewrite_the_historical_v5_release() -> None:
    dataset = _load(ANNOTATIONS_V5)
    protocols = _load(PROTOCOLS_V5)
    assert protocols["annotation_sha256"] == fingerprint(dataset)
    by_id = {row["case_id"]: row for row in protocols["cases"]}
    for case in dataset["cases"]:
        definition = case_definition(PilotCase.model_validate(case).model_dump(mode="json"))
        assert by_id[case["id"]]["case_definition_sha256"] == fingerprint(definition)
