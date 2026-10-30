"""Shadow-run mention detection and anchoring on the query-understanding set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from history_agent.answering.entity_linking import (
    anchor_mentions,
    detect_mentions,
    load_entities,
    query_time_range,
    resolve_followup,
)
from history_agent.answering.query_rewrite import build_query_arms, validate_arm
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    dataset = load_dataset(args.cases)
    records = load_entities(args.index)
    rows = []
    detect_tp = detect_pred = detect_expected = 0
    anchor_tp = anchor_pred = anchor_expected = 0
    unresolved = detected_total = 0
    arms_total = arms_valid = 0

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
        arms = build_query_arms(resolved_question, anchored)
        validations = [
            validate_arm(arm, resolved_question, time_range, records) for arm in arms
        ]
        arms_total += len(arms)
        arms_valid += sum(validation.valid for validation in validations)
        detected = {
            key
            for mention in mentions
            for candidate in mention.candidates
            for key in canonical_keys(candidate.canonical)
        }
        anchored_set = {
            key
            for mention in anchored
            if mention.status == "anchored"
            for name in mention.canonicals
            for key in canonical_keys(name)
        }
        detect_tp += len(expected & detected)
        detect_pred += len(detected)
        detect_expected += len(expected)
        anchor_tp += len(expected & anchored_set)
        anchor_pred += len(anchored_set)
        anchor_expected += len(expected)
        unresolved += sum(1 for mention in anchored if mention.status == "unresolved")
        detected_total += len(anchored)
        rows.append(
            {
                "id": case.id,
                "split": case.split,
                "resolved_question": resolved_question,
                "inherited": inherited,
                "expected": sorted(expected),
                "detected": sorted(detected),
                "anchored": sorted(anchored_set),
                "missing_detection": sorted(expected - detected),
                "missing_anchor": sorted(expected - anchored_set),
                "extra_anchor": sorted(anchored_set - expected),
                "unresolved_mentions": [
                    mention.text
                    for mention in anchored
                    if mention.status == "unresolved"
                ],
                "mentions": [mention.model_dump() for mention in anchored],
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
        "detection": _prf(detect_tp, detect_pred, detect_expected),
        "anchoring": _prf(anchor_tp, anchor_pred, anchor_expected),
        "unresolved_rate": unresolved / detected_total if detected_total else 0.0,
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    detection = result["detection"]
    anchoring = result["anchoring"]
    lines = [
        "# 实体链接 shadow 报告",
        "",
        "只检测和锚定，不改变检索。实体索引 v1 覆盖人物、文献、会议、事件、"
        "地点、组织和组合简称；未解决 mention 主要来自回指和索引外人物。",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 题数 | {result['cases']} |",
        f"| 检测 Precision | {detection['precision']:.1%} |",
        f"| 检测 Recall | {detection['recall']:.1%} |",
        f"| 检测 F1 | {detection['f1']:.1%} |",
        f"| 锚定 Precision | {anchoring['precision']:.1%} |",
        f"| 锚定 Recall | {anchoring['recall']:.1%} |",
        f"| 锚定 F1 | {anchoring['f1']:.1%} |",
        f"| 未解决 mention 比例 | {result['unresolved_rate']:.1%} |",
        f"| 查询臂总数 | {arms_total} |",
        f"| 查询臂校验通过率 | {arms_valid / arms_total:.1%} |",
        "",
        "## 逐题",
        "",
        "| 题 | 未检测到 | 未锚定 | 多余锚定 | 未解决 mention |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                row["id"],
                "、".join(row["missing_detection"]) or "—",
                "、".join(row["missing_anchor"]) or "—",
                "、".join(row["extra_anchor"]) or "—",
                "、".join(row["unresolved_mentions"]) or "—",
            )
        )
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "detection",
        {
            key: round(value, 3) if isinstance(value, float) else value
            for key, value in detection.items()
        },
        "anchoring",
        {
            key: round(value, 3) if isinstance(value, float) else value
            for key, value in anchoring.items()
        },
        "unresolved",
        round(result["unresolved_rate"], 3),
    )


if __name__ == "__main__":
    main()
