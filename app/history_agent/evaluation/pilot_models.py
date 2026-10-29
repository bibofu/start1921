"""Reviewable pilot annotations, kept separate from the approved Golden dataset."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HumanReview(StrictModel):
    status: Literal["pending", "approved", "rejected"] = "pending"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None
    confirmations: dict[str, bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_audit(self) -> HumanReview:
        if self.status != "pending" and not (self.reviewed_by and self.reviewed_at):
            raise ValueError("human decisions require reviewer and timestamp")
        if self.status == "approved" and not all(
            self.confirmations.get(key) is True
            for key in ("question", "evidence", "facts", "refusal")
        ):
            raise ValueError("approval requires question/evidence/facts/refusal confirmation")
        return self


class PilotAnchor(StrictModel):
    document_id: str
    pdf_page: int = Field(ge=1)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quote: str = Field(min_length=3)
    quote_normalization: Literal["remove_whitespace_only"] = "remove_whitespace_only"
    agent_verification: dict[str, Any] = Field(default_factory=dict)


class EvidenceGroup(StrictModel):
    id: str
    description: str
    alternatives: list[PilotAnchor] = Field(min_length=1)


class PilotFact(StrictModel):
    id: str
    claim: str
    required: bool = True
    evidence_group_ids: list[str] = Field(min_length=1)


class PilotJudgment(StrictModel):
    unit_id: str
    relevance: Literal[0, 1, 2]
    reason: str = Field(min_length=2)
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    basis: Literal["agent_review", "human_review", "llm_judge"]
    supported_groups: list[str] = Field(default_factory=list)


class PilotForbiddenClaim(StrictModel):
    claim: str
    reason: str


class RankingPoolIdentity(StrictModel):
    document_id: str = Field(min_length=1)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_page_start: int = Field(ge=1, strict=True)
    pdf_page_end: int = Field(ge=1, strict=True)
    normalized_text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RankingPoolUnit(RankingPoolIdentity):
    unit_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity: RankingPoolIdentity
    text: str = Field(min_length=1)


class RankingPool(StrictModel):
    """A sealed, case-specific universe for pool-relative ranking evaluation.

    Relevance labels stay in PilotCase.judgments. Keeping this model separate
    preserves historical case-definition hashes when ranking pools are added.
    """

    schema_version: Literal[1] = 1
    pool_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    selection_policy: str = Field(min_length=1)
    unit_ids: list[str] = Field(min_length=1)
    unit_identity_records: list[RankingPoolUnit] = Field(min_length=1)
    basis: Literal["agent_review", "human_review"]
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_complete_membership(self) -> RankingPool:
        record_ids = [record.unit_id for record in self.unit_identity_records]
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("ranking pool must contain unique unit IDs")
        if len(set(record_ids)) != len(record_ids) or set(self.unit_ids) != set(record_ids):
            raise ValueError("ranking pool membership must match its identity records exactly")
        return self

    def content_sha256(self) -> str:
        content = self.model_dump(exclude={"sha256"})
        content["unit_ids"] = sorted(content["unit_ids"])
        content["unit_identity_records"] = sorted(
            content["unit_identity_records"], key=lambda record: record["unit_id"]
        )
        serialized = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(("ranking-pool-v1\0" + serialized).encode("utf-8")).hexdigest()


def seal_ranking_pool(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate pool membership and seal its fixed selection and identity records."""
    pool = RankingPool.model_validate({**payload, "sha256": None})
    pool.sha256 = pool.content_sha256()
    return pool.model_dump()


class PilotCase(StrictModel):
    id: str
    question: str
    category: str
    answerability: Literal["answerable", "unanswerable"]
    split: Literal["development", "holdout"]
    topic_group: str
    human_review: HumanReview
    evidence_groups: list[EvidenceGroup] = Field(default_factory=list)
    facts: list[PilotFact] = Field(default_factory=list)
    forbidden_claims: list[PilotForbiddenClaim] = Field(default_factory=list)
    reference_answer: str | None = None
    review_notes: list[str] = Field(default_factory=list)
    judgments: list[PilotJudgment] = Field(default_factory=list)
    refusal_basis: dict[str, Any] | None = None
    not_applicable_metrics: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def references_are_consistent(self) -> PilotCase:
        groups = {group.id for group in self.evidence_groups}
        if len(groups) != len(self.evidence_groups):
            raise ValueError("duplicate evidence group IDs")
        if len({fact.id for fact in self.facts}) != len(self.facts):
            raise ValueError("duplicate fact IDs")
        if len({item.unit_id for item in self.judgments}) != len(self.judgments):
            raise ValueError("duplicate candidate judgments")
        if self.answerability == "answerable" and not (groups and self.facts):
            raise ValueError("answerable pilot cases require evidence groups and facts")
        if self.answerability == "unanswerable" and (groups or self.facts):
            raise ValueError("unanswerable cases cannot claim positive evidence")
        for fact in self.facts:
            if not set(fact.evidence_group_ids) <= groups:
                raise ValueError("fact refers to an unknown evidence group")
        for item in self.judgments:
            if not set(item.supported_groups) <= groups:
                raise ValueError("judgment refers to an unknown evidence group")
            if item.relevance == 0 and item.supported_groups:
                raise ValueError("irrelevant evidence cannot support required groups")
        return self


class PilotDataset(StrictModel):
    schema_version: Literal[1]
    version: str
    description: str
    annotation_status: str = "agent_verified_human_pending"
    evidence_group_semantics: dict[str, str] = Field(default_factory=dict)
    cases: list[PilotCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> PilotDataset:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate pilot case IDs")
        return self


def case_definition(case: dict[str, Any]) -> dict[str, Any]:
    """Separate immutable questions/evidence from subsequently supplied reviews."""
    return {key: value for key, value in case.items() if key not in {"judgments", "human_review"}}
