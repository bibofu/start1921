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


def test_followup_pronoun_is_resolved_from_history() -> None:
    from history_agent.answering.entity_linking import resolve_followup

    records = load_entities(INDEX)
    resolved, inherited = resolve_followup(
        "那他在1957年呢？",
        ["周恩来在1956年有哪些主要经历？", "1956年，周恩来主要主持…"],
        records,
    )

    assert resolved == "那周恩来在1957年呢？"
    assert inherited == ["周恩来"]


def test_query_arms_lock_canonical_entities_and_validate() -> None:
    from history_agent.answering.query_rewrite import build_query_arms, validate_arm

    records = load_entities(INDEX)
    question = "刘邓在1947年共同指挥了哪些战役？"
    mentions = detect_mentions(question, records)
    anchored = anchor_mentions(mentions, records, query_time_range(question))
    arms = build_query_arms(question, anchored)
    canonical = next(arm for arm in arms if arm.kind == "canonical")

    assert "刘伯承 邓小平" in canonical.text
    assert validate_arm(canonical, question, (1947, 1947), records).valid
    bad = canonical.model_copy(update={"text": canonical.text + " 1950年"})
    assert not validate_arm(bad, question, (1947, 1947), records).valid


def test_entity_normalization_uses_canonical_text() -> None:
    from history_agent.answering.entity_linking import normalize_entities

    records = load_entities(INDEX)

    assert normalize_entities("刘邓在1947年共同指挥了哪些战役？", records) == (
        "刘伯承 邓小平在1947年共同指挥了哪些战役？"
    )
    # Historical place names stay as written; 1949 sources say 北平.
    assert normalize_entities("毛泽东在北平会见了谁？", records) == (
        "毛泽东在北平会见了谁？"
    )
    assert normalize_entities("毛选和党史", records) == "毛泽东选集和中国共产党历史"
    assert normalize_entities("邓小平", records) == "邓小平"
    # Short person names are not expanded to longer canonical names.
    assert normalize_entities("斯诺在西行漫记中怎样描述红军学校？", records) == (
        "斯诺在西行漫记中怎样描述红军大学？"
    )
