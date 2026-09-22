from copy import deepcopy
from typing import Any

import pytest
from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit

HASHES = {"doc": "a" * 64, "other": "b" * 64}


def _hit(text: str, page: int = 10, document: str = "doc") -> dict[str, Any]:
    return {
        "document_id": document,
        "pdf_page_start": page,
        "pdf_page_end": page,
        "text": text,
        "chunk_id": "irrelevant-chunk-id",
    }


def _anchor(quote: str, page: int = 10, document: str = "doc") -> dict[str, Any]:
    return {
        "document_id": document,
        "pdf_page": page,
        "file_sha256": HASHES[document],
        "quote": quote,
    }


def _case() -> dict[str, Any]:
    return {
        "id": "pilot",
        "answerability": "answerable",
        "evidence_groups": [
            {"id": "g1", "description": "任职事实", "alternatives": [_anchor("出任总理")]},
        ],
        "judgments": [],
        "human_review": {"status": "pending"},
    }


def _label(
    hit: dict[str, Any],
    relevance: int,
    *,
    groups: tuple[str, ...] = (),
    basis: str = "agent_review",
) -> dict[str, Any]:
    return {
        "unit_id": evidence_unit(hit, HASHES)["unit_id"],
        "relevance": relevance,
        "reason": "已核对原文是否支持指定问题。",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-09-22T12:00:00+00:00",
        "basis": basis,
        "supported_groups": list(groups),
    }


def test_identity_uses_pdf_hash_page_and_exact_span_but_not_chunk_id_or_whitespace() -> None:
    hit = _hit("出任 总理。\n主持会议。")
    equivalent = {**hit, "text": "出任总理。主持会议。", "chunk_id": "new-index-id"}
    unit = evidence_unit(hit, HASHES)
    assert unit["unit_id"] == evidence_unit(equivalent, HASHES)["unit_id"]
    assert unit["unit_id"] != evidence_unit(_hit("出任总理。"), HASHES)["unit_id"]
    assert unit["unit_id"] != evidence_unit(_hit(hit["text"], 11), HASHES)["unit_id"]
    assert unit["unit_id"] != evidence_unit(hit, {**HASHES, "doc": "c" * 64})["unit_id"]
    assert unit["identity"]["file_sha256"] == HASHES["doc"]
    assert "chunk_id" not in unit["identity"]
    with pytest.raises(ValueError, match="current PDF"):
        evidence_unit(hit, {})
    with pytest.raises(ValueError, match="differs"):
        evidence_unit({**hit, "file_sha256": "old-hash"}, HASHES)


def test_same_page_different_span_is_not_an_evidence_or_judgment_match() -> None:
    case = _case()
    positive = _hit("出任总理。")
    unrelated = _hit("与任职无关的天气记载。")
    case["judgments"] = [_label(positive, 2, groups=("g1",))]
    result = evaluate_stage(case, [unrelated], HASHES, (1,))
    assert result["metrics"]["required_group_recall@1"]["value"] == 0
    assert result["metrics"]["precision@1"]["value"] is None
    assert result["metrics"]["mrr@1"]["value"] is None


def test_unknown_before_known_positive_makes_mrr_unknown_not_reciprocal_rank() -> None:
    case = _case()
    hits = [_hit("未判断的史料。"), _hit("出任总理。")]
    case["judgments"] = [_label(hits[1], 2)]
    result = evaluate_stage(case, hits, HASHES, (1, 2, 3))
    assert result["metrics"]["mrr@2"]["value"] is None
    assert result["metrics"]["annotated_mrr_lower_bound@2"]["value"] == 0.5
    assert result["metrics"]["precision@3"]["value"] is None
    assert result["diagnostics"]["at_k"]["3"]["empty_slots"] == 1
    assert result["diagnostics"]["at_k"]["3"]["unknown_count"] == 1
    case["judgments"].append(_label(hits[0], 0))
    complete = evaluate_stage(case, hits, HASHES, (2,))
    assert complete["metrics"]["mrr@2"] == {
        "value": 0.5,
        "evaluable": True,
        "reason": None,
        "numerator": 1,
        "denominator": 2,
    }


def test_unknown_after_first_positive_does_not_make_mrr_unknown() -> None:
    case = _case()
    hits = [_hit("出任总理。"), _hit("未判断的背景材料。")]
    case["judgments"] = [_label(hits[0], 2)]
    result = evaluate_stage(case, hits, HASHES, (2,))
    assert result["metrics"]["mrr@2"]["value"] == 1.0
    assert result["metrics"]["precision@2"]["value"] is None


def test_alternative_anchors_are_or_and_required_groups_keep_fixed_denominator() -> None:
    case = _case()
    case["evidence_groups"][0]["alternatives"].append(_anchor("担任总理", 20, "other"))
    case["evidence_groups"].append(
        {"id": "g2", "description": "另一件事", "alternatives": [_anchor("主持会议", 11)]}
    )
    hits = [_hit("担任 总理。", 20, "other"), _hit("主持会议。", 11)]
    result = evaluate_stage(case, hits, HASHES, (1, 2))
    assert result["metrics"]["required_group_recall@1"]["value"] == 0.5
    assert result["metrics"]["required_group_recall@2"]["value"] == 1.0
    assert result["metrics"]["required_group_recall@2"]["denominator"] == 2
    assert result["metrics"]["precision@2"]["value"] is None


def test_explicit_review_can_support_a_group_without_verbatim_anchor() -> None:
    case = _case()
    hit = _hit("另一页明确陈述同一任职事实。", 12)
    case["judgments"] = [_label(hit, 2, groups=("g1",))]
    result = evaluate_stage(case, [hit], HASHES, (1,))
    assert result["metrics"]["required_group_recall@1"]["value"] == 1.0
    case["judgments"][0]["relevance"] = 0
    result = evaluate_stage(case, [hit], HASHES, (1,))
    assert result["metrics"]["required_group_recall@1"]["value"] == 0.0


def test_stale_alternative_invalidates_recall_instead_of_shrinking_denominator() -> None:
    case = _case()
    case["evidence_groups"].append(
        {"id": "g2", "description": "另一事实", "alternatives": [_anchor("主持会议", 11)]}
    )
    stale = _anchor("担任总理", 20, "other")
    stale["file_sha256"] = "outdated-pdf"
    case["evidence_groups"][0]["alternatives"].append(stale)
    result = evaluate_stage(case, [_hit("主持会议。", 11)], HASHES, (1,))
    metric = result["metrics"]["required_group_recall@1"]
    assert metric["value"] is None and metric["evaluable"] is False
    assert metric["denominator"] == 2
    assert result["diagnostics"]["invalid_groups"] == {"g1": "missing_or_stale_anchor_pdf_hash"}


def test_duplicates_do_not_repeat_recall_or_mrr_but_precision_uses_positions() -> None:
    case = _case()
    positive = _hit("出任总理。")
    negative = _hit("无关材料。", 11)
    case["judgments"] = [_label(positive, 2), _label(negative, 0)]
    result = evaluate_stage(case, [negative, positive, deepcopy(positive)], HASHES, (3, 5))
    assert result["metrics"]["required_group_recall@3"]["numerator"] == 1
    assert result["metrics"]["mrr@3"]["value"] == 0.5
    assert result["metrics"]["precision@3"]["value"] == pytest.approx(2 / 3)
    assert result["metrics"]["precision@5"]["value"] == 0.4
    assert result["metrics"]["precision@5"]["denominator"] == 5
    assert result["diagnostics"]["duplicate_rate"] == pytest.approx(1 / 3)
    assert result["diagnostics"]["unique_unit_count"] == 2


def test_fully_judged_negative_list_has_zero_mrr_and_precision() -> None:
    case = _case()
    hit = _hit("无关材料。")
    case["judgments"] = [_label(hit, 0)]
    result = evaluate_stage(case, [hit], HASHES, (3,))
    assert result["metrics"]["mrr@3"]["value"] == 0
    assert result["metrics"]["precision@3"]["value"] == 0
    assert result["diagnostics"]["at_k"]["3"]["returned_count"] == 1
    assert result["metrics"]["pool_ndcg@3"]["value"] is None


@pytest.mark.parametrize("return_candidate", [False, True])
def test_refusal_has_no_retrieval_scores_but_still_reports_candidates(
    return_candidate: bool,
) -> None:
    case = _case()
    case["category"] = "refusal"
    case["answerability"] = "unanswerable"
    case["evidence_groups"] = []
    hits = [_hit("并不能回答越界问题的材料。")] if return_candidate else []
    case["judgments"] = [_label(hit, 0) for hit in hits]
    result = evaluate_stage(case, hits, HASHES, (5,))
    for name in ("required_group_recall@5", "mrr@5", "annotated_mrr_lower_bound@5"):
        assert result["metrics"][name]["value"] is None
        assert result["metrics"][name]["reason"] == "not_applicable_no_evidence_groups"
    assert result["metrics"]["precision@5"] == {
        "value": None,
        "evaluable": False,
        "reason": "no_relevance_target",
        "numerator": None,
        "denominator": None,
    }
    assert result["diagnostics"]["returned_count"] == len(hits)
    assert result["diagnostics"]["at_k"]["5"]["returned_count"] == len(hits)


def test_human_approval_gate_and_label_basis_are_enforced() -> None:
    case = _case()
    hit = _hit("出任总理。")
    case["judgments"] = [_label(hit, 2, groups=("g1",))]
    provisional = evaluate_stage(case, [hit], HASHES, (1,))
    assert provisional["basis"] == "provisional_agent_review"
    pending = evaluate_stage(case, [hit], HASHES, (1,), label_mode="approved")
    assert pending["case_evaluable"] is False
    assert all(metric["value"] is None for metric in pending["metrics"].values())
    case["human_review"] = {
        "status": "approved",
        "reviewed_by": "human",
        "reviewed_at": "2026-09-22",
    }
    agent_only = evaluate_stage(case, [hit], HASHES, (1,), label_mode="approved")
    assert agent_only["metrics"]["precision@1"]["value"] is None
    assert agent_only["metrics"]["mrr@1"]["value"] is None
    case["judgments"][0]["basis"] = "human_review"
    approved = evaluate_stage(case, [hit], HASHES, (1,), label_mode="approved")
    assert approved["basis"] == "human_review"
    assert approved["metrics"]["precision@1"]["value"] == 1.0
    assert approved["metrics"]["mrr@1"]["value"] == 1.0


def test_conflicting_or_incomplete_judgments_are_unknown() -> None:
    case = _case()
    hit = _hit("出任总理。")
    case["judgments"] = [_label(hit, 0), _label(hit, 2)]
    result = evaluate_stage(case, [hit], HASHES, (1,))
    assert result["metrics"]["precision@1"]["value"] is None
    case["judgments"] = [_label(hit, 2)]
    case["judgments"][0]["reason"] = ""
    result = evaluate_stage(case, [hit], HASHES, (1,))
    assert result["metrics"]["precision@1"]["value"] is None
    assert result["diagnostics"]["evaluable_unit_count"] == 0
