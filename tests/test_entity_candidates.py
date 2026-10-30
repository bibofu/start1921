from __future__ import annotations

from pathlib import Path

from history_agent.answering.entity_candidates import CandidateSet, ProposedCandidate, _validate
from history_agent.answering.entity_linking import load_entities

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "config/entities/entities.jsonl"


def test_empty_placeholder_candidates_are_ignored() -> None:
    records = load_entities(INDEX)
    query = "刘伯成和邓小平在1947年共同指挥了哪些战役？"
    parsed = CandidateSet(
        candidates=[
            ProposedCandidate(
                mention_text="刘伯成",
                entity_id="person:liu_bocheng",
                canonical="刘伯承",
                confidence=0.9,
            ),
            ProposedCandidate(
                mention_text="在1947年共同指挥了哪些战役",
                entity_id="",
                canonical="",
                confidence=0.0,
            ),
        ]
    )

    validated = _validate(
        parsed,
        query=query,
        mentions=["刘伯成", "在1947年共同指挥了哪些战役"],
        records=records,
    )

    assert [item.canonical for item in validated.candidates] == ["刘伯承"]


def test_unknown_entity_is_rejected() -> None:
    records = load_entities(INDEX)
    parsed = CandidateSet(
        candidates=[
            ProposedCandidate(
                mention_text="刘伯成",
                entity_id="person:not_in_index",
                canonical="刘伯承",
                confidence=0.9,
            )
        ]
    )

    try:
        _validate(
            parsed,
            query="刘伯成在1947年做了什么？",
            mentions=["刘伯成"],
            records=records,
        )
    except ValueError as exc:
        assert "unknown entity" in str(exc)
    else:
        raise AssertionError("unknown entity should be rejected")
