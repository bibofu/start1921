"""A/B the raw question against entity-derived query arms on development cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from history_agent.answering.entity_linking import (
    anchor_mentions,
    detect_mentions,
    load_entities,
    query_time_range,
    resolve_followup,
)
from history_agent.answering.planning import compile_research_plan
from history_agent.answering.query_rewrite import build_query_arms, validate_arm
from history_agent.config import get_settings
from history_agent.evaluation.pilot_metrics import evaluate_stage
from history_agent.retrieval.hybrid import search_hybrid_index
from history_agent.retrieval.models import RetrievalPlan

ROOT = Path(".")
GOLDEN = ROOT / "evals/golden/golden_dataset.json"
POOLS = ROOT / "evals/golden/ranking_pools.json"
CAPTURE = ROOT / "data/reports/golden20_r8_20261030/capture.json"
ENTITIES = ROOT / "config/entities/entities.jsonl"
OUTPUT = ROOT / "evals/query_understanding/query_arms_ab.json"
REPORT = ROOT / "evals/query_understanding/query_arms_ab.md"


def _retrieval_plan(question: str, aliases_path: Path) -> RetrievalPlan:
    interpretation = compile_research_plan(question, None, aliases_path).interpretation
    people = [
        entity.canonical for entity in interpretation.entities if entity.type == "person"
    ]
    years = (
        [interpretation.start_year, interpretation.end_year]
        if interpretation.start_year is not None and interpretation.end_year is not None
        else []
    )
    return RetrievalPlan.model_validate(
        {
            "query_intent": interpretation.intent,
            "query_years": years[:1] if years and years[0] == years[-1] else [],
            "query_year_range": years,
            "query_people": people,
            "coverage": interpretation.coverage,
        }
    )


def _metrics(case: dict, hits, file_hashes, pool) -> dict:
    result = evaluate_stage(
        case,
        [hit.model_dump() for hit in hits],
        file_hashes,
        k_values=(5, 20),
        label_mode="approved",
        ranking_pool=pool,
    )
    metrics = result["metrics"]
    return {
        "recall@20": metrics["required_group_recall@20"]["value"],
        "precision@5": metrics["precision@5"]["value"],
        "mrr@5": metrics["mrr@5"]["value"],
        "ndcg@5": metrics["pool_ndcg@5"]["value"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--arms", choices=["canonical", "full"], default="full")
    args = parser.parse_args()

    settings = get_settings()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    pools = {
        pool["case_id"]: pool
        for pool in json.loads(POOLS.read_text(encoding="utf-8"))["pools"]
    }
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    file_hashes = {
        item["document_id"]: item["sha256"] for item in capture["corpus"]["documents"]
    }
    records = load_entities(ENTITIES)

    rows = []
    for case in golden["cases"]:
        if case["split"] != "development" or case["answerability"] != "answerable":
            continue
        question = case["question"]
        resolved, _ = resolve_followup(question, [], records)
        mentions = detect_mentions(resolved, records, fuzzy=True)
        anchored = anchor_mentions(mentions, records, query_time_range(resolved))
        arms = [
            arm
            for arm in build_query_arms(resolved, anchored)
            if arm.kind != "raw"
            and (args.arms == "full" or arm.kind == "canonical")
            and validate_arm(arm, resolved, query_time_range(resolved), records).valid
        ]
        plan = _retrieval_plan(resolved, settings.person_aliases_path)
        baseline = search_hybrid_index(
            keyword_index_path=settings.keyword_index_target,
            vector_index_path=settings.vector_index_target,
            model_cache_dir=settings.model_cache_dir / "fastembed",
            aliases_path=settings.person_aliases_path,
            query=resolved,
            top_k=20,
            candidate_k=30,
            plan=plan,
        )
        rewritten = search_hybrid_index(
            keyword_index_path=settings.keyword_index_target,
            vector_index_path=settings.vector_index_target,
            model_cache_dir=settings.model_cache_dir / "fastembed",
            aliases_path=settings.person_aliases_path,
            query=resolved,
            top_k=20,
            candidate_k=30,
            plan=plan,
            additional_queries=[arm.text for arm in arms],
        )
        row = {
            "case_id": case["id"],
            "resolved": resolved,
            "arms": [arm.text for arm in arms],
            "baseline": _metrics(case, baseline.hits, file_hashes, pools[case["id"]]),
            "rewrite": _metrics(case, rewritten.hits, file_hashes, pools[case["id"]]),
        }
        rows.append(row)
        print(case["id"], row["baseline"], row["rewrite"])

    summary = {}
    for mode in ("baseline", "rewrite"):
        summary[mode] = {
            metric: mean(
                row[mode][metric] for row in rows if row[mode][metric] is not None
            )
            for metric in ("recall@20", "precision@5", "mrr@5", "ndcg@5")
        }
    payload = {"arms": args.arms, "cases": rows, "summary": summary}
    output = args.output.with_name(args.output.stem + f"_{args.arms}" + args.output.suffix)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 查询臂 A/B（开发题）",
        "",
        "只使用开发集可答题；保留题未运行。基线与重写使用同一采集配置、"
        "同一检索计划；重写只增加 canonical/per-entity 查询臂。",
        "",
        "| 指标 | baseline | rewrite | 变化 |",
        "|---|---:|---:|---:|",
    ]
    for metric in ("recall@20", "precision@5", "mrr@5", "ndcg@5"):
        base = summary["baseline"][metric]
        rewrite = summary["rewrite"][metric]
        lines.append(f"| {metric} | {base:.3f} | {rewrite:.3f} | {rewrite - base:+.3f} |")
    lines.extend(
        [
            "",
            "## 逐题",
            "",
            "| 题 | 查询臂 | baseline R/P/MRR/nDCG | rewrite R/P/MRR/nDCG |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        base = row["baseline"]
        rewrite = row["rewrite"]

        def fmt(values: dict) -> str:
            return " / ".join(
                "N/A" if values[key] is None else f"{values[key]:.2f}"
                for key in ("recall@20", "precision@5", "mrr@5", "ndcg@5")
            )

        lines.append(
            "| `{}` | {} | {} | {} |".format(
                row["case_id"], len(row["arms"]), fmt(base), fmt(rewrite)
            )
        )
    report = REPORT.with_name(REPORT.stem + f"_{args.arms}" + REPORT.suffix)
    report.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    print("summary", summary)


if __name__ == "__main__":
    main()
