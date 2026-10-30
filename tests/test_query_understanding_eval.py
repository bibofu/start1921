from __future__ import annotations

from pathlib import Path

from history_agent.evaluation.query_understanding_eval import (
    Prediction,
    QueryMention,
    QueryTime,
    QueryUnderstandingCase,
    canonical_keys,
    evaluate,
    load_dataset,
    predict_with_rules,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/query_understanding/cases.json"


def test_seed_set_has_expected_shape() -> None:
    dataset = load_dataset(CASES)

    assert len(dataset.cases) == 30
    assert sum(case.split == "development" for case in dataset.cases) == 24
    assert sum(case.split == "holdout" for case in dataset.cases) == 6
    assert all(case.review_status == "agent_prepared" for case in dataset.cases)


def test_canonical_keys_normalize_variants() -> None:
    assert canonical_keys("刘伯承、邓小平") == {"刘伯承", "邓小平"}
    assert canonical_keys("中国共产党第一次全国代表大会") == {"中共一大"}
    assert canonical_keys("邓小平年谱（1904—1974）") == {"邓小平年谱"}
    assert canonical_keys("红军学校") == {"红军大学"}
    assert canonical_keys("延安整风运动") == {"延安整风"}


def test_evaluate_reports_stage_metrics() -> None:
    case = QueryUnderstandingCase(
        id="case",
        split="development",
        question="毛润之在1949年出席了哪些会议？",
        intent="general",
        route="fast_fact",
        mentions=[QueryMention(text="毛润之", type="person", canonical=["毛泽东"])],
        time=QueryTime(start=1949, end=1949, precision="year"),
    )
    prediction = Prediction(
        intent="general",
        route="fast_fact",
        canonicals=["毛泽东"],
        time=QueryTime(start=1949, end=1949, precision="year"),
        needs_clarification=False,
    )

    result = evaluate([case], {"case": prediction})

    assert result["intent_accuracy"] == 1.0
    assert result["intent_family_accuracy"] == 1.0
    assert result["route_accuracy"] == 1.0
    assert result["mention"]["f1"] == 1.0
    assert result["time"]["exact_accuracy"] == 1.0


def test_rule_prediction_uses_deterministic_plan() -> None:
    dataset = load_dataset(CASES)
    case = next(item for item in dataset.cases if item.id == "qu_dev_intersection_maozhou")

    prediction = predict_with_rules(case, ROOT / "config/person_aliases.json")

    assert prediction.intent == "intersection"
    assert prediction.time == QueryTime(start=1949, end=1949, precision="year")
    assert {"毛泽东", "周恩来"}.issubset(set(prediction.canonicals))
