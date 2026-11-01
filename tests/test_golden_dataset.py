from __future__ import annotations

import json
from pathlib import Path

from history_agent.evaluation.pilot_models import PilotDataset

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/golden/golden_dataset.json"
DELETED = {
    "holdout_exact_decision",
    "pilot_semantic_deng_1962_agriculture",
    "pilot_multievidence_zunyi_leadership",
    "holdout_multi_sources",
    "pilot_negative_cppcc_1949",
    "pilot_constraint_deng_1973_march",
    "holdout_constraint_source_month",
    "dev_refusal_source_year",
    "holdout_refusal_insufficient",
}


def _load() -> dict:
    return json.loads(DATASET.read_text(encoding="utf8"))


def test_golden_v1_2_has_expected_counts_and_no_deleted_cases() -> None:
    dataset = PilotDataset.model_validate(_load())
    assert len(dataset.cases) == 32
    assert sum(case.split == "development" for case in dataset.cases) == 22
    assert sum(case.split == "holdout" for case in dataset.cases) == 10
    assert sum(case.answerability == "answerable" for case in dataset.cases) == 28
    assert sum(case.answerability == "unanswerable" for case in dataset.cases) == 4
    assert sum(len(case.facts) for case in dataset.cases) == 143
    assert sum(len(case.evidence_groups) for case in dataset.cases) == 143
    assert sum(len(case.judgments) for case in dataset.cases) == 301
    assert sum(case.human_review.status == "approved" for case in dataset.cases) == 32
    assert all(case.human_review.status == "approved" for case in dataset.cases)
    assert not {case.id for case in dataset.cases} & DELETED


def test_golden_v1_2_rewritten_questions_and_evidence_shapes() -> None:
    dataset = PilotDataset.model_validate(_load())
    by_id = {case.id: case for case in dataset.cases}

    mao_zhou = by_id["dev_intersection_mao_zhou_1949"]
    assert mao_zhou.question == "毛泽东与周恩来在1949年有哪些有共同出席的会议？"
    assert {group.id for group in mao_zhou.evidence_groups} == {
        "joint_meeting_0607",
        "joint_meeting_0701",
        "joint_meeting_0709",
        "joint_meeting_0908",
        "joint_consultation_0925",
        "joint_meeting_1024",
        "politburo_19491026",
        "politburo_19491102",
        "politburo_19491109",
        "politburo_19491125",
        "politburo_19491128",
        "politburo_19491201",
        "joint_meeting_1201",
        "politburo_19491204",
    }
    assert len(mao_zhou.facts) == len(mao_zhou.evidence_groups) == 14

    liu_deng = by_id["holdout_intersection_positive"]
    assert liu_deng.question == (
        "1948年11月至1949年12月，刘伯承和邓小平共同指挥了哪些战略决战和战略进军？"
    )
    assert {group.id for group in liu_deng.evidence_groups} == {
        "huaihai_1948",
        "yangtze_planning_1949",
        "yangtze_crossing_1949",
        "southwest_1949",
    }
    assert len(liu_deng.facts) == 3
    assert len(liu_deng.evidence_groups) == 4


def test_golden_v1_2_candidate_labels_cover_all_answerable_cases() -> None:
    dataset = PilotDataset.model_validate(_load())
    labelled = {case.id for case in dataset.cases if case.judgments}
    assert len(labelled) == 28
    assert sum(len(case.judgments) for case in dataset.cases) == 301
    assert sum(
        judgment.basis == "llm_judge"
        for case in dataset.cases
        for judgment in case.judgments
    ) == 0
    assert sum(
        judgment.basis == "human_review"
        for case in dataset.cases
        for judgment in case.judgments
    ) == 301
    assert sum(
        judgment.basis == "agent_review"
        for case in dataset.cases
        for judgment in case.judgments
    ) == 0
