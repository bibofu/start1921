"""Prepare and validate explicit, capture-bound query-understanding reviews.

This module never judges a question automatically. Legacy observation files are
accepted as review evidence, but their saved aggregate scores are never trusted.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import HumanReview, case_definition

RUBRIC_VERSION: Literal["explicit-process-review-v1"] = "explicit-process-review-v1"
HASH_PATTERN = r"^[0-9a-f]{64}$"


class ProcessReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    case_id: str = Field(min_length=1)
    case_definition_sha256: str = Field(pattern=HASH_PATTERN)
    basis: Literal["agent_review", "human_review"] | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    criterion: str = Field(min_length=1)
    status: Literal["pass", "fail", "unknown", "not_applicable"]
    reason: str = Field(min_length=2)
    denominator: Literal[1] = 1
    value: float | None = None
    executed_query_plan: dict[str, Any] | None
    observed_query_variants: list[str]
    raw_planner_call_index: int | None = Field(default=None, ge=1)
    raw_planner_response_sha256: str | None = Field(default=None, pattern=HASH_PATTERN)
    raw_planner_plan: dict[str, Any] | None = None
    raw_to_executed_plan_changed: bool | None = None
    raw_planner_semantic_note: str | None = None
    formal: dict[str, Any] | None = None  # Legacy display only; never grants approval.

    @field_validator("criterion", "reason")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("process criterion and reason cannot be blank")
        return value

    @model_validator(mode="after")
    def explicit_decision(self) -> ProcessReview:
        if self.status in {"pass", "fail", "not_applicable"}:
            if not self.basis or not self.reviewer or not self.reviewer.strip():
                raise ValueError("process decisions require a review basis and reviewer")
            if not self.reviewed_at:
                raise ValueError("process decisions require a review timestamp")
            parsed = datetime.fromisoformat(self.reviewed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("process review timestamp must include timezone")
        if self.value is not None and (
            self.status not in {"pass", "fail"} or self.value != float(self.status == "pass")
        ):
            raise ValueError("saved process score contradicts its explicit status")
        raw = (self.raw_planner_call_index, self.raw_planner_response_sha256)
        if any(item is not None for item in raw) and not all(item is not None for item in raw):
            raise ValueError("raw planner review requires both call index and response hash")
        if self.raw_planner_plan is not None and self.raw_planner_call_index is None:
            raise ValueError("raw planner plan is not bound to a recorded response")
        return self


class ProcessReviews(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1, 2]
    rubric_version: Literal["explicit-process-review-v1"] = RUBRIC_VERSION
    dimension: Literal["query_understanding"] = "query_understanding"
    basis: str | None = None
    captured_at: str | None = None
    reviewed_at: str | None = None
    capture_sha256: str = Field(pattern=HASH_PATTERN)
    dataset_sha256: str = Field(pattern=HASH_PATTERN)
    protocol_file: str | None = None
    protocol_file_sha256: str | None = Field(default=None, pattern=HASH_PATTERN)
    scope: str | None = None
    provisional_aggregate: dict[str, Any] | None = None
    formal_aggregate: dict[str, Any] | None = None
    approved_aggregate: dict[str, Any] | None = None
    cases: list[ProcessReview]

    @model_validator(mode="after")
    def unique_cases(self) -> ProcessReviews:
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValueError("duplicate process review cases")
        if self.protocol_file is not None and self.protocol_file_sha256 is None:
            raise ValueError("declared protocol file requires a file hash")
        return self


def _captured_cases(
    cases: list[dict[str, Any]], capture: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    ids = [case["id"] for case in cases]
    captured_ids = [case["case_id"] for case in capture["cases"]]
    if len(set(ids)) != len(ids) or len(set(captured_ids)) != len(captured_ids):
        raise ValueError("duplicate dataset or capture case IDs")
    if set(ids) != set(captured_ids):
        raise ValueError("capture and dataset case IDs differ")
    result = {case["case_id"]: case for case in capture["cases"]}
    for case in cases:
        raw = result[case["id"]]
        if raw["case_definition_sha256"] != fingerprint(case_definition(case)):
            raise ValueError(f"captured case definition changed: {case['id']}")
        if "question" in raw and raw["question"] != case["question"]:
            raise ValueError(f"captured question differs: {case['id']}")
    return result


def _protocols(path: Path | None) -> tuple[str | None, dict[str, Any]]:
    if path is None:
        return None, {}
    content = path.read_bytes()
    payload = json.loads(content.decode("utf-8"))
    if not payload.get("cases"):
        raise ValueError("process protocol file must contain case rubrics")
    result = {}
    for item in payload["cases"]:
        if item["case_id"] in result:
            raise ValueError("duplicate protocol case IDs")
        result[item["case_id"]] = item
    return hashlib.sha256(content).hexdigest(), result


def _criterion(case: dict[str, Any], protocols: dict[str, Any]) -> str:
    if not protocols:
        return "核对实际执行计划与检索问题是否保留当前问题的实体、意图、时间及来源约束。"
    protocol = protocols.get(case["id"])
    if not protocol or protocol["case_definition_sha256"] != fingerprint(case_definition(case)):
        raise ValueError(f"process protocol missing or case definition changed: {case['id']}")
    rubric = protocol["stages"]["query_understanding"]
    if type(rubric["denominator"]) is not int or rubric["denominator"] != 1:
        raise ValueError("query understanding protocol must have denominator 1")
    return str(rubric["criterion"])


def _queries(raw: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            stage["query"]
            for stage in raw.get("production_stages", [])
            if isinstance(stage.get("query"), str) and stage["query"]
        )
    )


def _response(call: dict[str, Any]) -> str | None:
    choices = (call.get("response_summary") or {}).get("choices") or []
    if not choices:
        return None
    value = (choices[0].get("message") or {}).get("content")
    return value if isinstance(value, str) else None


def _parsed_plan(content: str) -> dict[str, Any] | None:
    # Parsing is for a review snapshot only; never execute or repair model output.
    try:
        result = json.loads(content)
    except ValueError:
        return None
    return result if isinstance(result, dict) else None


def _planner_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    for call in raw.get("llm_calls", []):
        content = _response(call)
        plan = _parsed_plan(content) if content is not None else None
        if (
            content is not None
            and plan is not None
            and {"intent", "normalized_question", "retrieval_route"} <= plan.keys()
        ):
            return {
                "raw_planner_call_index": call["call_index"],
                "raw_planner_response_sha256": hashlib.sha256(content.encode("utf8")).hexdigest(),
                "raw_planner_plan": plan,
                "raw_to_executed_plan_changed": plan != (raw.get("answer") or {}).get("query_plan"),
            }
    return {
        "raw_planner_call_index": None,
        "raw_planner_response_sha256": None,
        "raw_planner_plan": None,
        "raw_to_executed_plan_changed": None,
    }


def prepare_process_reviews(
    cases: list[dict[str, Any]],
    capture: dict[str, Any],
    dataset_sha256: str,
    *,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    """Create a pending packet; no facts, scores or human approvals are inferred."""
    captured = _captured_cases(cases, capture)
    protocol_hash, protocols = _protocols(protocol_path)
    rows = []
    for case in cases:
        raw = captured[case["id"]]
        rows.append(
            {
                "case_id": case["id"],
                "case_definition_sha256": raw["case_definition_sha256"],
                "basis": None,
                "reviewer": None,
                "reviewed_at": None,
                "criterion": _criterion(case, protocols),
                "status": "unknown",
                "reason": "awaiting_explicit_process_review",
                "denominator": 1,
                "executed_query_plan": deepcopy((raw.get("answer") or {}).get("query_plan")),
                "observed_query_variants": _queries(raw),
                **_planner_snapshot(raw),
            }
        )
    result = {
        "schema_version": 2,
        "rubric_version": RUBRIC_VERSION,
        "dimension": "query_understanding",
        "capture_sha256": fingerprint(capture),
        "dataset_sha256": dataset_sha256,
        "protocol_file": str(protocol_path) if protocol_path else None,
        "protocol_file_sha256": protocol_hash,
        "scope": "Effective plan and observable production queries; separate from routing.",
        "cases": rows,
    }
    ProcessReviews.model_validate(result)
    return result


def _validate_snapshot(review: ProcessReview, raw: dict[str, Any]) -> None:
    if review.executed_query_plan != (raw.get("answer") or {}).get("query_plan"):
        raise ValueError(f"reviewed executed query plan changed: {review.case_id}")
    if review.observed_query_variants != _queries(raw):
        raise ValueError(f"reviewed query variants changed: {review.case_id}")
    if review.raw_planner_call_index is None:
        return
    calls = [
        call
        for call in raw.get("llm_calls", [])
        if call.get("call_index") == review.raw_planner_call_index
    ]
    if len(calls) != 1:
        raise ValueError(f"reviewed planner call missing or ambiguous: {review.case_id}")
    content = _response(calls[0])
    if content is None or hashlib.sha256(content.encode("utf8")).hexdigest() != (
        review.raw_planner_response_sha256
    ):
        raise ValueError(f"reviewed raw planner response changed: {review.case_id}")
    if review.raw_planner_plan is not None and review.raw_planner_plan != _parsed_plan(content):
        raise ValueError(f"reviewed raw planner plan changed: {review.case_id}")
    if review.raw_to_executed_plan_changed is not None and (
        review.raw_to_executed_plan_changed
        != (review.raw_planner_plan != review.executed_query_plan)
    ):
        raise ValueError(f"raw to executed plan comparison is inconsistent: {review.case_id}")


def _metric(case: dict[str, Any], review: ProcessReview | None, *, mode: str) -> dict[str, Any]:
    reason = None
    if review is None:
        reason = "process_not_reviewed"
    elif review.status in {"unknown", "not_applicable"}:
        reason = review.status
    elif not review.executed_query_plan and not review.observed_query_variants:
        reason = "query_understanding_trace_unavailable"
    elif mode == "approved" and (
        HumanReview.model_validate(case.get("human_review", {})).status != "approved"
        or review.basis != "human_review"
    ):
        reason = "human_case_and_process_review_required"
    value = float(review.status == "pass") if review is not None and reason is None else None
    return {
        "value": value,
        "evaluable": value is not None,
        "numerator": value,
        "denominator": 1 if value is not None else 0,
        "expected_denominator": 1,
        "unit_ids": [case["id"]] if value is not None else [],
        "reason": reason,
        "review_reason": review.reason if review else None,
    }


def _aggregate(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    valid = [row for row in rows if row["query_understanding"][mode]["evaluable"]]
    unavailable = [row for row in rows if not row["query_understanding"][mode]["evaluable"]]
    numerator = sum(row["query_understanding"][mode]["value"] for row in valid)
    return {
        "value": numerator / len(valid) if valid else None,
        "evaluable": bool(valid),
        "numerator": numerator if valid else None,
        "denominator": len(valid),
        "aggregation": "macro_over_cases",
        "total_cases": len(rows),
        "evaluable_cases": len(valid),
        "evaluable_case_ids": [row["case_id"] for row in valid],
        "unevaluable_case_ids": [row["case_id"] for row in unavailable],
        "unevaluable_reasons": {
            row["case_id"]: row["query_understanding"][mode]["reason"] for row in unavailable
        },
        "reason": None if valid else "no_evaluable_process_reviews",
    }


def evaluate_process_reviews(
    payload: dict[str, Any] | None,
    cases: list[dict[str, Any]],
    capture: dict[str, Any],
    dataset_sha256: str,
    *,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    """Recompute per-case/aggregate scores only from validated explicit judgments.

    A saved protocol hash requires the caller to supply its actual file path.
    Paths inside a review are labels, never implicitly opened. Missing reviews
    produce N/A; missing bindings or mismatched snapshots are rejected.
    """
    captured = _captured_cases(cases, capture)
    reviews: dict[str, ProcessReview] = {}
    if payload is not None:
        packet = ProcessReviews.model_validate(payload)
        if packet.capture_sha256 != fingerprint(capture):
            raise ValueError("process reviews belong to a different capture")
        if packet.dataset_sha256 != dataset_sha256:
            raise ValueError("process reviews belong to a different dataset")
        protocol_hash, protocols = _protocols(protocol_path)
        if packet.protocol_file_sha256 is not None and protocol_path is None:
            raise ValueError("process reviews require the bound protocol_path for verification")
        if packet.protocol_file_sha256 != protocol_hash:
            raise ValueError("process review protocol file hash differs")
        by_case = {case["id"]: case for case in cases}
        for review in packet.cases:
            if review.case_id not in by_case:
                raise ValueError(f"unknown process reviewed case: {review.case_id}")
            case, raw = by_case[review.case_id], captured[review.case_id]
            if review.case_definition_sha256 != raw["case_definition_sha256"]:
                raise ValueError(f"process review case definition changed: {review.case_id}")
            if protocols and review.criterion != _criterion(case, protocols):
                raise ValueError(f"review criterion differs from bound protocol: {review.case_id}")
            _validate_snapshot(review, raw)
            reviews[review.case_id] = review
    rows = [
        {
            "case_id": case["id"],
            "status": reviews[case["id"]].status if case["id"] in reviews else "unknown",
            "basis": reviews[case["id"]].basis if case["id"] in reviews else None,
            "query_understanding": {
                mode: _metric(case, reviews.get(case["id"]), mode=mode)
                for mode in ("provisional", "approved")
            },
        }
        for case in cases
    ]
    return {
        "rubric_version": RUBRIC_VERSION,
        "dimension": "query_understanding",
        "cases": rows,
        "provisional_aggregate": _aggregate(rows, "provisional"),
        "approved_aggregate": _aggregate(rows, "approved"),
    }
