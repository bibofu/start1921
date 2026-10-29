from __future__ import annotations

import pytest
from history_agent.evaluation.candidate_judge import (
    CandidateJudgment,
    judgment_to_record,
)
from pydantic import ValidationError


def test_abstained_judgment_cannot_carry_relevance_or_groups() -> None:
    with pytest.raises(ValidationError):
        CandidateJudgment(candidate_id="C1", relevance=2, reason="x", abstain=True)
    with pytest.raises(ValidationError):
        CandidateJudgment(
            candidate_id="C1",
            relevance=None,
            supported_groups=["g"],
            reason="x",
            abstain=True,
        )
    with pytest.raises(ValidationError):
        CandidateJudgment(candidate_id="C1", relevance=None, reason="x")


def test_irrelevant_judgment_cannot_support_groups() -> None:
    with pytest.raises(ValidationError):
        CandidateJudgment(
            candidate_id="C1", relevance=0, supported_groups=["g"], reason="x"
        )


def test_judgment_to_record_uses_llm_basis_and_skips_abstention() -> None:
    record = judgment_to_record(
        CandidateJudgment(
            candidate_id="C1",
            relevance=2,
            supported_groups=["g1"],
            reason="原文直接支持",
        ),
        unit_id="u1",
        model="test-model",
        reviewed_at="2026-10-29T00:00:00+00:00",
    )
    assert record is not None
    assert record["unit_id"] == "u1"
    assert record["basis"] == "llm_judge"
    assert record["supported_groups"] == ["g1"]
    assert record["reviewer"].startswith("llm:test-model:")

    assert (
        judgment_to_record(
            CandidateJudgment(candidate_id="C2", reason="截断无法判断", abstain=True),
            unit_id="u2",
            model="test-model",
            reviewed_at="2026-10-29T00:00:00+00:00",
        )
        is None
    )
