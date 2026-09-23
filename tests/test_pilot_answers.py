from copy import deepcopy
from typing import Any

import pytest
from history_agent.evaluation.pilot_answers import (
    DIMENSIONS,
    AnswerReview,
    AnswerReviews,
    aggregate_answers,
    answer_fingerprint,
    evaluate_answer,
    fingerprint,
    validate_reviews,
)
from pydantic import ValidationError


def _case(case_id: str = "case-a") -> dict[str, Any]:
    return {
        "id": case_id,
        "question": "当时分别担任何职？",
        "facts": [
            {"id": "f1", "claim": "出任总理。", "required": True},
            {"id": "f2", "claim": "主持会议。", "required": True},
            {"id": "f3", "claim": "参加工作。", "required": True},
            {"id": "context", "claim": "相关背景。", "required": False},
        ],
        "judgments": [],
        "human_review": {"status": "pending"},
    }


def _definition(case: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in case.items() if key not in {"judgments", "human_review"}}


def _answer() -> dict[str, Any]:
    return {
        "answer": "他出任总理。[E1] 随后主持会议，参加工作。",
        "citations": [
            {
                "evidence_id": "E1",
                "document_id": "doc-1",
                "pdf_page": 10,
                "quote": "任职后主持了会议。",
            }
        ],
    }


def _review_payload(case: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "case_definition_sha256": fingerprint(_definition(case)),
        "answer_sha256": answer_fingerprint(answer),
        "basis": "agent_review",
        "reviewer": "test-agent",
        "reviewed_at": "2026-09-23T12:00:00+08:00",
        "facts": [
            {
                "fact_id": fact["id"],
                "status": "covered",
                "reason": "逐项与回答及证据核对。",
                "answer_excerpt": "他出任总理。" if fact["id"] == "f1" else None,
                "cited_evidence_ids": ["E1"],
                "support_status": "supported",
            }
            for fact in case["facts"]
        ],
        "dimensions": {
            dimension: {"status": "pass", "reason": "按该维度的评分口径核对。"}
            for dimension in DIMENSIONS
        },
    }


def _bundle() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case = _case()
    answer = _answer()
    capture = {
        "run_name": "fixed-answer-baseline",
        "cases": [
            {
                "case_id": case["id"],
                "case_definition_sha256": fingerprint(_definition(case)),
                "answer": answer,
            }
        ],
    }
    review = {
        "capture_sha256": fingerprint(capture),
        "cases": [_review_payload(case, answer)],
    }
    return case, capture, review


def _evaluate(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return evaluate_answer(case, AnswerReview.model_validate(payload), mode="provisional")


def test_answer_reviews_bind_exact_capture_but_case_labels_can_be_reviewed_later() -> None:
    case, capture, payload = _bundle()
    case["judgments"] = [{"unit_id": "newly-graded-candidate", "relevance": 2}]
    case["human_review"] = {"status": "approved", "reviewed_by": "human"}
    validated = validate_reviews(AnswerReviews.model_validate(payload), capture, [case])
    assert list(validated) == [case["id"]]
    capture["run_name"] = "another-run-even-if-answer-is-the-same"
    with pytest.raises(ValueError, match="different capture"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("change", ["case_definition", "captured_definition", "unknown_case"])
def test_review_cannot_rebind_to_a_changed_or_unknown_question(change: str) -> None:
    case, capture, payload = _bundle()
    if change == "case_definition":
        case["question"] = "更改题意后的问题？"
        expected = "case definition changed"
    elif change == "captured_definition":
        capture["cases"][0]["case_definition_sha256"] = "a" * 64
        payload["capture_sha256"] = fingerprint(capture)
        expected = "captured case definition differs"
    else:
        payload["cases"][0]["case_id"] = "unknown-question"
        expected = "unknown reviewed case"
    with pytest.raises(ValueError, match=expected):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("change", ["answer", "citation_quote", "citation_document", "citation_id"])
def test_answer_binding_includes_answer_text_and_full_delivered_citations(change: str) -> None:
    case, capture, payload = _bundle()
    captured_answer = capture["cases"][0]["answer"]
    if change == "answer":
        captured_answer["answer"] += "额外且未复核的结论。"
    else:
        field = {
            "citation_quote": "quote",
            "citation_document": "document_id",
            "citation_id": "evidence_id",
        }[change]
        captured_answer["citations"][0][field] = "changed-value"
    payload["capture_sha256"] = fingerprint(capture)
    with pytest.raises(ValueError, match="answer or citations changed"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_every_declared_fact_including_optional_facts_requires_exactly_one_review(
    change: str,
) -> None:
    case, capture, payload = _bundle()
    facts = payload["cases"][0]["facts"]
    if change == "missing":
        facts.pop()
    elif change == "extra":
        facts.append({**facts[0], "fact_id": "invented-fact"})
    else:
        facts.append(deepcopy(facts[0]))
    expected = "duplicate fact reviews" if change == "duplicate" else "every fact requires"
    with pytest.raises(ValueError, match=expected):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


def test_fact_review_cannot_cite_an_id_absent_from_the_delivered_answer() -> None:
    case, capture, payload = _bundle()
    capture["cases"][0]["retrieved_but_not_cited"] = [{"evidence_id": "E99"}]
    payload["capture_sha256"] = fingerprint(capture)
    payload["cases"][0]["facts"][0]["cited_evidence_ids"] = ["E99"]
    with pytest.raises(ValueError, match="evidence absent from delivered answer"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("excerpt", ["他出任副总理。", "他出任总理。随后主持会议。"])
def test_review_excerpts_cannot_invent_or_merge_text_missing_from_captured_answer(
    excerpt: str,
) -> None:
    case, capture, payload = _bundle()
    payload["cases"][0]["facts"][0]["answer_excerpt"] = excerpt
    with pytest.raises(ValueError, match="excerpt must be verbatim"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


def test_excerpt_matching_ignores_only_whitespace_and_allows_explicit_no_excerpt() -> None:
    case, capture, payload = _bundle()
    payload["cases"][0]["facts"][0]["answer_excerpt"] = "他 出任\n 总理。"
    validated = validate_reviews(AnswerReviews.model_validate(payload), capture, [case])
    assert validated[case["id"]].facts[0].answer_excerpt == "他 出任\n 总理。"
    payload["cases"][0]["facts"][0]["answer_excerpt"] = None
    assert validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("support_status", ["supported", "partial"])
def test_claimed_evidence_support_requires_at_least_one_delivered_citation(
    support_status: str,
) -> None:
    case, capture, payload = _bundle()
    fact = payload["cases"][0]["facts"][0]
    fact["support_status"] = support_status
    fact["cited_evidence_ids"] = []
    with pytest.raises(ValueError, match="requires delivered citation IDs"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])


@pytest.mark.parametrize("support_status", ["unsupported", "unknown"])
def test_citation_pass_cannot_contradict_fact_level_evidence_support(support_status: str) -> None:
    case, capture, payload = _bundle()
    payload["cases"][0]["facts"][0]["support_status"] = support_status
    with pytest.raises(ValueError, match="citation pass contradicts"):
        validate_reviews(AnswerReviews.model_validate(payload), capture, [case])
    payload["cases"][0]["dimensions"]["citation_support"]["status"] = "fail"
    validated = validate_reviews(AnswerReviews.model_validate(payload), capture, [case])
    result = evaluate_answer(case, validated[case["id"]], mode="provisional")
    assert result["metrics"]["required_fact_recall"]["value"] == 1
    assert result["metrics"]["citation_support"]["value"] == 0
    assert result["metrics"]["answer_pass"]["value"] == 0


def test_missing_fact_may_have_no_quote_or_citation_and_explicit_support_not_applicable() -> None:
    case, capture, payload = _bundle()
    fact = payload["cases"][0]["facts"][0]
    fact.update(
        status="missing",
        support_status="not_applicable",
        cited_evidence_ids=[],
        answer_excerpt=None,
    )
    validated = validate_reviews(AnswerReviews.model_validate(payload), capture, [case])
    result = evaluate_answer(case, validated[case["id"]], mode="provisional")
    assert result["metrics"]["required_fact_recall"]["value"] == pytest.approx(2 / 3)
    assert result["metrics"]["citation_support"]["value"] == 1
    assert result["metrics"]["answer_pass"]["value"] == 0


@pytest.mark.parametrize("change", ["dimension", "timestamp", "duplicate_case"])
def test_review_requires_complete_explicit_dimensions_and_auditable_metadata(change: str) -> None:
    _, _, payload = _bundle()
    if change == "dimension":
        del payload["cases"][0]["dimensions"]["routing"]
        expected = "every answer dimension"
    elif change == "timestamp":
        payload["cases"][0]["reviewed_at"] = "2026-09-23T12:00:00"
        expected = "timestamp must include timezone"
    else:
        payload["cases"].append(deepcopy(payload["cases"][0]))
        expected = "duplicate answer review cases"
    with pytest.raises(ValidationError, match=expected):
        AnswerReviews.model_validate(payload)


def test_partial_and_missing_required_facts_are_zero_credit_optional_unknown_is_excluded() -> None:
    case = _case()
    payload = _review_payload(case, _answer())
    for fact, status in zip(
        payload["facts"], ["covered", "partial", "missing", "unknown"], strict=True
    ):
        fact["status"] = status
    result = _evaluate(case, payload)
    metric = result["metrics"]["required_fact_recall"]
    assert metric["value"] == pytest.approx(1 / 3)
    assert metric["numerator"] == 1
    assert metric["denominator"] == 3
    assert metric["unit_ids"] == ["case-a:f1", "case-a:f2", "case-a:f3"]
    assert result["fact_status_counts"] == {
        "covered": 1,
        "partial": 1,
        "missing": 1,
        "contradicted": 0,
        "unknown": 0,
    }
    assert result["metrics"]["answer_pass"]["value"] == 0


def test_unknown_required_fact_does_not_become_zero_or_shrink_denominator() -> None:
    case = _case()
    payload = _review_payload(case, _answer())
    payload["facts"][0]["status"] = "unknown"
    result = _evaluate(case, payload)
    metric = result["metrics"]["required_fact_recall"]
    assert metric["value"] is None
    assert metric["numerator"] is None
    assert metric["denominator"] == 3
    assert metric["reason"] == "unknown_fact_judgments"
    assert result["metrics"]["answer_pass"]["reason"] == "unknown_applicable_judgments"
    assert result["metrics"]["citation_support"]["value"] == 1


def test_known_contradicted_or_missing_facts_are_evaluable_zero() -> None:
    case = _case()
    payload = _review_payload(case, _answer())
    for fact in payload["facts"]:
        fact["status"] = "contradicted" if fact["fact_id"] == "f1" else "missing"
    result = _evaluate(case, payload)
    assert result["metrics"]["required_fact_recall"]["value"] == 0
    assert result["metrics"]["required_fact_recall"]["evaluable"] is True
    assert result["metrics"]["required_fact_recall"]["denominator"] == 3


def test_not_applicable_dimensions_do_not_fail_answer_but_unknown_dimensions_block_pass() -> None:
    case = _case()
    payload = _review_payload(case, _answer())
    payload["dimensions"]["safe_refusal"]["status"] = "not_applicable"
    result = _evaluate(case, payload)
    assert result["metrics"]["safe_refusal"]["value"] is None
    assert result["metrics"]["safe_refusal"]["reason"] == "not_applicable"
    assert result["metrics"]["answer_pass"]["value"] == 1
    payload["dimensions"]["time_constraint"]["status"] = "unknown"
    result = _evaluate(case, payload)
    assert result["metrics"]["time_constraint"]["value"] is None
    assert result["metrics"]["answer_pass"]["value"] is None
    assert result["metrics"]["answer_pass"]["reason"] == "unknown_applicable_judgments"


@pytest.mark.parametrize("known_failure", ["fact", "dimension"])
def test_known_failure_keeps_answer_failed_without_turning_other_unknowns_into_zero(
    known_failure: str,
) -> None:
    case = _case()
    payload = _review_payload(case, _answer())
    payload["dimensions"]["time_constraint"]["status"] = "unknown"
    if known_failure == "fact":
        payload["facts"][0]["status"] = "partial"
    else:
        payload["facts"][0]["status"] = "unknown"
        payload["dimensions"]["source_constraint"]["status"] = "fail"
    result = _evaluate(case, payload)
    assert result["metrics"]["answer_pass"]["value"] == 0
    assert result["metrics"]["answer_pass"]["evaluable"] is True
    assert result["metrics"]["time_constraint"]["value"] is None
    if known_failure == "dimension":
        assert result["metrics"]["required_fact_recall"]["value"] is None


def test_refusal_with_no_required_facts_uses_only_applicable_dimensions() -> None:
    case = _case()
    case["facts"] = []
    payload = _review_payload(case, _answer())
    for dimension in payload["dimensions"].values():
        dimension["status"] = "not_applicable"
    result = _evaluate(case, payload)
    assert result["metrics"]["required_fact_recall"]["reason"] == "no_required_facts"
    assert result["metrics"]["required_fact_recall"]["denominator"] == 0
    assert result["metrics"]["answer_pass"]["reason"] == "no_applicable_judgments"
    payload["dimensions"]["safe_refusal"]["status"] = "pass"
    payload["dimensions"]["scope_explanation"]["status"] = "fail"
    result = _evaluate(case, payload)
    assert result["metrics"]["answer_pass"]["value"] == 0


@pytest.mark.parametrize(
    "approved_case,human_answer", [(False, False), (True, False), (False, True)]
)
def test_approved_scores_require_both_case_and_answer_human_review(
    approved_case: bool,
    human_answer: bool,
) -> None:
    case = _case()
    case["human_review"]["status"] = "approved" if approved_case else "pending"
    payload = _review_payload(case, _answer())
    payload["basis"] = "human_review" if human_answer else "agent_review"
    result = evaluate_answer(case, AnswerReview.model_validate(payload), mode="approved")
    assert all(metric["value"] is None for metric in result["metrics"].values())
    assert all(
        metric["reason"] == "human_case_and_answer_review_required"
        for metric in result["metrics"].values()
    )
    assert result["fact_status_counts"] is None


def test_human_approved_answer_and_case_can_score_and_absent_review_stays_unknown() -> None:
    case = _case()
    case["human_review"]["status"] = "approved"
    payload = _review_payload(case, _answer())
    payload["basis"] = "human_review"
    result = evaluate_answer(case, AnswerReview.model_validate(payload), mode="approved")
    assert result["metrics"]["answer_pass"]["value"] == 1
    missing = evaluate_answer(case, None, mode="provisional")
    assert all(metric["value"] is None for metric in missing["metrics"].values())
    assert all(metric["reason"] == "answer_not_reviewed" for metric in missing["metrics"].values())
    assert missing["metrics"]["required_fact_recall"]["denominator"] == 3
    with pytest.raises(ValueError, match="unknown label mode"):
        evaluate_answer(case, None, mode="some-other-mode")


def test_aggregate_micro_weights_required_facts_and_macro_weights_case_dimensions() -> None:
    results = []
    for case_id in ("a", "b", "unknown", "na"):
        case = _case(case_id)
        if case_id == "b":
            case["facts"] = case["facts"][:1]
        elif case_id == "na":
            case["facts"] = []
        payload = _review_payload(case, _answer())
        if case_id == "a":
            payload["facts"][1]["status"] = "partial"
            payload["facts"][2]["status"] = "missing"
        elif case_id == "b":
            payload["dimensions"]["citation_support"]["status"] = "fail"
        elif case_id == "unknown":
            payload["facts"][0]["status"] = "unknown"
            payload["dimensions"]["citation_support"]["status"] = "unknown"
        else:
            payload["dimensions"]["citation_support"]["status"] = "not_applicable"
        results.append(
            {
                "case_id": case_id,
                "generation_assessment": {"provisional": _evaluate(case, payload)},
            }
        )
    result = aggregate_answers(results, "provisional")
    facts = result["required_fact_recall"]
    assert facts["value"] == 0.5
    assert facts["numerator"] == 2 and facts["denominator"] == 4
    assert facts["aggregation"] == "micro_over_required_facts"
    assert facts["evaluable_case_ids"] == ["a", "b"]
    assert facts["evaluable_unit_ids"] == ["a:f1", "a:f2", "a:f3", "b:f1"]
    assert facts["unevaluable_case_ids"] == ["unknown", "na"]
    citations = result["citation_support"]
    assert citations["value"] == 0.5
    assert citations["numerator"] == 1 and citations["denominator"] == 2
    assert citations["aggregation"] == "macro_over_cases"
    assert citations["evaluable_case_ids"] == ["a", "b"]
    assert citations["unevaluable_case_ids"] == ["unknown", "na"]


def test_aggregate_without_evaluable_units_stays_na_instead_of_zero() -> None:
    case = _case()
    assessment = evaluate_answer(case, None, mode="provisional")
    result = aggregate_answers(
        [
            {"case_id": case["id"], "generation_assessment": {"provisional": assessment}},
        ],
        "provisional",
    )
    assert all(metric["value"] is None for metric in result.values())
    assert all(metric["denominator"] == 0 for metric in result.values())
    assert all(metric["evaluable_unit_ids"] == [] for metric in result.values())
    assert all(metric["unevaluable_case_ids"] == [case["id"]] for metric in result.values())
