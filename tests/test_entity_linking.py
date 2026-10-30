from __future__ import annotations

from pathlib import Path

from history_agent.answering.entity_linking import (
    anchor_mentions,
    detect_mentions,
    load_entities,
    query_time_range,
)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "config/entities/entities.jsonl"


def test_index_has_expected_coverage() -> None:
    records = load_entities(INDEX)

    assert len(records) >= 140
    assert {record.type for record in records} >= {
        "person",
        "document",
        "congress",
        "event",
        "period",
        "place",
        "organization",
    }


def test_group_alias_returns_multiple_people() -> None:
    records = load_entities(INDEX)
    mentions = detect_mentions("刘邓在1947年共同指挥了哪些战役？", records)

    assert len(mentions) == 1
    assert mentions[0].text == "刘邓"
    assert {candidate.canonical for candidate in mentions[0].candidates} == {
        "刘伯承",
        "邓小平",
    }


def test_congress_shorthand_prefers_longest_match() -> None:
    records = load_entities(INDEX)

    seven = detect_mentions("七大在哪一年召开？", records)
    seventeen = detect_mentions("十七大在哪一年召开？", records)

    assert [candidate.canonical for candidate in seven[0].candidates] == ["中共七大"]
    assert [candidate.canonical for candidate in seventeen[0].candidates] == ["中共十七大"]


def test_anchoring_with_time_and_unknown_mentions() -> None:
    records = load_entities(INDEX)
    question = "刘邓在1947年共同指挥了哪些战役？"
    mentions = detect_mentions(question, records)
    anchored = anchor_mentions(mentions, records, query_time_range(question))

    assert anchored[0].status == "anchored"
    assert set(anchored[0].canonicals) == {"刘伯承", "邓小平"}
    assert detect_mentions("习近平在2024年考察了哪些地方？", records) == []


def test_organization_group_alias() -> None:
    records = load_entities(INDEX)
    mentions = detect_mentions("比较国共两党的军事策略", records)

    assert len(mentions) == 1
    assert {candidate.canonical for candidate in mentions[0].candidates} == {
        "中国共产党",
        "中国国民党",
    }
