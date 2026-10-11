"""Collect and score reviewable development trials without changing Golden v1."""

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
from history_agent.evaluation.pilot_answers import (
    AnswerReviews,
    aggregate_answers,
    evaluate_answer,
    validate_reviews,
)
from history_agent.evaluation.pilot_comparison import compare
from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit
from history_agent.evaluation.pilot_models import PilotDataset, RankingPool, case_definition
from history_agent.evaluation.pilot_process import summarize_process
from history_agent.evaluation.pilot_process_reviews import evaluate_process_reviews
from history_agent.evaluation.pilot_reporting import markdown_report
from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime
from history_agent.evaluation.pilot_workflow import (
    prepare_reviews,
    protect_inputs,
    validate_capture_binding,
)
from history_agent.extraction.report import load_page_records
from history_agent.processing.chunks import effective_pages
from history_agent.retrieval.hybrid import search_hybrid_index

VERSION = "reviewable-pilot-v3"
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
    protect_inputs([output, output.with_suffix(".partial.json")], [dataset_path])
    if output.exists() or output.with_suffix(".partial.json").exists():
        raise FileExistsError("capture output already exists; choose a new run directory")
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
    ranking_pool: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = evaluate_stage(
        case, hits, file_hashes, k_values, label_mode=mode, ranking_pool=ranking_pool
    )
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
            "pool_fingerprints": {
                case_id: metric.get("pool_fingerprint") for case_id, metric in valid
            }
            if ".pool_ndcg@" in key
            else None,
        }
    return result


def score(
    dataset_path: Path,
    capture_path: Path,
    output: Path,
    k_values: tuple[int, ...] = DEFAULT_K,
    *,
    ranking_pools_path: Path | None = None,
    assessments_path: Path | None = None,
    process_reviews_path: Path | None = None,
    protocols_path: Path | None = None,
) -> dict[str, Any]:
    if not k_values or any(type(k) is not int or k < 1 for k in k_values):
        raise ValueError("K values must be positive integers")
    k_values = tuple(sorted(set(k_values)))
    protect_inputs(
        [output, output.with_suffix(".md"), output.with_suffix(".summary.json")],
        [
            dataset_path,
            capture_path,
            ranking_pools_path,
            assessments_path,
            process_reviews_path,
            protocols_path,
        ],
    )
    dataset = PilotDataset.model_validate(read_json(dataset_path))
    capture = read_json(capture_path)
    case_definitions = [case.model_dump(mode="json") for case in dataset.cases]
    captured = validate_capture_binding(case_definitions, capture)
    process_review_payload = read_json(process_reviews_path) if process_reviews_path else None
    understanding = evaluate_process_reviews(
        process_review_payload,
        case_definitions,
        capture,
        digest(dataset.model_dump(mode="json")),
        protocol_path=protocols_path,
    )
    pools = {}
    if ranking_pools_path is not None:
        pool_payload = read_json(ranking_pools_path)
        if set(pool_payload) != {"schema_version", "pools"} or pool_payload["schema_version"] != 1:
            raise ValueError("invalid ranking pool collection")
        for payload in pool_payload["pools"]:
            pool = RankingPool.model_validate(payload)
            if pool.case_id in pools:
                raise ValueError("duplicate ranking pool for case")
            if pool.sha256 != pool.content_sha256():
                raise ValueError("ranking pool seal mismatch")
            pools[pool.case_id] = pool.model_dump(mode="json")
    assessment = (
        AnswerReviews.model_validate(read_json(assessments_path)) if assessments_path else None
    )
    reviews = (
        validate_reviews(assessment, capture, [c.model_dump(mode="json") for c in dataset.cases])
        if assessment
        else {}
    )
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
                item[mode] = stage_metrics(
                    case, source["hits"], file_hashes, k_values, mode, pools.get(model.id)
                )
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
                item[mode] = stage_metrics(
                    case, source["hits"], file_hashes, k_values, mode, pools.get(model.id)
                )
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
                    mode: evaluate_answer(case, reviews.get(model.id), mode=mode)
                    for mode in ("provisional", "approved")
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
        "answer_rubric_version": assessment.rubric_version if assessment else None,
        "answer_reviews_sha256": digest(assessment.model_dump(mode="json")) if assessment else None,
        "process_reviews_sha256": digest(process_review_payload)
        if process_review_payload
        else None,
        "protocol_file_sha256": hashlib.sha256(protocols_path.read_bytes()).hexdigest()
        if protocols_path
        else None,
        "query_understanding": understanding,
        "process_summary": summarize_process(case_definitions, capture),
        "k_values": list(k_values),
        "cases": results,
        "provisional_aggregate": _aggregate(results, "provisional"),
        "approved_aggregate": _aggregate(results, "approved"),
        "provisional_answer_aggregate": aggregate_answers(results, "provisional"),
        "approved_answer_aggregate": aggregate_answers(results, "approved"),
    }
    write_json(output, result)
    write_json(output.with_suffix(".summary.json"), compact_report(result))
    output.with_suffix(".md").write_text(markdown_report(result), encoding="utf8")
    return result


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep versions, denominators and per-case outcomes without repeated hit diagnostics."""
    result = {key: value for key, value in report.items() if key != "cases"}
    result["cases"] = [
        {
            key: case[key]
            for key in (
                "case_id",
                "question",
                "human_review",
                "retrieval_ms",
                "answer_ms",
                "generation_assessment",
            )
        }
        for case in report["cases"]
    ]
    return result


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
    score_parser.add_argument("--ranking-pools", type=Path)
    score_parser.add_argument("--assessments", type=Path)
    score_parser.add_argument("--process-reviews", type=Path)
    score_parser.add_argument("--protocols", type=Path)
    score_parser.add_argument("--k-values", type=int, nargs="+", default=DEFAULT_K)
    review_parser = sub.add_parser("prepare-reviews")
    review_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    review_parser.add_argument("--capture", type=Path, required=True)
    review_parser.add_argument("--protocols", type=Path)
    review_parser.add_argument("--output-dir", type=Path, required=True)
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
        score(
            args.dataset,
            args.capture,
            args.output,
            tuple(args.k_values),
            ranking_pools_path=args.ranking_pools,
            assessments_path=args.assessments,
            process_reviews_path=args.process_reviews,
            protocols_path=args.protocols,
        )
    elif args.command == "prepare-reviews":
        prepare_reviews(args.dataset, args.capture, args.output_dir, protocol_path=args.protocols)
        print(args.output_dir)
        return
    else:
        protect_inputs([args.output], [args.left, args.right])
        write_json(args.output, compare(read_json(args.left), read_json(args.right)))
    print(args.output)


if __name__ == "__main__":
    main()
