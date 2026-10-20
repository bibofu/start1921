"""Collect and score reviewable development trials without changing Golden v1."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from history_agent.answering.models import QuestionRequest
from history_agent.answering.service import PROMPT_VERSION, answer_question
from history_agent.config import Settings, get_settings
from history_agent.db import Database
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
from history_agent.evaluation.pilot_calibration import (
    build_calibration_packet,
    validate_review_decisions,
)
from history_agent.evaluation.pilot_comparison import compare
from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit
from history_agent.evaluation.pilot_models import (
    PilotAnchor,
    PilotDataset,
    RankingPool,
    case_definition,
)
from history_agent.evaluation.pilot_process import summarize_process
from history_agent.evaluation.pilot_process_reviews import evaluate_process_reviews
from history_agent.evaluation.pilot_protocols import capture_contract, load_inputs
from history_agent.evaluation.pilot_reporting import markdown_report
from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime
from history_agent.evaluation.pilot_specialist import evaluate_specialist_reviews
from history_agent.evaluation.pilot_variants import (
    list_control_variants,
    project_control_capture,
    validate_protocol_capture,
)
from history_agent.evaluation.pilot_workflow import (
    prepare_reviews,
    protect_inputs,
    validate_capture_binding,
)
from history_agent.extraction.report import load_page_records
from history_agent.processing.chunks import effective_pages
from history_agent.retrieval.hybrid import search_hybrid_index

VERSION = "reviewable-pilot-v5"
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
    database = Database(settings.database_target)
    if database.path is not None and not database.path.is_file():
        raise FileNotFoundError(database.path)
    with database.connect() as connection:
        if settings.database_backend == "postgresql":
            connection.execute("SET TRANSACTION READ ONLY")
        else:
            connection.execute("PRAGMA query_only = ON")
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
        anchor_sets = [(group.id, group.alternatives) for group in case.evidence_groups]
        basis = case.refusal_basis or {}
        audit = basis.get("local_search_audit")
        if audit:
            records = audit.get("documents", [])
            if len(records) != len(hashes) or {r["document_id"] for r in records} != set(hashes):
                raise ValueError(f"refusal search audit corpus changed: {case.id}")
            for record in records:
                doc_id = record["document_id"]
                if (
                    record["sha256"] != hashes[doc_id]
                    or record["actual_pdf_sha256"] != hashes[doc_id]
                ):
                    raise ValueError(f"refusal search audit PDF changed: {case.id}/{doc_id}")
                for directory, field in (
                    (settings.pages_dir, "pages_cache_sha256"),
                    (settings.ocr_dir, "ocr_cache_sha256"),
                ):
                    path = directory / f"{doc_id}.jsonl"
                    actual = (
                        hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                    )
                    if record.get(field) != actual:
                        raise ValueError(f"refusal search audit text changed: {case.id}/{doc_id}")
        anchor_sets.append(
            (
                "refusal_meta",
                [PilotAnchor.model_validate(anchor) for anchor in basis.get("meta_evidence", [])],
            )
        )
        project_basis = basis.get("project_basis")
        if project_basis:
            path = (settings.project_root / project_basis["path"]).resolve()
            if not path.is_relative_to(settings.project_root.resolve()):
                raise ValueError("project refusal basis must be inside the repository")
            if hashlib.sha256(path.read_bytes()).hexdigest() != project_basis["file_sha256"]:
                raise ValueError(f"project refusal basis changed: {case.id}")
            if any(
                rule["quote"] not in path.read_text(encoding="utf8")
                for rule in project_basis["rules"]
            ):
                raise ValueError(f"project refusal basis quote changed: {case.id}")
        for group_id, anchors in anchor_sets:
            for anchor in anchors:
                if hashes.get(anchor.document_id) != anchor.file_sha256:
                    raise ValueError(f"stale or unavailable source: {case.id}/{group_id}")
                if anchor.document_id not in cache:
                    base = load_page_records(settings.pages_dir / f"{anchor.document_id}.jsonl")
                    ocr_path = settings.ocr_dir / f"{anchor.document_id}.jsonl"
                    ocr = load_page_records(ocr_path) if ocr_path.exists() else {}
                    cache[anchor.document_id] = effective_pages(base, ocr)
                page = cache[anchor.document_id].get(anchor.pdf_page)
                if page is not None and page.file_sha256 != anchor.file_sha256:
                    raise ValueError(f"stale page extraction: {case.id}/{group_id}")
                if page is None or re.sub(r"\s+", "", anchor.quote) not in re.sub(
                    r"\s+",
                    "",
                    page.normalized_text,
                ):
                    raise ValueError(f"evidence quote not on source page: {case.id}/{group_id}")


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
    protocols_path: Path | None = None,
) -> dict[str, Any]:
    protect_inputs([output, output.with_suffix(".partial.json")], [dataset_path, protocols_path])
    if output.exists() or output.with_suffix(".partial.json").exists():
        raise FileExistsError("capture output already exists; choose a new run directory")
    settings = settings or get_settings()
    inputs = load_inputs(dataset_path, protocols_path)
    dataset = inputs.dataset
    if not 1 <= top_k <= candidate_k <= 100 or not 1 <= answer_top_k <= 12:
        raise ValueError("require 1 <= top_k <= candidate_k <= 100; answer_top_k in 1..12")
    corpus = corpus_snapshot(settings)
    validate_anchors(dataset, settings, corpus)
    file_hashes = {item["document_id"]: item["sha256"] for item in corpus["documents"]}
    reports = _load_index_metadata(settings)
    initial_source_sha256 = source_fingerprint(settings.project_root)
    results: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    actual_branches: set[str] = set()
    degraded_cases: dict[str, list[str]] = {}
    candidate_fingerprints: dict[str, dict[str, str]] = {}
    for case in dataset.cases:
        for variant_index, variant in enumerate(inputs.variants[case.id]):
            print(f"collect {case.id}/{variant['id']}", flush=True)
            started = perf_counter()
            response = search_hybrid_index(
                keyword_index_path=settings.keyword_index_target,
                vector_index_path=settings.vector_index_target,
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
            branch_fingerprints = {
                item["stage"]: digest(
                    [evidence_unit(hit, file_hashes)["unit_id"] for hit in item["hits"]]
                )
                for item in trace
                if item["stage"] in {"keyword_candidates", "vector_candidates"}
            }
            for branch in ("keyword", "vector"):
                if any(
                    item["stage"] == f"{branch}_candidates" and item["status"] == "ok"
                    for item in trace
                ):
                    actual_branches.add(branch)
            if variant_index == 0:
                candidate_fingerprints[case.id] = branch_fingerprints
            request = QuestionRequest(
                question=variant["question"], history=variant["history"], top_k=answer_top_k
            )
            answer_settings = (
                settings if with_llm else settings.model_copy(update={"llm_api_key": None})
            )
            runtime = RecordedLLMRuntime(settings.llm_max_concurrency)
            started = perf_counter()
            try:
                answer = answer_question(
                    answer_settings,
                    request,
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
            target = results if variant_index == 0 else controls
            target.append(
                {
                    "case_id": case.id,
                    "input_variant_id": variant["id"],
                    "request": request.model_dump(mode="json"),
                    "input_sha256": digest(
                        {"question": variant["question"], "history": variant["history"]}
                    ),
                    "component_candidate_fingerprints": branch_fingerprints,
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
            write_json(
                output.with_suffix(".partial.json"),
                {"completed_cases": results, "control_cases": controls},
            )
    attribution = _index_attribution(reports["reports"], sorted(actual_branches))
    final_source_sha256 = source_fingerprint(settings.project_root)
    if initial_source_sha256 != final_source_sha256:
        attribution["attribution_safe"] = False
        attribution.setdefault("attribution_unsafe_reasons", []).append(
            "source files changed during collection"
        )
    if degraded_cases:
        attribution["attribution_safe"] = False
        attribution["attribution_unsafe_reasons"].append(
            "one or more cases used degraded retrieval"
        )
    result = {
        "schema_version": 2 if inputs.is_protocol_release else 1,
        "evaluator_version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": run_name,
        "dataset_sha256": inputs.dataset_sha256,
        "git": _git_metadata(settings.project_root),
        "source_sha256": initial_source_sha256,
        "source_sha256_after_collection": final_source_sha256,
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
    if inputs.is_protocol_release:
        result["execution_contract"] = capture_contract(inputs)
        result["control_cases"] = controls
        validate_protocol_capture(inputs, result)
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
    reviews_dir: Path | None = None,
) -> dict[str, Any]:
    if not k_values or any(type(k) is not int or k < 1 for k in k_values):
        raise ValueError("K values must be positive integers")
    k_values = tuple(sorted(set(k_values)))
    if reviews_dir and (assessments_path or process_reviews_path):
        raise ValueError("use reviews-dir or individual review paths, not both")
    if reviews_dir:
        assessments_path = reviews_dir / "answer_reviews.json"
        process_reviews_path = reviews_dir / "process_reviews.json"
    inputs = load_inputs(dataset_path, protocols_path)
    capture = read_json(capture_path)
    validate_protocol_capture(inputs, capture)
    calibration = build_calibration_packet(
        [case.model_dump(mode="json") for case in inputs.dataset.cases],
        inputs.protocols,
        dataset_sha256=inputs.dataset_sha256,
    )
    calibration_sha256 = digest(calibration)
    calibration_path = reviews_dir / "calibration.json" if reviews_dir else None
    calibrated_directory = bool(calibration_path and calibration_path.exists())
    if (
        calibration_path is not None
        and calibrated_directory
        and read_json(calibration_path) != calibration
    ):
        raise ValueError("review calibration changed; prepare a new review workspace")
    controls = {
        name: project_control_capture(capture, name) for name in list_control_variants(capture)
    }
    review_paths = [assessments_path, process_reviews_path]
    if reviews_dir:
        review_paths += [
            reviews_dir / "controls" / name / filename
            for name in controls
            for filename in ("answer_reviews.json", "process_reviews.json")
        ]
    specialist_path = (
        reviews_dir / "specialist_reviews.json"
        if reviews_dir and inputs.is_protocol_release
        else None
    )
    protect_inputs(
        [output, output.with_suffix(".md"), output.with_suffix(".summary.json")],
        [
            dataset_path,
            capture_path,
            ranking_pools_path,
            protocols_path,
            specialist_path,
            calibration_path,
            *review_paths,
        ],
    )
    result = _score_capture(
        inputs.dataset,
        capture,
        inputs.dataset_sha256,
        k_values,
        ranking_pools_path=ranking_pools_path,
        assessments_path=assessments_path,
        process_reviews_path=process_reviews_path,
        protocols_path=protocols_path,
        expected_calibration_sha256=calibration_sha256,
        calibration_protocols=inputs.protocols,
        require_calibration=calibrated_directory,
    )
    control_reports = {}
    for name, control in controls.items():
        ids = {case["case_id"] for case in control["cases"]}
        subset = inputs.dataset.model_copy(
            update={"cases": [case for case in inputs.dataset.cases if case.id in ids]}
        )
        directory = reviews_dir / "controls" / name if reviews_dir else None
        control_reports[name] = _score_capture(
            subset,
            control,
            inputs.dataset_sha256,
            k_values,
            ranking_pools_path=ranking_pools_path,
            assessments_path=directory / "answer_reviews.json" if directory else None,
            process_reviews_path=directory / "process_reviews.json" if directory else None,
            protocols_path=protocols_path,
            expected_calibration_sha256=calibration_sha256,
            calibration_protocols=inputs.protocols,
            require_calibration=calibrated_directory,
        )
    if inputs.is_protocol_release:
        assert inputs.protocols is not None
        result["control_reports"] = control_reports
        result["specialist_assessment"] = evaluate_specialist_reviews(
            read_json(specialist_path) if specialist_path else None,
            [c.model_dump(mode="json") for c in inputs.dataset.cases],
            inputs.protocols,
            capture,
            result,
            control_reports,
        )
        result["execution_accounting"] = execution_accounting(result, control_reports)
    write_json(output, result)
    write_json(output.with_suffix(".summary.json"), compact_report(result))
    output.with_suffix(".md").write_text(markdown_report(result), encoding="utf8")
    return result


def execution_accounting(main: dict[str, Any], controls: dict[str, Any]) -> dict[str, Any]:
    """Bill every execution once while keeping paired controls out of quality denominators."""
    rows = []
    for report in [main, *controls.values()]:
        variants = {case["case_id"]: case["input_variant_id"] for case in report["cases"]}
        for row in report["process_summary"]["per_case"]:
            rows.append(
                {
                    "case_id": row["case_id"],
                    "input_variant_id": variants[row["case_id"]],
                    "cost": row["cost"],
                    "http": row["http"],
                    "latency": row["latency"],
                }
            )
    tokens = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        metrics = [row["cost"]["tokens"][field] for row in rows]
        complete = all(m["value"] is not None for m in metrics)
        known = [m["known_sum"] for m in metrics if m["known_sum"] is not None]
        tokens[field] = {
            "value": sum(m["value"] for m in metrics) if complete else None,
            "known_sum": sum(known) if known else None,
            "reason": None if complete else "no_calls_or_incomplete_usage",
        }
    return {
        "independent_case_count": len(main["cases"]),
        "execution_count": len(rows),
        "http_calls": sum(row["http"]["calls"] for row in rows)
        if all(row["http"]["calls"] is not None for row in rows)
        else None,
        "tokens": tokens,
        "executions": rows,
        "note": "Quality aggregates contain primary variants only; controls billed here once.",
    }


def _score_capture(
    dataset: PilotDataset,
    capture: dict[str, Any],
    dataset_sha256: str,
    k_values: tuple[int, ...],
    *,
    ranking_pools_path: Path | None = None,
    assessments_path: Path | None = None,
    process_reviews_path: Path | None = None,
    protocols_path: Path | None = None,
    expected_calibration_sha256: str | None = None,
    calibration_protocols: dict[str, Any] | None = None,
    require_calibration: bool = False,
) -> dict[str, Any]:
    case_definitions = [case.model_dump(mode="json") for case in dataset.cases]
    captured = validate_capture_binding(case_definitions, capture)
    process_review_payload = read_json(process_reviews_path) if process_reviews_path else None
    understanding = evaluate_process_reviews(
        process_review_payload,
        case_definitions,
        capture,
        dataset_sha256,
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
    if require_calibration and (assessment is None or assessment.calibration_sha256 is None):
        raise ValueError("calibrated review directory requires bound answer reviews on every arm")
    if assessment and assessment.calibration_sha256 is not None:
        if assessment.calibration_sha256 != expected_calibration_sha256:
            raise ValueError(
                "answer review calibration differs from the bound dataset and protocol"
            )
        validate_review_decisions(assessment, capture, case_definitions, calibration_protocols)
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
                "input_variant_id": raw.get("input_variant_id", "single_turn"),
                "input_sha256": raw.get("input_sha256"),
                "request": raw.get("request"),
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
        **(
            {"execution_contract": capture["execution_contract"]}
            if capture.get("execution_contract") is not None
            else {}
        ),
        **(
            {"control_variant_id": capture["control_variant_id"]}
            if capture.get("control_variant_id") is not None
            else {}
        ),
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": capture["run_name"],
        "capture_sha256": digest(capture),
        "dataset_sha256": dataset_sha256,
        "corpus_sha256": capture["corpus"]["sha256"],
        "git": capture["git"],
        "source_sha256": capture.get("source_sha256"),
        "source_sha256_after_collection": capture.get("source_sha256_after_collection"),
        "index_metadata": capture["index_metadata"],
        "degraded_cases": capture.get("degraded_cases", {}),
        "config": capture["config"],
        "index_attribution": capture["index_attribution"],
        "component_candidate_fingerprints": capture.get("component_candidate_fingerprints"),
        "labels": "Provisional agent labels are diagnostic only, not approved Golden results.",
        "answer_rubric_version": assessment.rubric_version if assessment else None,
        "answer_calibration_sha256": assessment.calibration_sha256 if assessment else None,
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
    return result


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep versions, denominators and per-case outcomes without repeated hit diagnostics."""
    result = {key: value for key, value in report.items() if key != "cases"}
    result["cases"] = [
        {k: v for k, v in case.items() if k not in {"stages", "answer"}} for case in report["cases"]
    ]
    if "control_reports" in result:
        result["control_reports"] = {
            name: compact_report(control) for name, control in result["control_reports"].items()
        }
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
    collect_parser.add_argument("--protocols", type=Path)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    score_parser.add_argument("--capture", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    score_parser.add_argument("--ranking-pools", type=Path)
    score_parser.add_argument("--assessments", type=Path)
    score_parser.add_argument("--process-reviews", type=Path)
    score_parser.add_argument("--protocols", type=Path)
    score_parser.add_argument("--reviews-dir", type=Path)
    score_parser.add_argument("--k-values", type=int, nargs="+", default=DEFAULT_K)
    review_parser = sub.add_parser("prepare-reviews")
    review_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    review_parser.add_argument("--capture", type=Path, required=True)
    review_parser.add_argument("--protocols", type=Path)
    review_parser.add_argument("--output-dir", type=Path, required=True)
    import_parser = sub.add_parser("import-reviews")
    import_parser.add_argument("--dataset", type=Path, default=Path(DEFAULT_DATASET))
    import_parser.add_argument("--capture", type=Path, required=True)
    import_parser.add_argument("--protocols", type=Path)
    import_parser.add_argument("--bundle", type=Path, required=True)
    import_parser.add_argument("--output-dir", type=Path, required=True)
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
            protocols_path=args.protocols,
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
            reviews_dir=args.reviews_dir,
        )
    elif args.command == "prepare-reviews":
        prepare_reviews(args.dataset, args.capture, args.output_dir, protocol_path=args.protocols)
        print(args.output_dir)
        return
    elif args.command == "import-reviews":
        from history_agent.evaluation.pilot_review_bundle import import_reviews

        import_reviews(
            args.dataset, args.capture, args.bundle, args.output_dir, protocol_path=args.protocols
        )
        print(args.output_dir)
        return
    else:
        protect_inputs([args.output], [args.left, args.right])
        write_json(args.output, compare(read_json(args.left), read_json(args.right)))
    print(args.output)


if __name__ == "__main__":
    main()
