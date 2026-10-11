"""Score explicit answer reviews bound to an exact captured answer and case.

This module aggregates judgments; it does not invent semantic judgments or turn
Agent reviews into human approval. Unknown and not-applicable remain distinct.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIMENSIONS = (
    "citation_support",
    "source_constraint",
    "time_constraint",
    "routing",
    "safe_refusal",
    "scope_explanation",
)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")
    ).hexdigest()


def answer_fingerprint(answer: dict[str, Any]) -> str:
    return fingerprint({"answer": answer["answer"], "citations": answer["citations"]})


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FactReview(ReviewModel):
    fact_id: str = Field(min_length=1)
    status: Literal["covered", "partial", "missing", "contradicted", "unknown"]
    reason: str = Field(min_length=2)
    answer_excerpt: str | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)
    support_status: Literal["supported", "partial", "unsupported", "unknown", "not_applicable"]


class DimensionReview(ReviewModel):
    status: Literal["pass", "fail", "unknown", "not_applicable"]
    reason: str = Field(min_length=2)


class AnswerReview(ReviewModel):
    case_id: str = Field(min_length=1)
    case_definition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    basis: Literal["agent_review", "human_review"] | None = None
    reviewer: str | None = Field(default=None, min_length=1)
    reviewed_at: str | None = None
    facts: list[FactReview]
    dimensions: dict[str, DimensionReview]

    @field_validator("reviewed_at")
    @classmethod
    def require_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("review timestamp must include timezone")
        return value

    @model_validator(mode="after")
    def require_complete_dimensions(self) -> AnswerReview:
        if set(self.dimensions) != set(DIMENSIONS):
            raise ValueError("every answer dimension needs an explicit judgment or N/A reason")
        if len({item.fact_id for item in self.facts}) != len(self.facts):
            raise ValueError("duplicate fact reviews")
        identity = (self.basis, self.reviewer, self.reviewed_at)
        judged = any(f.status != "unknown" or f.support_status != "unknown" for f in self.facts)
        judged = judged or any(d.status != "unknown" for d in self.dimensions.values())
        if (judged or any(v is not None for v in identity)) and not all(identity):
            raise ValueError("explicit judgments require basis, reviewer and reviewed_at")
        return self


class AnswerReviews(ReviewModel):
    schema_version: Literal[1] = 1
    rubric_version: Literal["explicit-answer-review-v1"] = "explicit-answer-review-v1"
    capture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[AnswerReview]

    @model_validator(mode="after")
    def unique_cases(self) -> AnswerReviews:
        if len({item.case_id for item in self.cases}) != len(self.cases):
            raise ValueError("duplicate answer review cases")
        return self


def validate_reviews(
    reviews: AnswerReviews, capture: dict[str, Any], cases: list[dict[str, Any]]
) -> dict[str, AnswerReview]:
    if reviews.capture_sha256 != fingerprint(capture):
        raise ValueError("answer reviews belong to a different capture")
    by_case = {case["id"]: case for case in cases}
    captured = {case["case_id"]: case for case in capture["cases"]}
    result = {}
    for review in reviews.cases:
        if review.case_id not in by_case or review.case_id not in captured:
            raise ValueError("unknown reviewed case")
        case, raw = by_case[review.case_id], captured[review.case_id]
        definition = {
            key: value for key, value in case.items() if key not in {"judgments", "human_review"}
        }
        if review.case_definition_sha256 != fingerprint(definition):
            raise ValueError("answer review case definition changed")
        if review.case_definition_sha256 != raw["case_definition_sha256"]:
            raise ValueError("captured case definition differs")
        if review.answer_sha256 != answer_fingerprint(raw["answer"]):
            raise ValueError("reviewed answer or citations changed")
        if {f.fact_id for f in review.facts} != {f["id"] for f in case["facts"]}:
            raise ValueError("every fact requires an explicit status, including unknown")
        citation_ids = {item["evidence_id"] for item in raw["answer"]["citations"]}
        if any(not set(f.cited_evidence_ids) <= citation_ids for f in review.facts):
            raise ValueError("fact review cites evidence absent from delivered answer")
        answer_text = re.sub(r"\s+", "", raw["answer"]["answer"])
        for fact in review.facts:
            if fact.answer_excerpt and re.sub(r"\s+", "", fact.answer_excerpt) not in answer_text:
                raise ValueError("answer excerpt must be verbatim apart from whitespace")
            if fact.support_status in {"supported", "partial"} and not fact.cited_evidence_ids:
                raise ValueError("supported fact review requires delivered citation IDs")
            if (
                fact.status == "covered"
                and fact.support_status in {"unsupported", "unknown"}
                and review.dimensions["citation_support"].status == "pass"
            ):
                raise ValueError("citation pass contradicts an unsupported or unknown covered fact")
        result[review.case_id] = review
    return result


def _metric(value: float | None, reason: str | None, units: list[str]) -> dict[str, Any]:
    return {
        "value": value,
        "evaluable": value is not None,
        "reason": reason,
        "denominator": len(units),
        "unit_ids": units,
        "numerator": value * len(units) if value is not None else None,
    }


def evaluate_answer(
    case: dict[str, Any], review: AnswerReview | None, *, mode: str
) -> dict[str, Any]:
    if mode not in {"provisional", "approved"}:
        raise ValueError("unknown label mode")
    gate = None
    if review is None:
        gate = "answer_not_reviewed"
    elif mode == "approved" and (
        case["human_review"]["status"] != "approved" or review.basis != "human_review"
    ):
        gate = "human_case_and_answer_review_required"
    required = {f["id"] for f in case["facts"] if f.get("required", True)}
    units = [f"{case['id']}:{fact}" for fact in sorted(required)]
    metrics = {}
    facts = [f for f in review.facts if f.fact_id in required] if review else []
    if gate:
        metrics["required_fact_recall"] = _metric(None, gate, units)
    elif not required:
        metrics["required_fact_recall"] = _metric(None, "no_required_facts", [])
    elif any(f.status == "unknown" for f in facts):
        metrics["required_fact_recall"] = _metric(None, "unknown_fact_judgments", units)
    else:
        metrics["required_fact_recall"] = _metric(
            sum(f.status == "covered" for f in facts) / len(required), None, units
        )
    for dimension in DIMENSIONS:
        judgment = review.dimensions[dimension] if review else None
        reason = gate
        if not reason and judgment is not None and judgment.status in {"unknown", "not_applicable"}:
            reason = judgment.status
        value = float(judgment.status == "pass") if judgment and not reason else None
        metrics[dimension] = _metric(value, reason, [case["id"]])
    applicable = [
        m
        for m in metrics.values()
        if m["reason"]
        not in {
            "no_required_facts",
            "not_applicable",
        }
    ]
    known_failure = any(m["evaluable"] and m["value"] < 1 for m in applicable)
    reason = gate or (
        "unknown_applicable_judgments"
        if not known_failure and any(not m["evaluable"] for m in applicable)
        else "no_applicable_judgments"
        if not applicable
        else None
    )
    metrics["answer_pass"] = _metric(
        None if reason else float(all(m["value"] == 1 for m in applicable)), reason, [case["id"]]
    )
    return {
        "basis": review.basis if review else None,
        "mode": mode,
        "metrics": metrics,
        "fact_statuses": {f.fact_id: f.status for f in facts} if not gate else {},
        "fact_status_counts": {
            status: sum(f.status == status for f in facts)
            for status in ("covered", "partial", "missing", "contradicted", "unknown")
        }
        if not gate
        else None,
    }


def aggregate_answers(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    output = {}
    for name in ("required_fact_recall", *DIMENSIONS, "answer_pass"):
        entries = [
            (c["case_id"], c["generation_assessment"][mode]["metrics"][name]) for c in results
        ]
        valid = [(cid, m) for cid, m in entries if m["evaluable"]]
        denominator = sum(m["denominator"] for _, m in valid)
        numerator = sum(m["numerator"] for _, m in valid)
        output[name] = {
            "value": numerator / denominator if denominator else None,
            "numerator": numerator,
            "denominator": denominator,
            "aggregation": "micro_over_required_facts"
            if name == "required_fact_recall"
            else "macro_over_cases",
            "evaluable_case_ids": [cid for cid, _ in valid],
            "evaluable_unit_ids": [unit for _, m in valid for unit in m["unit_ids"]],
            "unevaluable_case_ids": [cid for cid, m in entries if not m["evaluable"]],
            "review_bases": {
                c["case_id"]: c["generation_assessment"][mode]["basis"]
                for c in results
                if c["case_id"] in {cid for cid, _ in valid}
            },
        }
    return output
