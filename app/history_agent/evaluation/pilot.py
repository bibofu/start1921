"""Collect and score reviewable six-case trials without changing Golden v1."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from history_agent.answering.models import QuestionRequest
from history_agent.answering.service import PROMPT_VERSION, answer_question
from history_agent.config import Settings, get_settings
from history_agent.evaluation.golden import (
    _git_metadata,
    _index_attribution,
    _load_index_metadata,
)
from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit
from history_agent.evaluation.pilot_models import PilotDataset, case_definition
from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime
from history_agent.extraction.report import load_page_records
from history_agent.processing.chunks import effective_pages
from history_agent.retrieval.hybrid import search_hybrid_index

VERSION = "reviewable-pilot-v1"
DEFAULT_DATASET = "evals/golden/pilot_annotations.json"
DEFAULT_K = (1, 3, 5, 10, 20)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf8"))


def source_fingerprint(project_root: Path) -> str:
    files = {
        path.relative_to(project_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((project_root / "app" / "history_agent").rglob("*.py"))
    }
    return digest(files)


def corpus_snapshot(settings: Settings) -> dict[str, Any]:
    with closing(
        sqlite3.connect(
            f"file:{settings.database_path.as_posix()}?mode=ro",
            uri=True,
        )
    ) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT d.document_id,d.title,f.sha256,f.relative_path,f.page_count "
            "FROM documents d JOIN document_files f ON f.document_id=d.document_id "
            "WHERE d.enabled=1 AND f.is_current=1 AND f.is_present=1 ORDER BY d.document_id"
        ).fetchall()
    documents = [dict(row) for row in rows]
    for item in documents:
        path = (settings.project_root / item["relative_path"]).resolve()
        if not path.is_relative_to(settings.docs_dir.resolve()):
            raise ValueError("corpus path is outside docs directory")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"PDF changed since corpus scan: {item['document_id']}")
    return {"documents": documents, "sha256": digest(documents)}


def validate_anchors(dataset: PilotDataset, settings: Settings, corpus: dict[str, Any]) -> None:
    hashes = {item["document_id"]: item["sha256"] for item in corpus["documents"]}
    cache: dict[str, Any] = {}
    for case in dataset.cases:
        for group in case.evidence_groups:
            for anchor in group.alternatives:
                if hashes.get(anchor.document_id) != anchor.file_sha256:
                    raise ValueError(f"stale or unavailable source: {case.id}/{group.id}")
                if anchor.document_id not in cache:
                    base = load_page_records(settings.pages_dir / f"{anchor.document_id}.jsonl")
                    ocr_path = settings.ocr_dir / f"{anchor.document_id}.jsonl"
                    ocr = load_page_records(ocr_path) if ocr_path.exists() else {}
                    cache[anchor.document_id] = effective_pages(base, ocr)
                page = cache[anchor.document_id].get(anchor.pdf_page)
                if page is not None and page.file_sha256 != anchor.file_sha256:
                    raise ValueError(f"stale page extraction: {case.id}/{group.id}")
                if page is None or re.sub(r"\s+", "", anchor.quote) not in re.sub(
                    r"\s+",
                    "",
                    page.normalized_text,
                ):
                    raise ValueError(f"evidence quote not on source page: {case.id}/{group.id}")


EVIDENCE_HEADER = re.compile(r"\[(E\d+)\] 《([^》]+)》PDF第(\d+)页；片段标注年份：[^\n]*\n")


def generation_contexts(
    calls: list[dict[str, Any]], documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Parse the production prompt's explicit evidence block, never repair answers."""
    by_title: dict[str, list[str]] = {}
    for document in documents:
        by_title.setdefault(document["title"], []).append(document["document_id"])
    contexts = []
    for call in calls:
        for message in call["request"].get("messages", []):
            content = message.get("content", "")
            marker = "\n\n仅可使用的本地证据：\n"
            if (
                message.get("role") != "user"
                or not content.startswith("问题：")
                or marker not in content
            ):
                continue
            evidence = content.split(marker, 1)[1]
            matches = list(EVIDENCE_HEADER.finditer(evidence))
            # Hierarchical summaries may repeat valid-looking evidence headers.
            # Only the direct evidence format starts immediately with such a header.
            if matches and evidence[: matches[0].start()].strip():
                matches = []
            hits: list[dict[str, Any]] = []
            unmapped = []
            for index, match in enumerate(matches):
                ids = by_title.get(match.group(2), [])
                if len(ids) != 1:
                    unmapped.append(match.group(1))
                    continue
                end = matches[index + 1].start() if index + 1 < len(matches) else len(evidence)
                hits.append(
                    {
                        "document_id": ids[0],
                        "title": match.group(2),
                        "pdf_page_start": int(match.group(3)),
                        "pdf_page_end": int(match.group(3)),
                        "text": evidence[match.end() : end].strip(),
                        "rank": len(hits) + 1,
                        "evidence_id": match.group(1),
                    }
                )
            direct = bool(matches) and not unmapped
            contexts.append(
                {
                    "call_index": call["call_index"],
                    "stage": "generation_prompt_evidence",
                    "hits": hits,
                    "evidence_text": evidence,
                    "mapping_complete": direct,
                    "http_status": call.get("http_status"),
                    "notes": []
                    if direct
                    else [
                        "Summary-based or unmapped evidence: preserve text; do not score as pages.",
                    ],
                }
            )
    return contexts


def production_stages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        response = record["response"]
        if record["phase"] == "retrieval_round":
            for source in response.get("trace") or []:
                stages.append({**source, "stage": f"production_{index}_{source['stage']}"})
        else:
            stages.append(
                {
                    "stage": f"production_{index}_{record['phase']}",
                    "query": response["query"],
                    "hits": response["hits"],
                    "elapsed_ms": None,
                    "status": "ok",
                }
            )
    return stages


def collect(
    dataset_path: Path,
    output: Path,
    *,
    candidate_k: int = 30,
    top_k: int = 20,
    answer_top_k: int = 10,
    with_llm: bool = False,
    run_name: str = "pilot_baseline",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    dataset = PilotDataset.model_validate(read_json(dataset_path))
    if not 1 <= top_k <= candidate_k <= 100 or not 1 <= answer_top_k <= 12:
        raise ValueError("require 1 <= top_k <= candidate_k <= 100; answer_top_k in 1..12")
    corpus = corpus_snapshot(settings)
    validate_anchors(dataset, settings, corpus)
    file_hashes = {item["document_id"]: item["sha256"] for item in corpus["documents"]}
    reports = _load_index_metadata(settings)
    results = []
    actual_branches: set[str] = set()
    degraded_cases: dict[str, list[str]] = {}
    candidate_fingerprints: dict[str, dict[str, str]] = {}
    for case in dataset.cases:
        print(f"collect {case.id}", flush=True)
        started = perf_counter()
        response = search_hybrid_index(
            keyword_index_path=settings.keyword_index_path,
            vector_index_path=settings.vector_index_path,
            model_cache_dir=settings.model_cache_dir / "fastembed",
            aliases_path=settings.person_aliases_path,
            query=case.question,
            top_k=top_k,
            candidate_k=candidate_k,
            capture_trace=True,
        )
        search_ms = round((perf_counter() - started) * 1000, 3)
        if response.degraded_components:
            degraded_cases[case.id] = response.degraded_components
        trace = [item.model_dump(mode="json") for item in response.trace or []]
        candidate_fingerprints[case.id] = {
            item["stage"]: digest(
                [evidence_unit(hit, file_hashes)["unit_id"] for hit in item["hits"]]
            )
            for item in trace
            if item["stage"] in {"keyword_candidates", "vector_candidates"}
        }
        for branch in ("keyword", "vector"):
            if any(
                item["stage"] == f"{branch}_candidates" and item["status"] == "ok" for item in trace
            ):
                actual_branches.add(branch)
        answer_settings = (
            settings if with_llm else settings.model_copy(update={"llm_api_key": None})
        )
        runtime = RecordedLLMRuntime(settings.llm_max_concurrency)
        started = perf_counter()
        try:
            answer = answer_question(
                answer_settings,
                QuestionRequest(
                    question=case.question,
                    top_k=answer_top_k,
                ),
                runtime=runtime,
            )
            answer_payload = answer.model_dump(mode="json")
        finally:
            asyncio.run(runtime.aclose())
        answer_ms = round((perf_counter() - started) * 1000, 3)
        contexts = generation_contexts(runtime.calls, corpus["documents"])
        production_trace = production_stages(runtime.retrieval_calls)
        pool: dict[str, Any] = {}
        for item in [*trace, *production_trace, *contexts]:
            for hit in item["hits"]:
                unit = evidence_unit(hit, file_hashes)
                pool.setdefault(unit["unit_id"], unit)
        results.append(
            {
                "case_id": case.id,
                "question": case.question,
                "case_definition_sha256": digest(case_definition(case.model_dump(mode="json"))),
                "retrieval": response.model_dump(mode="json"),
                "stages": trace,
                "candidate_pool": list(pool.values()),
                "answer": answer_payload,
                "llm_calls": runtime.calls,
                "generation_contexts": contexts,
                "production_stages": production_trace,
                "retrieval_ms": search_ms,
                "answer_ms": answer_ms,
            }
        )
        # A recoverable checkpoint prevents losing expensive completed calls.
        write_json(output.with_suffix(".partial.json"), {"completed_cases": results})
    attribution = _index_attribution(reports["reports"], sorted(actual_branches))
    if degraded_cases:
        attribution["attribution_safe"] = False
        attribution["attribution_unsafe_reasons"].append(
            "one or more cases used degraded retrieval"
        )
    result = {
        "schema_version": 1,
        "evaluator_version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": run_name,
        "dataset_sha256": digest(dataset.model_dump(mode="json")),
        "git": _git_metadata(settings.project_root),
        "source_sha256": source_fingerprint(settings.project_root),
        "corpus": corpus,
        "index_metadata": reports,
        "index_attribution": attribution,
        "degraded_cases": degraded_cases,
        "config": {
            "candidate_k": candidate_k,
            "top_k": top_k,
            "answer_top_k": answer_top_k,
            "component_query": "raw_question",
            "with_llm": with_llm,
            "llm_model": settings.llm_model if with_llm else None,
            "query_planner_model": settings.llm_query_planner_model if with_llm else None,
            "prompt_version": PROMPT_VERSION,
            "e2e_candidate_policy": "production default; independent from component budget",
        },
        "cases": results,
        "component_candidate_fingerprints": candidate_fingerprints,
    }
    write_json(output, result)
    return result


def stage_metrics(
    case: dict[str, Any],
    hits: list[dict[str, Any]],
    file_hashes: dict[str, str],
    k_values: tuple[int, ...],
    mode: str,
) -> dict[str, Any]:
    result = evaluate_stage(case, hits, file_hashes, k_values, label_mode=mode)
    full_k = max(1, len(hits))
    full = evaluate_stage(case, hits, file_hashes, (full_k,), label_mode=mode)
    result["metrics"]["required_group_recall_at_returned"] = full["metrics"][
        f"required_group_recall@{full_k}"
    ]
    return result


def _aggregate(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    bins: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for case in results:
        for stage in case["stages"]:
            if stage.get("scope") != "component":
                continue
            for name, metric in stage[mode]["metrics"].items():
                bins.setdefault(f"{stage['stage']}.{name}", []).append((case["case_id"], metric))
    result = {}
    for key, items in bins.items():
        valid = [(case_id, metric) for case_id, metric in items if metric["evaluable"]]
        result[key] = {
            "value": sum(item["value"] for _, item in valid) / len(valid) if valid else None,
            "aggregation": "macro_over_cases",
            "evaluable_cases": len(valid),
            "total_cases": len(items),
            "evaluable_case_ids": [case_id for case_id, _ in valid],
            "unevaluable_case_ids": [case_id for case_id, item in items if not item["evaluable"]],
        }
    return result


def score(
    dataset_path: Path, capture_path: Path, output: Path, k_values: tuple[int, ...] = DEFAULT_K
) -> dict[str, Any]:
    dataset = PilotDataset.model_validate(read_json(dataset_path))
    capture = read_json(capture_path)
    captured = {item["case_id"]: item for item in capture["cases"]}
    if {case.id for case in dataset.cases} != set(captured):
        raise ValueError("capture and dataset case IDs differ")
    file_hashes = {item["document_id"]: item["sha256"] for item in capture["corpus"]["documents"]}
    results = []
    for model in dataset.cases:
        case = model.model_dump(mode="json")
        raw = captured[model.id]
        if digest(case_definition(case)) != raw["case_definition_sha256"]:
            raise ValueError(f"question or evidence definition changed: {model.id}; recollect")
        stages = []
        for source in [*raw["stages"], *raw.get("production_stages", [])]:
            if source["status"] != "ok":
                continue
            item = {
                "stage": source["stage"],
                "query": source["query"],
                "scope": "production_retrieval"
                if source["stage"].startswith("production_")
                else "component",
                "elapsed_ms": source["elapsed_ms"],
            }
            for mode in ("provisional", "approved"):
                item[mode] = stage_metrics(case, source["hits"], file_hashes, k_values, mode)
            stages.append(item)
        for source in raw["generation_contexts"]:
            if not source["mapping_complete"] or source.get("http_status") != 200:
                continue
            item = {
                "stage": f"generation_prompt_evidence_call_{source['call_index']}",
                "scope": "production_prompt",
                "query": model.question,
                "elapsed_ms": None,
            }
            for mode in ("provisional", "approved"):
                item[mode] = stage_metrics(case, source["hits"], file_hashes, k_values, mode)
            stages.append(item)
        results.append(
            {
                "case_id": model.id,
                "question": model.question,
                "human_review": case["human_review"],
                "stages": stages,
                "answer": raw["answer"],
                "retrieval_ms": raw["retrieval_ms"],
                "answer_ms": raw["answer_ms"],
                "generation_assessment": {
                    "value": None,
                    "evaluable": False,
                    "reason": "requires fact-by-fact human review; not auto string scoring",
                },
            }
        )
    result = {
        "evaluator_version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": capture["run_name"],
        "capture_sha256": digest(capture),
        "dataset_sha256": digest(dataset.model_dump(mode="json")),
        "corpus_sha256": capture["corpus"]["sha256"],
        "git": capture["git"],
        "source_sha256": capture.get("source_sha256"),
        "index_metadata": capture["index_metadata"],
        "degraded_cases": capture.get("degraded_cases", {}),
        "config": capture["config"],
        "index_attribution": capture["index_attribution"],
        "component_candidate_fingerprints": capture.get("component_candidate_fingerprints"),
        "labels": "Provisional agent labels are diagnostic only, not approved Golden results.",
        "k_values": list(k_values),
        "cases": results,
        "provisional_aggregate": _aggregate(results, "provisional"),
        "approved_aggregate": _aggregate(results, "approved"),
    }
    write_json(output, result)
    output.with_suffix(".md").write_text(markdown_report(result), encoding="utf8")
    return result


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# 六题评测试点报告",
        "",
        f"运行：`{report['run_name']}`",
        "",
        "以下数值来自 Agent 核对的暂定标签，不是人工确认的 Golden 分数。",
        "未知候选不按不相关处理，未审题目的正式指标保持不可评。",
        "",
        "同次运行的多 K 值是排序前缀诊断，不等于重新执行不同 Top-K 的生产实验。",
        "生成上下文来自实际 HTTP 请求中的证据区；它与最终答案引用列表分别记录。",
        "",
        "| 题目 | 阶段 | 关键证据组 Recall@5 | Precision@5 | MRR@5 | 未判断候选 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        for stage in case["stages"]:
            if stage["stage"] not in {
                "keyword_candidates",
                "vector_candidates",
                "rrf_fusion",
                "rule_ranking",
                "page_deduplication",
                "final",
            }:
                continue
            metrics = stage["provisional"]["metrics"]
            values = []
            for key in ("required_group_recall@5", "precision@5", "mrr@5"):
                metric = metrics.get(key, {})
                value = metric.get("value")
                values.append(f"{value:.3f}" if value is not None else "不可评")
            unknown = stage["provisional"]["diagnostics"].get("unknown_judgment_count", "—")
            lines.append(
                f"| {case['case_id']} | {stage['stage']} | "
                + " | ".join(values)
                + f" | {unknown} |"
            )
    lines += [
        "",
        "逐题答案、引用、模型状态、Token 用量、各指标不可评原因与分母见同名 JSON。",
        "正式分数仅纳入人工已批准标签；nDCG 等未满足标注条件的指标不填零。",
        "",
    ]
    return "\n".join(lines)


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = ("evaluator_version", "dataset_sha256", "corpus_sha256", "k_values")
    reasons = [f"{key} differs" for key in keys if left[key] != right[key]]
    if [item["case_id"] for item in left["cases"]] != [item["case_id"] for item in right["cases"]]:
        reasons.append("case IDs differ")
    metrics = {}
    for name in sorted(set(left["provisional_aggregate"]) & set(right["provisional_aggregate"])):
        a, b = left["provisional_aggregate"][name], right["provisional_aggregate"][name]
        valid = not reasons and a["evaluable_case_ids"] == b["evaluable_case_ids"]
        valid = valid and a["value"] is not None and b["value"] is not None
        metrics[name] = {
            "comparable": valid,
            "delta": b["value"] - a["value"] if valid else None,
            "left_cases": a["evaluable_case_ids"],
            "right_cases": b["evaluable_case_ids"],
        }
    changes = {
        key: [left["config"].get(key), right["config"].get(key)]
        for key in set(left["config"]) | set(right["config"])
        if left["config"].get(key) != right["config"].get(key)
    }
    pools_known = all(report.get("component_candidate_fingerprints") for report in (left, right))
    pools_equal = (
        left.get("component_candidate_fingerprints")
        == right.get("component_candidate_fingerprints")
        if pools_known
        else None
    )
    attribution_reasons = []
    if set(changes) - {"top_k"}:
        attribution_reasons.append(
            "Pilot isolation currently verifies only Top-K or repeated-control experiments"
        )
    if pools_equal is not True:
        attribution_reasons.append("Isolation requires identical ordered branch candidates")
    if (
        not left.get("source_sha256") or left.get("source_sha256") != right.get("source_sha256")
    ):
        attribution_reasons.append("Isolation requires identical captured source code")
    return {
        "compatible": not reasons,
        "reasons": reasons,
        "config_changes": changes,
        "basis": "provisional_agent_review",
        "metrics": metrics,
        "ordered_branch_candidates_equal": pools_equal,
        "attribution_unsafe_reasons": attribution_reasons,
        "attribution_safe": not reasons
        and not attribution_reasons
        and all(
            report["index_attribution"].get("attribution_safe", False) for report in (left, right)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    collect_parser.add_argument("--output", type=Path, required=True)
    collect_parser.add_argument("--candidate-k", type=int, default=30)
    collect_parser.add_argument("--top-k", type=int, default=20)
    collect_parser.add_argument("--answer-top-k", type=int, default=10)
    collect_parser.add_argument("--with-llm", action="store_true")
    collect_parser.add_argument("--run-name", default="pilot_baseline")
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    score_parser.add_argument("--capture", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("left", type=Path)
    compare_parser.add_argument("right", type=Path)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "collect":
        collect(
            args.dataset,
            args.output,
            candidate_k=args.candidate_k,
            top_k=args.top_k,
            answer_top_k=args.answer_top_k,
            with_llm=args.with_llm,
            run_name=args.run_name,
        )
    elif args.command == "score":
        score(args.dataset, args.capture, args.output)
    else:
        write_json(args.output, compare(read_json(args.left), read_json(args.right)))
    print(args.output)


if __name__ == "__main__":
    main()
