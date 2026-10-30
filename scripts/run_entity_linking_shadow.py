"""Shadow-run entity linking with optional LLM candidate generation."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter

from history_agent.answering.entity_candidates import propose_candidates
from history_agent.answering.entity_linking import (
    DetectedMention,
    MentionCandidate,
    anchor_mentions,
    detect_mentions,
    load_entities,
    query_time_range,
    resolve_followup,
    uncovered_spans,
)
from history_agent.answering.query_rewrite import build_query_arms, validate_arm
from history_agent.config import get_settings
from history_agent.evaluation.query_understanding_eval import (
    canonical_keys,
    load_dataset,
)

DEFAULT_CASES = Path("evals/query_understanding/cases.json")
DEFAULT_INDEX = Path("config/entities/entities.jsonl")
DEFAULT_OUTPUT = Path("evals/query_understanding/entity_linking")


def _prf(tp: int, predicted: int, expected: int) -> dict[str, float | int]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": tp,
        "predicted": predicted,
        "expected": expected,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _keys(values: list[str]) -> set[str]:
    return {key for value in values for key in canonical_keys(value)}


FUNCTION_MARKERS = (
    "哪些", "什么", "怎样", "如何", "为什么", "主要", "经历", "活动",
    "担任", "职务", "参加", "期间", "做了", "有哪些",
)
SPAN_SPLIT = re.compile(r"[在的年了和与\s\d年月日，。、？！?!:：;；]")


def _entity_like_spans(spans: list[str], records) -> list[str]:
    """Extract proper-noun-like segments and keep only alias-close ones."""

    aliases = [
        alias
        for record in records
        for alias in {record.canonical, *record.aliases}
        if alias
    ]
    selected: list[str] = []
    for span in spans:
        for segment in SPAN_SPLIT.split(span):
            if not 2 <= len(segment) <= 8:
                continue
            if any(marker in segment for marker in FUNCTION_MARKERS):
                continue
            close = any(
                abs(len(alias) - len(segment)) <= 1
                and SequenceMatcher(None, segment, alias).ratio() >= 0.5
                for alias in aliases
            )
            if close and segment not in selected:
                selected.append(segment)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    dataset = load_dataset(args.cases)
    records = load_entities(args.index)
    by_id = {record.entity_id: record for record in records}
    rows = []
    dict_tp = dict_pred = dict_expected = 0
    llm_tp = llm_pred = 0
    unresolved = detected_total = 0
    arms_total = arms_valid = 0
    statuses: Counter[str] = Counter()
    llm_calls = 0
    usage_totals: Counter[str] = Counter()

    for case in dataset.cases:
        expected = {
            key
            for mention in case.mentions
            for name in mention.canonical
            for key in canonical_keys(name)
        }
        resolved_question, inherited = resolve_followup(
            case.question, [message.content for message in case.history], records
        )
        mentions = detect_mentions(resolved_question, records, fuzzy=True)
        time_range = query_time_range(resolved_question)
        anchored = anchor_mentions(mentions, records, time_range)
        dict_detected = {
            key
            for mention in mentions
            for candidate in mention.candidates
            for key in _keys([candidate.canonical])
        }
        dict_anchored = {
            key
            for mention in anchored
            if mention.status == "anchored"
            for name in mention.canonicals
            for key in canonical_keys(name)
        }

        raw_spans = uncovered_spans(resolved_question, mentions)
        spans = _entity_like_spans(raw_spans, records)
        llm_result = None
        if spans and not args.no_llm:
            started = perf_counter()
            llm_result = propose_candidates(
                settings, resolved_question, spans, records
            )
            duration_ms = round((perf_counter() - started) * 1000, 2)
            statuses[llm_result.status] += 1
            llm_calls += 1
            if llm_result.usage:
                usage_totals.update(llm_result.usage)
        else:
            duration_ms = None
        merged = list(mentions)
        existing_ranges = [(mention.start, mention.end) for mention in mentions]
        existing_canonicals = {
            candidate.canonical
            for mention in mentions
            for candidate in mention.candidates
        }
        for candidate in llm_result.candidates if llm_result else ():
            start = resolved_question.find(candidate.mention_text)
            if start < 0:
                continue
            end = start + len(candidate.mention_text)
            if candidate.canonical in existing_canonicals:
                continue
            if any(left < end and start < right for left, right in existing_ranges):
                continue
            record = by_id[candidate.entity_id]
            if record.type == "person_group":
                members = {
                    by_id[member].canonical
                    for member in record.members
                    if member in by_id
                }
                if members <= existing_canonicals:
                    continue
            merged.append(
                DetectedMention(
                    text=candidate.mention_text,
                    start=start,
                    end=end,
                    candidates=[
                        MentionCandidate(
                            entity_id=record.entity_id,
                            canonical=record.canonical,
                            type=record.type,
                            score=candidate.confidence,
                        )
                    ],
                )
            )
            existing_ranges.append((start, end))
            existing_canonicals.add(record.canonical)
        merged.sort(key=lambda mention: mention.start)
        llm_anchored_mentions = anchor_mentions(merged, records, time_range)
        llm_detected = {
            key
            for mention in merged
            for candidate in mention.candidates
            for key in _keys([candidate.canonical])
        }
        llm_anchored = {
            key
            for mention in llm_anchored_mentions
            if mention.status == "anchored"
            for name in mention.canonicals
            for key in canonical_keys(name)
        }

        arms = build_query_arms(resolved_question, llm_anchored_mentions)
        validations = [
            validate_arm(arm, resolved_question, time_range, records) for arm in arms
        ]
        arms_total += len(arms)
        arms_valid += sum(validation.valid for validation in validations)

        dict_tp += len(expected & dict_detected)
        dict_pred += len(dict_detected)
        dict_expected += len(expected)
        llm_tp += len(expected & llm_detected)
        llm_pred += len(llm_detected)
        unresolved += sum(
            1 for mention in llm_anchored_mentions if mention.status == "unresolved"
        )
        detected_total += len(llm_anchored_mentions)
        rows.append(
            {
                "id": case.id,
                "split": case.split,
                "resolved_question": resolved_question,
                "inherited": inherited,
                "expected": sorted(expected),
                "dictionary": {
                    "detected": sorted(dict_detected),
                    "anchored": sorted(dict_anchored),
                    "missing": sorted(expected - dict_detected),
                },
                "llm": {
                    "status": llm_result.status if llm_result else "skipped",
                    "spans": spans,
                    "raw_spans": raw_spans,
                    "candidates": [
                        candidate.model_dump()
                        for candidate in (llm_result.candidates if llm_result else ())
                    ],
                    "usage": llm_result.usage if llm_result else None,
                    "duration_ms": duration_ms,
                    "error_code": llm_result.error_code if llm_result else None,
                },
                "with_llm": {
                    "detected": sorted(llm_detected),
                    "anchored": sorted(llm_anchored),
                    "missing": sorted(expected - llm_detected),
                },
                "unresolved_mentions": [
                    mention.text
                    for mention in llm_anchored_mentions
                    if mention.status == "unresolved"
                ],
                "mentions": [mention.model_dump() for mention in llm_anchored_mentions],
                "arms": [arm.model_dump() for arm in arms],
                "invalid_arms": [
                    {"text": arm.text, "issues": validation.issues}
                    for arm, validation in zip(arms, validations, strict=True)
                    if not validation.valid
                ],
            }
        )

    result = {
        "cases": len(dataset.cases),
        "dictionary_detection": _prf(dict_tp, dict_pred, dict_expected),
        "with_llm_detection": _prf(llm_tp, llm_pred, dict_expected),
        "llm_statuses": dict(statuses),
        "llm_calls": llm_calls,
        "llm_usage": dict(usage_totals),
        "unresolved_rate": unresolved / detected_total if detected_total else 0.0,
        "arms_total": arms_total,
        "arms_valid": arms_valid,
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    dictionary = result["dictionary_detection"]
    with_llm = result["with_llm_detection"]
    lines = [
        "# 实体链接 shadow 报告（含 LLM 候选）",
        "",
        "只检测和锚定，不改变检索。实体索引 v1 覆盖人物、文献、会议、事件、"
        "地点、组织和组合简称；LLM 只在未覆盖 span 上从索引内提名。",
        "",
        "| 指标 | 词典 + 模糊 | 再加 LLM |",
        "|---|---:|---:|",
        f"| Precision | {dictionary['precision']:.1%} | {with_llm['precision']:.1%} |",
        f"| Recall | {dictionary['recall']:.1%} | {with_llm['recall']:.1%} |",
        f"| F1 | {dictionary['f1']:.1%} | {with_llm['f1']:.1%} |",
        f"| 查询臂校验通过 | {arms_valid} / {arms_total} | — |",
        f"| LLM 调用 / 状态 | {llm_calls} | {result['llm_statuses']} |",
        f"| LLM token | — | {result['llm_usage'] or 'N/A'} |",
        "",
        "## 逐题",
        "",
        "| 题 | LLM 状态 | 词典漏检 | 加 LLM 后漏检 | LLM 候选 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                row["id"],
                row["llm"]["status"],
                "、".join(row["dictionary"]["missing"]) or "—",
                "、".join(row["with_llm"]["missing"]) or "—",
                "、".join(
                    f"{item['mention_text']}→{item['canonical']}"
                    for item in row["llm"]["candidates"]
                )
                or "—",
            )
        )
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("dictionary", dictionary)
    print("with_llm", with_llm)
    print("llm", result["llm_statuses"], result["llm_usage"])


if __name__ == "__main__":
    main()
