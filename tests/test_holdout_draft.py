from __future__ import annotations

import json
from pathlib import Path

from history_agent.evaluation.pilot_models import PilotDataset

ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "evals/golden/holdout_annotations_v1_draft6.json"
DEVELOPMENT = ROOT / "evals/golden/development_annotations_v6.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf8"))


def test_holdout_draft_has_six_pending_cases_and_expected_denominators() -> None:
    dataset = PilotDataset.model_validate(_load(HOLDOUT))
    assert len(dataset.cases) == 6
    assert all(case.split == "holdout" for case in dataset.cases)
    assert all(case.human_review.status == "pending" for case in dataset.cases)
    assert sum(len(case.facts) for case in dataset.cases) == 20
    assert sum(len(case.evidence_groups) for case in dataset.cases) == 21
    assert sum(case.answerability == "unanswerable" for case in dataset.cases) == 1


def test_holdout_cases_are_disjoint_from_development_cases() -> None:
    holdout = PilotDataset.model_validate(_load(HOLDOUT))
    development = _load(DEVELOPMENT)
    development_ids = {case["id"] for case in development["cases"]}
    assert not {case.id for case in holdout.cases} & development_ids


def test_holdout_answerable_and_refusal_contracts() -> None:
    dataset = PilotDataset.model_validate(_load(HOLDOUT))
    for case in dataset.cases:
        if case.answerability == "answerable":
            assert case.facts and case.evidence_groups
            assert all(fact.evidence_group_ids for fact in case.facts)
        else:
            assert not case.facts
            assert not case.evidence_groups
            assert case.refusal_basis
            assert case.refusal_basis.get("meta_evidence")
