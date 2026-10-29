"""Strict span-based metrics for a small, explicitly reviewed evaluation pilot.

These metrics describe the supplied annotations, not exhaustive corpus relevance.
Whitespace is ignored for evidence identity and exact quote matching; characters,
case, punctuation, and Unicode normalization are otherwise left unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from pydantic import ValidationError

from history_agent.evaluation.pilot_models import RankingPool


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def evidence_unit(hit: dict[str, Any], file_hashes: dict[str, str]) -> dict[str, Any]:
    """Identify a concrete returned span without depending on a chunk ID."""
    document_id = str(hit.get("document_id", "")).strip()
    file_hash = file_hashes.get(document_id)
    if not document_id or not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError("Evidence identity requires document_id and its current PDF file hash")
    if hit.get("file_sha256") and hit["file_sha256"] != file_hash:
        raise ValueError(f"Hit PDF hash differs from the current PDF: {document_id}")
    start = hit.get("pdf_page_start", hit.get("pdf_page"))
    end = hit.get("pdf_page_end", start)
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 1
        or end < start
    ):
        raise ValueError("Evidence identity requires a valid physical PDF page range")
    text = hit.get("text", hit.get("quote", hit.get("snippet", "")))
    if not isinstance(text, str) or not _normalized_text(text):
        raise ValueError("Evidence identity requires nonempty returned text")
    normalized = _normalized_text(text)
    identity = {
        "document_id": document_id,
        "file_sha256": file_hash,
        "pdf_page_start": start,
        "pdf_page_end": end,
        "normalized_text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }
    serialized = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    unit_id = hashlib.sha256(("evidence-unit-v1\0" + serialized).encode("utf-8")).hexdigest()
    return {"unit_id": unit_id, **identity, "identity": identity, "text": text}


def _metric(
    value: float | None,
    reason: str | None,
    numerator: int | float | None = None,
    denominator: int | float | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "evaluable": value is not None,
        "reason": reason,
        "numerator": numerator,
        "denominator": denominator,
    }


def _judgments(
    case: dict[str, Any], label_mode: str
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    invalid: dict[str, str] = {}
    for judgment in case.get("judgments", []):
        unit_id = judgment.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id:
            continue
        allowed = (
            {"human_review"}
            if label_mode == "approved"
            else {"human_review", "agent_review", "llm_judge"}
        )
        relevance = judgment.get("relevance")
        if judgment.get("basis") not in allowed:
            invalid[unit_id] = "judgment_basis_not_allowed"
        elif type(relevance) is not int or relevance not in {0, 1, 2}:
            invalid[unit_id] = "invalid_relevance_grade"
        elif not all(
            isinstance(judgment.get(field), str) and judgment[field].strip()
            for field in ("reason", "reviewer", "reviewed_at")
        ):
            invalid[unit_id] = "judgment_review_metadata_missing"
        elif not isinstance(judgment.get("supported_groups", []), list) or not all(
            isinstance(group, str) for group in judgment.get("supported_groups", [])
        ):
            invalid[unit_id] = "invalid_supported_groups"
        else:
            candidates.setdefault(unit_id, []).append(judgment)
    valid: dict[str, dict[str, Any]] = {}
    for unit_id, labels in candidates.items():
        human = [label for label in labels if label["basis"] == "human_review"]
        selected = human or labels
        meanings = {
            (label["relevance"], tuple(sorted(set(label.get("supported_groups", [])))))
            for label in selected
        }
        if len(meanings) == 1:
            valid[unit_id] = selected[0]
            invalid.pop(unit_id, None)
        else:
            invalid[unit_id] = "conflicting_judgments"
    return valid, invalid


def _invalid_groups(groups: list[dict[str, Any]], file_hashes: dict[str, str]) -> dict[str, str]:
    invalid: dict[str, str] = {}
    seen: set[str] = set()
    for group in groups:
        group_id = str(group.get("id", ""))
        if not group_id or group_id in seen:
            invalid[group_id] = "missing_or_duplicate_group_id"
        seen.add(group_id)
        alternatives = group.get("alternatives", [])
        if not alternatives:
            invalid[group_id] = "no_evidence_anchors"
        for anchor in alternatives:
            current_hash = file_hashes.get(anchor.get("document_id", ""))
            if not current_hash or anchor.get("file_sha256") != current_hash:
                invalid[group_id] = "missing_or_stale_anchor_pdf_hash"
                break
            quote = anchor.get("quote")
            page = anchor.get("pdf_page")
            if (
                not isinstance(quote, str)
                or not _normalized_text(quote)
                or not isinstance(page, int)
                or isinstance(page, bool)
                or page < 1
            ):
                invalid[group_id] = "invalid_quote_or_physical_page_anchor"
    return invalid


def _matched_groups(
    unit: dict[str, Any],
    groups: list[dict[str, Any]],
    judgment: dict[str, Any] | None,
    invalid_groups: dict[str, str],
) -> set[str]:
    matched: set[str] = set()
    normalized = _normalized_text(unit["text"])
    supported = set(judgment.get("supported_groups", [])) if judgment else set()
    for group in groups:
        group_id = group["id"]
        if group_id in invalid_groups:
            continue
        if judgment and judgment["relevance"] > 0 and group_id in supported:
            matched.add(group_id)
            continue
        for anchor in group["alternatives"]:
            if (
                anchor["document_id"] == unit["document_id"]
                and anchor["file_sha256"] == unit["file_sha256"]
                and unit["pdf_page_start"] <= anchor["pdf_page"] <= unit["pdf_page_end"]
                and _normalized_text(anchor["quote"]) in normalized
            ):
                matched.add(group_id)
                break
    return matched


_POOL_NDCG_CONVENTION = {
    "gain": "2**relevance-1",
    "discount": "log2(rank+1)",
    "ideal_order": "all_unique_pool_units_by_descending_relevance",
    "duplicates": "first_occurrence_only_later_positions_have_zero_gain",
    "empty_slots": "zero_gain_without_reducing_ideal_denominator",
    "relevance_grades": [0, 1, 2],
    "scope": "fixed_judged_pool_not_exhaustive_corpus_relevance",
}


def _prepare_ranking_pool(
    case: dict[str, Any],
    payload: dict[str, Any] | None,
    file_hashes: dict[str, str],
    judgments: dict[str, dict[str, Any]],
    label_mode: str,
) -> tuple[dict[str, Any], set[str], list[int]]:
    details: dict[str, Any] = {
        "pool_id": None,
        "pool_sha256": None,
        "pool_fingerprint": None,
        "pool_unit_count": None,
        "selection_policy": None,
        "convention": _POOL_NDCG_CONVENTION,
        "reason": None,
    }
    if payload is None:
        details["reason"] = "fixed_fully_judged_candidate_pool_required"
        return details, set(), []
    try:
        pool = RankingPool.model_validate(payload)
    except ValidationError as exc:
        details["reason"] = "invalid_candidate_pool"
        details["validation_errors"] = [
            {"location": list(error["loc"]), "type": error["type"]} for error in exc.errors()
        ]
        return details, set(), []
    details.update(
        pool_id=pool.pool_id,
        pool_sha256=pool.sha256,
        pool_unit_count=len(pool.unit_ids),
        selection_policy=pool.selection_policy,
        basis=pool.basis,
    )
    members = set(pool.unit_ids)
    if pool.case_id != case.get("id", case.get("case_id")):
        details["reason"] = "pool_case_mismatch"
    elif pool.sha256 != pool.content_sha256():
        details["reason"] = "pool_sha256_mismatch"
    elif label_mode == "approved" and pool.basis != "human_review":
        details["reason"] = "pool_human_review_required"
    else:
        invalid: dict[str, str] = {}
        for record in pool.unit_identity_records:
            try:
                current = evidence_unit(record.model_dump(), file_hashes)
            except ValueError:
                invalid[record.unit_id] = "missing_or_stale_pool_pdf_hash"
                continue
            if (
                current["unit_id"] != record.unit_id
                or current["identity"] != record.identity.model_dump()
                or current["normalized_text_sha256"] != record.normalized_text_sha256
            ):
                invalid[record.unit_id] = "pool_unit_identity_mismatch"
        if invalid:
            details["reason"] = "invalid_pool_unit_identities"
            details["invalid_units"] = invalid
        else:
            unjudged = sorted(members - judgments.keys())
            if unjudged:
                details["reason"] = "pool_contains_unjudged_units"
                details["unjudged_unit_ids"] = unjudged
    if details["reason"]:
        return details, members, []
    grades = {unit_id: judgments[unit_id]["relevance"] for unit_id in sorted(members)}
    fingerprint = json.dumps(
        {"pool_sha256": pool.sha256, "grades": grades, "convention": _POOL_NDCG_CONVENTION},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    details["pool_fingerprint"] = hashlib.sha256(
        ("pool-ndcg-v1\0" + fingerprint).encode("utf-8")
    ).hexdigest()
    return details, members, sorted(grades.values(), reverse=True)


def _pool_ndcg(
    top: list[dict[str, Any]],
    k: int,
    details: dict[str, Any],
    members: set[str],
    ideal_grades: list[int],
    *,
    gate: bool,
    answerable: bool,
) -> dict[str, Any]:
    outside = sorted({unit["unit_id"] for unit in top} - members)
    reason = (
        "case_human_review_not_approved"
        if gate
        else "no_relevance_target"
        if not answerable
        else details["reason"] or ("returned_units_outside_candidate_pool" if outside else None)
    )
    dcg = idcg = None
    value = None
    if not reason:
        idcg = sum(
            (2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades[:k], 1)
        )
        dcg = sum(
            (2 ** unit["relevance"] - 1) / math.log2(unit["rank"] + 1)
            for unit in top
            if not unit["duplicate"]
        )
        if not idcg:
            reason = "pool_has_no_positive_relevance"
        else:
            value = dcg / idcg
    return {
        **_metric(value, reason, dcg, idcg),
        "dcg": dcg,
        "idcg": idcg,
        "pool_id": details["pool_id"],
        "pool_sha256": details["pool_sha256"],
        "pool_fingerprint": details["pool_fingerprint"],
        "pool_unit_count": details["pool_unit_count"],
        "outside_pool_unit_ids": outside if members else [],
        "convention": _POOL_NDCG_CONVENTION,
    }


def evaluate_stage(
    case: dict[str, Any],
    hits: list[dict[str, Any]],
    file_hashes: dict[str, str],
    k_values: tuple[int, ...] = (1, 3, 5, 10, 20),
    *,
    label_mode: str = "provisional",
    ranking_pool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a returned ordered list with explicit missing-label denominators.

    Precision uses standard returned-position relevance, including repeated
    relevant positions. Duplicate rates are separate diagnostics. Missing slots
    after retrieval exhaustion count as zero; unknown returned units never do.
    MRR is exact only when no earlier unknown unit can change the first positive.
    Pool nDCG uses a separately sealed, completely graded candidate universe;
    candidates outside that universe make its applicable K values unevaluable.
    """
    if label_mode not in {"provisional", "approved"}:
        raise ValueError("label_mode must be provisional or approved")
    if not k_values or any(type(k) is not int or k < 1 for k in k_values):
        raise ValueError("k_values must contain positive integers")
    groups = case.get("evidence_groups", [])
    valid, invalid_labels = _judgments(case, label_mode)
    pool_details, pool_members, ideal_grades = _prepare_ranking_pool(
        case, ranking_pool, file_hashes, valid, label_mode
    )
    invalid_groups = _invalid_groups(groups, file_hashes)
    gate = label_mode == "approved" and case.get("human_review", {}).get("status") != "approved"
    basis = "provisional_agent_review" if label_mode == "provisional" else "human_review"
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, hit in enumerate(hits, 1):
        unit = evidence_unit(hit, file_hashes)
        label = valid.get(unit["unit_id"]) if not gate else None
        unit.update(
            rank=rank,
            duplicate=unit["unit_id"] in seen,
            relevance=label["relevance"] if label else None,
            judgment_evaluable=label is not None,
            judgment_reason=None if label else invalid_labels.get(unit["unit_id"], "unjudged_unit"),
            matched_groups=sorted(_matched_groups(unit, groups, label, invalid_groups))
            if not gate
            else [],
        )
        seen.add(unit["unit_id"])
        units.append(unit)
    metrics: dict[str, dict[str, Any]] = {}
    at_k: dict[str, Any] = {}
    for k in dict.fromkeys(k_values):
        top = units[:k]
        unknown = [unit for unit in top if not unit["judgment_evaluable"]]
        matches = {group for unit in top for group in unit["matched_groups"]}
        first_positive = next((unit["rank"] for unit in top if (unit["relevance"] or 0) > 0), None)
        at_k[str(k)] = {
            "returned_count": len(top),
            "empty_slots": max(0, k - len(top)),
            "unique_unit_count": len({unit["unit_id"] for unit in top}),
            "duplicate_count": sum(unit["duplicate"] for unit in top),
            "duplicate_rate": sum(unit["duplicate"] for unit in top) / len(top) if top else 0.0,
            "unknown_count": len(unknown),
            "unknown_unit_count": len({unit["unit_id"] for unit in unknown}),
            "evaluable_unit_count": len(top) - len(unknown),
            "matched_groups": sorted(matches),
            "evidence_group_count": len(groups),
            "evaluable_group_count": len(groups) - len(invalid_groups),
        }
        metrics[f"pool_ndcg@{k}"] = _pool_ndcg(
            top,
            k,
            pool_details,
            pool_members,
            ideal_grades,
            gate=gate,
            answerable=case.get("answerability") == "answerable",
        )
        if gate:
            for name in (
                "required_group_recall",
                "precision",
                "mrr",
                "annotated_mrr_lower_bound",
            ):
                metrics[f"{name}@{k}"] = _metric(None, "case_human_review_not_approved")
            continue
        recall_reason = (
            "not_applicable_no_evidence_groups"
            if not groups
            else "invalid_evidence_groups"
            if invalid_groups
            else None
        )
        metrics[f"required_group_recall@{k}"] = (
            _metric(None, recall_reason, denominator=len(groups) or None)
            if recall_reason
            else _metric(len(matches) / len(groups), None, len(matches), len(groups))
        )
        positive_count = sum((unit["relevance"] or 0) > 0 for unit in top)
        if case.get("answerability") != "answerable":
            metrics[f"precision@{k}"] = _metric(None, "no_relevance_target")
        else:
            metrics[f"precision@{k}"] = (
                _metric(None, "unjudged_returned_units", denominator=k)
                if unknown
                else _metric(positive_count / k, None, positive_count, k)
            )
        if not groups:
            mrr = lower_bound = _metric(None, "not_applicable_no_evidence_groups")
        else:
            lower_bound = _metric(
                1.0 / first_positive if first_positive else 0.0,
                "annotated_lower_bound_not_exact_mrr",
                1 if first_positive else 0,
                first_positive or 1,
            )
            if first_positive and not any(unit["rank"] < first_positive for unit in unknown):
                mrr = _metric(1.0 / first_positive, None, 1, first_positive)
            elif not first_positive and not unknown:
                mrr = _metric(0.0, None, 0, 1)
            else:
                mrr = _metric(None, "unknown_units_can_change_first_positive_rank")
        metrics[f"mrr@{k}"] = mrr
        metrics[f"annotated_mrr_lower_bound@{k}"] = lower_bound
    duplicate_count = sum(unit["duplicate"] for unit in units)
    return {
        "case_id": case.get("id", case.get("case_id")),
        "label_mode": label_mode,
        "basis": "unapproved" if gate else basis,
        "case_evaluable": not gate,
        "case_reason": "case_human_review_not_approved" if gate else None,
        "metrics": metrics,
        "diagnostics": {
            "returned_count": len(units),
            "unique_unit_count": len(seen),
            "duplicate_count": duplicate_count,
            "duplicate_rate": duplicate_count / len(units) if units else 0.0,
            "unknown_judgment_count": sum(not unit["judgment_evaluable"] for unit in units),
            "evaluable_unit_count": sum(unit["judgment_evaluable"] for unit in units),
            "evidence_group_count": len(groups),
            "invalid_groups": invalid_groups,
            "invalid_judgments": invalid_labels,
            "ranking_pool": pool_details,
            "at_k": at_k,
        },
        "units": units,
    }
