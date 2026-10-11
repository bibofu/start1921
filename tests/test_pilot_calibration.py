from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import (
    DIMENSIONS,
    AnswerReviews,
    answer_fingerprint,
    fingerprint,
)
from history_agent.evaluation.pilot_calibration import (
    build_calibration_packet,
    validate_calibration_packet,
    validate_review_decisions,
)
from history_agent.evaluation.pilot_models import case_definition
from history_agent.evaluation.pilot_protocols import load_inputs

ROOT = Path(__file__).resolve().parents[1]


def _release() -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    inputs = load_inputs(
        ROOT / "evals/golden/development_annotations_v3.json",
        ROOT / "evals/golden/development_protocols_v3.json",
    )
    assert inputs.protocols is not None
    return (
        [case.model_dump(mode="json") for case in inputs.dataset.cases],
        inputs.protocols,
        inputs.dataset_sha256,
    )


def _case(packet: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(row for row in packet["cases"] if row["case_id"] == case_id)


def test_packet_binds_frozen_20_cases_without_changing_85_fact_denominator() -> None:
    cases, protocols, digest = _release()
    original = deepcopy((cases, protocols))
    packet = build_calibration_packet(cases, protocols, dataset_sha256=digest)
    assert (cases, protocols) == original
    assert packet["independent_case_count"] == 20
    assert packet["required_fact_count"] == 85
    assert packet["protocol_sha256"] == fingerprint(protocols)
    assert packet["annotation_status"] == "guidance_only_human_pending"
    unsigned = {key: value for key, value in packet.items() if key != "calibration_sha256"}
    assert packet["calibration_sha256"] == fingerprint(unsigned)
    for case in cases:
        row = _case(packet, case["id"])
        assert row["required_fact_ids"] == [fact["id"] for fact in case["facts"]]
        assert row["case_definition_sha256"] == fingerprint(case_definition(case))
        for fact, guidance in zip(case["facts"], row["facts"], strict=True):
            assert guidance["claim"] == fact["claim"]
            assert guidance["required"] == fact["required"]
            assert guidance["semantic_requirements"]
            assert guidance["source_refs"]
    validate_calibration_packet(packet, cases, protocols, dataset_sha256=digest)


def test_guidance_keeps_binary_recall_and_separates_body_from_citations() -> None:
    cases, protocols, digest = _release()
    packet = build_calibration_packet(cases, protocols, dataset_sha256=digest)
    statuses = packet["policy"]["fact_statuses"]
    assert {name: row["score"] for name, row in statuses.items()} == {
        "covered": 1,
        "partial": 0,
        "missing": 0,
        "contradicted": 0,
        "unknown": None,
    }
    examples = _case(packet, "pilot_constraint_deng_1973_march")["examples"]
    assert examples[0]["expected_status"] == "partial"
    assert examples[0]["expected_support_status"] == "supported"
    assert examples[1]["expected_status"] == "missing"
    assert examples[1]["expected_support_status"] == "not_applicable"
    for row in packet["cases"]:
        for example in row["examples"]:
            assert example["kind"] == "synthetic_scoring_example_not_annotation"
            assert example["review_status"] == "agent_suggested_human_pending"
    citation_rule = packet["policy"]["dimension_guidance"]["citation_support"]
    assert "包括必要事实之外" in citation_rule


def test_known_dispute_years_and_paired_case_keep_scoped_boundaries() -> None:
    cases, protocols, digest = _release()
    packet = build_calibration_packet(cases, protocols, dataset_sha256=digest)
    zunyi = _case(packet, "pilot_multievidence_zunyi_leadership")
    march = next(row for row in zunyi["facts"] if row["fact_id"] == "march_group")
    assert "中旬/下旬不作硬性评分" in " ".join(march["non_requirements"])
    assert zunyi["case_human_review"]["status"] != "approved"
    hunan = _case(packet, "dev_multi_mao_hunan")
    years = hunan["specialist_boundary"]["answer_boundary"]
    assert years["year_coverage_denominator"] == 6
    assert [len(row["required_fact_ids"]) for row in years["years"]] == [2, 2, 2, 1, 5, 2]
    history = _case(packet, "dev_constraint_history_isolation")
    assert history["required_fact_count"] == 10
    assert history["specialist_boundary"]["conversation_protocol"]["isolation_denominator"] == 4


@pytest.mark.parametrize("mutation", ["rubric", "denominator", "criterion", "protocol", "digest"])
def test_altered_calibration_cannot_rebind_itself(mutation: str) -> None:
    cases, protocols, digest = _release()
    packet = build_calibration_packet(cases, protocols, dataset_sha256=digest)
    if mutation == "rubric":
        packet["rubric_version"] = "new-unreviewed-rule"
    elif mutation == "denominator":
        packet["cases"][0]["required_fact_count"] = 0
    elif mutation == "criterion":
        packet["cases"][0]["facts"][0]["criterion"] = "anything passes"
    elif mutation == "protocol":
        packet["protocol_sha256"] = "a" * 64
    else:
        packet["dataset_sha256"] = "b" * 64
    unsigned = {key: value for key, value in packet.items() if key != "calibration_sha256"}
    packet["calibration_sha256"] = fingerprint(unsigned)
    with pytest.raises(ValueError, match="calibration packet differs"):
        validate_calibration_packet(packet, cases, protocols, dataset_sha256=digest)


def test_legacy_cases_can_get_guidance_without_becoming_protocol_release() -> None:
    inputs = load_inputs(ROOT / "evals/golden/development_v2.json")
    cases = [case.model_dump(mode="json") for case in inputs.dataset.cases]
    packet = build_calibration_packet(cases, dataset_sha256=inputs.dataset_sha256)
    assert len(packet["cases"]) == 13
    assert packet["protocol_sha256"] is None
    assert packet["required_fact_count"] == 43


def test_changed_case_cannot_use_frozen_protocol_guidance() -> None:
    cases, protocols, digest = _release()
    cases[0]["facts"][0]["claim"] = "Changed meaning"
    with pytest.raises(ValueError, match="different case definition"):
        build_calibration_packet(cases, protocols, dataset_sha256=digest)


def _review_fixture(
    case_id: str = "pilot_exact_deng_1952_appointment",
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    cases, protocols, _ = _release()
    case = next(row for row in cases if row["id"] == case_id)
    answer = {"answer": "已核对正文中的明确命题。", "citations": [{"evidence_id": "E1"}]}
    capture = {
        "cases": [
            {
                "case_id": case_id,
                "case_definition_sha256": fingerprint(case_definition(case)),
                "answer": answer,
            }
        ]
    }
    reviews = {
        "capture_sha256": fingerprint(capture),
        "cases": [
            {
                "case_id": case_id,
                "case_definition_sha256": fingerprint(case_definition(case)),
                "answer_sha256": answer_fingerprint(answer),
                "basis": "agent_review",
                "reviewer": "test reviewer",
                "reviewed_at": "2026-10-11T12:00:00+08:00",
                "facts": [
                    {
                        "fact_id": fact["id"],
                        "status": "covered",
                        "reason": "已按冻结命题核对正文及交付原文。",
                        "answer_excerpt": "已核对正文中的明确命题。",
                        "cited_evidence_ids": ["E1"],
                        "support_status": "supported",
                    }
                    for fact in case["facts"]
                ],
                "dimensions": {
                    name: {"status": "unknown", "reason": "待复核"} for name in DIMENSIONS
                },
            }
        ],
    }
    return reviews, capture, [case], protocols


def test_new_review_accepts_explicit_excerpts_without_semantic_auto_judging() -> None:
    reviews, capture, cases, protocols = _review_fixture()
    validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


@pytest.mark.parametrize("status", ["covered", "partial", "contradicted"])
def test_expressed_fact_needs_body_excerpt(status: str) -> None:
    reviews, capture, cases, protocols = _review_fixture()
    reviews["cases"][0]["facts"][0].update(status=status, answer_excerpt=None)
    with pytest.raises(ValueError, match="verbatim answer excerpt"):
        validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


@pytest.mark.parametrize("support", ["supported", "partial", "unsupported"])
def test_missing_body_fact_cannot_claim_citation_support(support: str) -> None:
    reviews, capture, cases, protocols = _review_fixture()
    reviews["cases"][0]["facts"][0].update(status="missing", support_status=support)
    with pytest.raises(ValueError, match="missing body fact"):
        validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


@pytest.mark.parametrize(
    "reason",
    ["待复核", "pending", "不适用", "TODO", "待逐事实复核", "待本次回答复核", "awaiting_review"],
)
def test_judgment_placeholder_is_rejected(reason: str) -> None:
    reviews, capture, cases, protocols = _review_fixture()
    reviews["cases"][0]["facts"][0]["reason"] = reason
    with pytest.raises(ValueError, match="substantive reason"):
        validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


def test_changed_definition_without_protocol_uses_original_claim_not_stale_examples() -> None:
    cases, _, digest = _release()
    case = next(row for row in cases if row["id"] == "pilot_multievidence_zunyi_leadership")
    case["facts"][2]["claim"] = "New release fact needs its own calibration."
    packet = build_calibration_packet([case], dataset_sha256=digest)
    row = packet["cases"][0]
    assert row["case_specific_guidance_applied"] is False
    assert row["examples"] == []
    assert row["boundary_notes"] == []
    assert row["facts"][2]["semantic_requirements"] == [case["facts"][2]["claim"]]


@pytest.mark.parametrize(
    "dimension,case_id",
    [
        ("routing", "pilot_exact_deng_1952_appointment"),
        ("citation_support", "pilot_exact_deng_1952_appointment"),
        ("time_constraint", "pilot_exact_deng_1952_appointment"),
        ("source_constraint", "pilot_constraint_deng_1973_march"),
        ("source_constraint", "dev_semantic_contradiction"),
        ("safe_refusal", "dev_refusal_einstein"),
        ("scope_explanation", "dev_refusal_source_year"),
    ],
)
def test_demonstrably_applicable_dimension_cannot_be_na(dimension: str, case_id: str) -> None:
    reviews, capture, cases, protocols = _review_fixture(case_id)
    reviews["cases"][0]["dimensions"][dimension] = {
        "status": "not_applicable",
        "reason": "此处错误尝试跳过已有约束。",
    }
    with pytest.raises(ValueError, match="applicable dimension cannot be N/A"):
        validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


def test_nonexclusive_annotation_source_can_be_explicitly_not_applicable() -> None:
    reviews, capture, cases, protocols = _review_fixture()
    reviews["cases"][0]["dimensions"]["source_constraint"] = {
        "status": "not_applicable",
        "reason": "题干未限定来源，协议取材范围也非硬限制。",
    }
    validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)


def test_delivered_refusal_metadata_requires_citation_review_but_not_positive_fact() -> None:
    reviews, capture, cases, protocols = _review_fixture("dev_refusal_source_year")
    assert not reviews["cases"][0]["facts"]
    reviews["cases"][0]["dimensions"]["citation_support"] = {
        "status": "not_applicable",
        "reason": "虽交付出版说明引用但尝试省略核验。",
    }
    with pytest.raises(ValueError, match="citation_support"):
        validate_review_decisions(AnswerReviews.model_validate(reviews), capture, cases, protocols)
