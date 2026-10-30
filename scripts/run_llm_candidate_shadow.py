"""Shadow-run LLM entity candidate generation against dictionary-only detection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from history_agent.answering.entity_candidates import propose_candidates
from history_agent.answering.entity_linking import (
    DetectedMention,
    MentionCandidate,
    anchor_mentions,
    detect_mentions,
    load_entities,
    query_time_range,
    uncovered_spans,
)
from history_agent.config import get_settings
from history_agent.evaluation.query_understanding_eval import canonical_keys

DEFAULT_CASES = Path("evals/query_understanding/candidate_cases.json")
DEFAULT_INDEX = Path("config/entities/entities.jsonl")
DEFAULT_OUTPUT = Path("evals/query_understanding/llm_candidates")


def _keys(values: list[str]) -> set[str]:
    return {key for value in values for key in canonical_keys(value)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    settings = get_settings()
    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    records = load_entities(args.index)
    by_id = {record.entity_id: record for record in records}
    rows = []
    dict_tp = dict_pred = llm_tp = llm_pred = expected_total = 0
    statuses: dict[str, int] = {}

    for case in payload["cases"]:
        query = case["question"]
        expected = _keys(case["expected"])
        mentions = detect_mentions(query, records, fuzzy=True)
        dict_anchored = anchor_mentions(mentions, records, query_time_range(query))
        dict_set = {
            key
            for mention in dict_anchored
            if mention.status == "anchored"
            for name in mention.canonicals
            for key in canonical_keys(name)
        }
        spans = uncovered_spans(query, mentions)
        result = propose_candidates(settings, query, spans, records)
        if result.status == "invalid_response":
            result = propose_candidates(settings, query, spans, records)
        statuses[result.status] = statuses.get(result.status, 0) + 1
        llm_mentions = list(mentions)
        for candidate in result.candidates:
            record = by_id[candidate.entity_id]
            start = query.find(candidate.mention_text)
            llm_mentions.append(
                DetectedMention(
                    text=candidate.mention_text,
                    start=start,
                    end=start + len(candidate.mention_text),
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
        llm_anchored = anchor_mentions(llm_mentions, records, query_time_range(query))
        llm_set = {
            key
            for mention in llm_anchored
            if mention.status == "anchored"
            for name in mention.canonicals
            for key in canonical_keys(name)
        }
        dict_tp += len(expected & dict_set)
        dict_pred += len(dict_set)
        llm_tp += len(expected & llm_set)
        llm_pred += len(llm_set)
        expected_total += len(expected)
        rows.append(
            {
                "id": case["id"],
                "question": query,
                "expected": sorted(expected),
                "dictionary": sorted(dict_set),
                "llm_status": result.status,
                "llm_candidates": [candidate.model_dump() for candidate in result.candidates],
                "with_llm": sorted(llm_set),
                "missing_dictionary": sorted(expected - dict_set),
                "missing_with_llm": sorted(expected - llm_set),
            }
        )
        print(
            case["id"],
            result.status,
            sorted(expected - dict_set),
            "->",
            sorted(expected - llm_set),
        )

    def prf(tp: int, predicted: int) -> dict[str, float | int]:
        precision = tp / predicted if predicted else 0.0
        recall = tp / expected_total if expected_total else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "true_positive": tp,
            "predicted": predicted,
            "expected": expected_total,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    result_payload = {
        "version": payload["version"],
        "statuses": statuses,
        "dictionary": prf(dict_tp, dict_pred),
        "with_llm": prf(llm_tp, llm_pred),
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dictionary = result_payload["dictionary"]
    with_llm = result_payload["with_llm"]
    lines = [
        "# LLM 实体候选 shadow 报告",
        "",
        "对照：词典+模糊匹配 vs 再叠加 LLM 候选。LLM 只能从实体索引中选择，不能新增实体。",
        "",
        "| 指标 | 词典 | 词典 + LLM |",
        "|---|---:|---:|",
        f"| Precision | {dictionary['precision']:.1%} | {with_llm['precision']:.1%} |",
        f"| Recall | {dictionary['recall']:.1%} | {with_llm['recall']:.1%} |",
        f"| F1 | {dictionary['f1']:.1%} | {with_llm['f1']:.1%} |",
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
                row["llm_status"],
                "、".join(row["missing_dictionary"]) or "—",
                "、".join(row["missing_with_llm"]) or "—",
                "、".join(
                    f"{item['mention_text']}→{item['canonical']}"
                    for item in row["llm_candidates"]
                )
                or "—",
            )
        )
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("dictionary", dictionary)
    print("with_llm", with_llm)


if __name__ == "__main__":
    main()
