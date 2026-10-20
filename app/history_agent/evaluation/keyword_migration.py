"""Frozen-oracle evaluation for a keyword storage migration, separate from Golden."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
import sqlite3
import subprocess
import sys
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from history_agent.config import Settings, get_settings
from history_agent.db import Database
from history_agent.errors import RetrievalError
from history_agent.evaluation.pilot_metrics import evaluate_stage
from history_agent.evaluation.pilot_protocols import load_inputs
from history_agent.retrieval.models import RetrievalPlan

PROTOCOL = Path("evals/keyword_migration/protocol_v1.json")
ORACLE_IDENTITY = Path("evals/keyword_migration/oracle_identity_v1.json")
DATASET = Path("evals/golden/development_annotations_v5.json")
CASE_PROTOCOLS = Path("evals/golden/development_protocols_v5.json")
SYNTHETIC = Path("evals/keyword_migration/synthetic_v1.json")
VOLATILE_FIELDS = {"elapsed_ms", "retrieval_ms", "answer_ms", "latency_ms"}


def file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")
    ).hexdigest()


def corpus_snapshot(settings: Settings) -> dict[str, Any]:
    """Verify actual corpus files without importing the Agent implementation."""
    with Database(settings.database_target).connect() as connection:
        connection.execute(
            "SET TRANSACTION READ ONLY"
            if settings.database_backend == "postgresql"
            else "PRAGMA query_only = ON"
        )
        rows = connection.execute(
            "SELECT d.document_id,d.title,f.sha256,f.relative_path,f.page_count "
            "FROM documents d JOIN document_files f ON f.document_id=d.document_id "
            "WHERE d.enabled=1 AND f.is_current=1 AND f.is_present=1 ORDER BY d.document_id"
        ).fetchall()
    documents = [dict(row) for row in rows]
    for item in documents:
        path = (settings.project_root / item["relative_path"]).resolve()
        if not path.is_relative_to(settings.docs_dir.resolve()):
            raise ValueError("Corpus path is outside docs directory.")
        if file_sha(path) != item["sha256"]:
            raise ValueError(f"PDF changed since corpus scan: {item['document_id']}")
    return {"documents": documents, "sha256": digest(documents)}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load_contract(root: Path) -> dict[str, Any]:
    contract: dict[str, Any] = read_json(root / PROTOCOL)
    for artifact in contract["annotation_inputs"]:
        if file_sha(root / artifact["path"]) != artifact["sha256"]:
            raise ValueError(f"Frozen annotation changed: {artifact['path']}")
    frozen = contract["frozen_artifacts"]
    oracle = read_json(root / ORACLE_IDENTITY)
    if (
        oracle["source"]["artifact_sha256"] != frozen["sqlite_index_sha256"]
        or oracle["snapshot"]["path"] != frozen["sqlite_index"]
    ):
        raise ValueError("Oracle identity addendum is not bound to the frozen protocol.")
    for path_key, hash_key in (
        ("sqlite_index", "sqlite_index_sha256"),
        ("legacy_keyword_module", "legacy_keyword_module_sha256"),
    ):
        expected = (
            oracle["snapshot"]["artifact_sha256"]
            if path_key == "sqlite_index"
            else frozen[hash_key]
        )
        if file_sha(root / frozen[path_key]) != expected:
            raise ValueError(f"Frozen oracle artifact changed: {path_key}")
    inventory = read_json(root / frozen["inventory"])
    for relative, expected in inventory["files"].items():
        portable = relative.replace("\\", "/")
        if (
            portable.startswith("data/processed/chunks/")
            or portable == "config/person_aliases.json"
        ) and file_sha(root / portable) != expected:
            raise ValueError(f"Frozen corpus/query artifact changed: {portable}")
    return contract


def legacy_module(root: Path, contract: dict[str, Any]) -> Any:
    path = root / contract["frozen_artifacts"]["legacy_keyword_module"]
    spec = importlib.util.spec_from_file_location("_frozen_keyword_migration_oracle", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load frozen keyword oracle.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_workload(
    inputs: Any, document_ids: list[str], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build compatibility inputs; document filters do not alter Golden questions."""
    workload = []
    for case in inputs.dataset.cases:
        for variant in inputs.variants[case.id]:
            base = {
                "case_id": case.id,
                "variant_id": variant["id"],
                "question": variant["question"],
                "history": variant["history"],
            }
            filters: list[tuple[str, dict[str, Any]]] = [
                ("default", {}),
                ("include_out_of_scope", {"include_out_of_scope": True}),
                ("two_documents", {"document_ids": document_ids[:2]}),
                ("missing_document", {"document_ids": ["__missing_migration_document__"]}),
            ]
            filters.extend(
                (f"document_{index:02d}", {"document_ids": [document_id]})
                for index, document_id in enumerate(document_ids)
            )
            for name, options in filters:
                workload.append(
                    {
                        **base,
                        "id": f"{case.id}/{variant['id']}/{name}",
                        "filter_id": name,
                        "options": options,
                    }
                )
    for index, query in enumerate(contract["keyword_compatibility"]["additional_queries"]):
        workload.append(
            {
                "id": f"compatibility/query_{index:02d}",
                "case_id": None,
                "variant_id": None,
                "question": query,
                "history": [],
                "filter_id": "default",
                "options": {},
            }
        )
    for index, section in enumerate(("1935", "%", "_", "\\")):
        workload.append(
            {
                "id": f"compatibility/section_{index:02d}",
                "case_id": None,
                "variant_id": None,
                "question": "中国共产党",
                "history": [],
                "filter_id": "literal_section",
                "options": {"section_path_contains": section},
            }
        )
    for index, plan in enumerate(
        (
            {"query_intent": "general", "query_years": [1935]},
            {"query_intent": "timeline", "query_year_range": [1921, 1949]},
            {"query_intent": "intersection", "query_people": ["毛泽东", "周恩来"]},
            {"query_intent": "viewpoint", "query_people": ["毛泽东"]},
        )
    ):
        workload.append(
            {
                "id": f"compatibility/plan_{index:02d}",
                "case_id": None,
                "variant_id": None,
                "question": "中国共产党",
                "history": [],
                "filter_id": "explicit_plan",
                "options": {"plan": plan},
            }
        )
    return workload


def hit_signature(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": hit["chunk_id"],
        "score": hit["score"],
        "fields_sha256": digest({key: value for key, value in hit.items() if key != "rank"}),
    }


def public_response(response: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = response.model_dump(mode="json")
    hits = payload.pop("hits")
    payload.pop("trace", None)
    return payload, hits


def observed_response(
    search: Callable[..., Any], arguments: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        return public_response(search(**arguments))
    except RetrievalError as exc:
        return {"error": {"type": type(exc).__name__, "message": str(exc)}}, []


def strict_aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Independent main cases only; never convert unavailable labels into zero."""
    names = sorted({name for case in cases for name in case["metrics"]})
    result = {}
    for name in names:
        valid = [case for case in cases if case["metrics"][name]["evaluable"]]
        result[name] = {
            "value": (
                sum(case["metrics"][name]["value"] for case in valid) / len(valid)
                if valid
                else None
            ),
            "aggregation": "macro_over_evaluable_main_cases",
            "evaluable_case_ids": [case["case_id"] for case in valid],
            "evaluable_cases": len(valid),
            "total_cases": len(cases),
            "per_case_denominators": {
                case["case_id"]: case["metrics"][name]["denominator"] for case in cases
            },
            "unevaluable_reasons": {
                case["case_id"]: case["metrics"][name]["reason"]
                for case in cases
                if not case["metrics"][name]["evaluable"]
            },
        }
    return result


def capture_keyword(
    output: Path,
    *,
    backend: str,
    target: Path | str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    checkpoint = output.with_suffix(".checkpoint.jsonl")
    if output.exists() or checkpoint.exists():
        raise FileExistsError("Use a new output path.")
    settings = settings or get_settings()
    root = settings.project_root
    contract = load_contract(root)
    inputs = load_inputs(root / DATASET, root / CASE_PROTOCOLS)
    corpus = corpus_snapshot(settings)
    file_hashes = {item["document_id"]: item["sha256"] for item in corpus["documents"]}
    workload = build_workload(inputs, sorted(file_hashes), contract)
    if backend == "legacy":
        search: Callable[..., Any] = legacy_module(root, contract).search_keyword_index
        target = root / contract["frozen_artifacts"]["sqlite_index"]
        engine_paths = [root / contract["frozen_artifacts"]["legacy_keyword_module"]]
        index_identity = read_json(root / ORACLE_IDENTITY)["snapshot"]
    elif backend == "candidate":
        from history_agent.retrieval.keyword import (
            load_keyword_index_metadata,
            search_keyword_index,
        )

        search = search_keyword_index
        if target is None:
            raise ValueError("Candidate capture requires an explicit target.")
        engine_paths = [
            root / f"app/history_agent/retrieval/{name}.py"
            for name in ("keyword", "keyword_postgres", "keyword_legacy")
        ]
        index_identity = load_keyword_index_metadata(str(target))
    else:
        raise ValueError("backend must be legacy or candidate")
    k_values = tuple(contract["keyword_compatibility"]["k_values"])
    exhaustive_k = contract["keyword_compatibility"]["exhaustive_k"]
    by_case = {case.id: case.model_dump(mode="json") for case in inputs.dataset.cases}
    observed_main: set[str] = set()
    strict_cases = []
    results = []
    engine_identity = {path.name: file_sha(path) for path in engine_paths}
    started = perf_counter()
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("x", encoding="utf8") as stream:
        stream.write(
            json.dumps(
                {
                    "backend": backend,
                    "protocol_sha256": file_sha(root / PROTOCOL),
                    "oracle_identity_sha256": file_sha(root / ORACLE_IDENTITY),
                    "dataset_sha256": inputs.dataset_sha256,
                }
            )
            + "\n"
        )
    for number, item in enumerate(workload, 1):
        options = dict(item["options"])
        if "plan" in options:
            options["plan"] = RetrievalPlan.model_validate(options["plan"])
        call = {
            "index_path": target,
            "aliases_path": settings.person_aliases_path,
            "query": item["question"],
            **options,
        }
        begin = perf_counter()
        metadata, hits = observed_response(search, {**call, "top_k": exhaustive_k})
        all_ms = (perf_counter() - begin) * 1000
        signatures = [hit_signature(hit) for hit in hits]
        per_k = {}
        for k in k_values:
            begin = perf_counter()
            small_metadata, small_hits = observed_response(search, {**call, "top_k": k})
            small_signatures = [hit_signature(hit) for hit in small_hits]
            per_k[str(k)] = {
                "elapsed_ms": (perf_counter() - begin) * 1000,
                "hits": small_signatures,
                "metadata": small_metadata,
                "matches_exhaustive_prefix": small_signatures == signatures[:k],
            }
        metric_report = None
        case_id = item["case_id"]
        if case_id and item["filter_id"] == "default":
            if "error" in metadata:
                raise ValueError(f"Unexpected default Golden retrieval error: {case_id}")
            metric_report = evaluate_stage(
                by_case[case_id],
                hits[: max(k_values)],
                file_hashes,
                k_values,
                label_mode="approved",
            )
            # The lower-bound diagnostic is not an exact MRR quality metric.
            metric_report["metrics"] = {
                name: metric
                for name, metric in metric_report["metrics"].items()
                if not name.startswith("annotated_mrr_lower_bound")
            }
            metric_report.pop("units", None)
            if case_id not in observed_main:
                strict_cases.append(metric_report)
                observed_main.add(case_id)
        results.append(
            {
                "input": item,
                "input_sha256": digest(item),
                "metadata": metadata,
                "hits": signatures,
                "all_results_ms": all_ms,
                "at_k": per_k,
                "human_metrics": metric_report,
            }
        )
        with checkpoint.open("a", encoding="utf8") as stream:
            stream.write(json.dumps(results[-1], ensure_ascii=False) + "\n")
        if number % 50 == 0 or number == len(workload):
            print(f"keyword {backend}: {number}/{len(workload)}", flush=True)
    result = {
        "schema_version": 1,
        "scope": "storage_compatibility_and_strict_human_metric_availability",
        "created_at": datetime.now(UTC).isoformat(),
        "backend": backend,
        "engine_sha256_before": engine_identity,
        "engine_sha256_after": {path.name: file_sha(path) for path in engine_paths},
        "index_identity": index_identity,
        "protocol_sha256": file_sha(root / PROTOCOL),
        "oracle_identity_sha256": file_sha(root / ORACLE_IDENTITY),
        "dataset_sha256": inputs.dataset_sha256,
        "corpus_sha256": corpus["sha256"],
        "file_hashes": file_hashes,
        "aliases_sha256": file_sha(settings.person_aliases_path),
        "baseline_inventory_sha256": file_sha(root / contract["frozen_artifacts"]["inventory"]),
        "k_values": k_values,
        "exhaustive_k": exhaustive_k,
        "independent_cases": len(inputs.dataset.cases),
        "execution_inputs": sum(map(len, inputs.variants.values())),
        "workload_count": len(workload),
        "elapsed_ms": (perf_counter() - started) * 1000,
        "sqlite_version": sqlite3.sqlite_version,
        "python_version": sys.version,
        "historical_quality_limit": (
            "No human candidate relevance judgments; unavailable Precision/MRR/nDCG remain null. "
            "Strict empty-result zeros follow the existing metric definition."
        ),
        "strict_human_aggregate": strict_aggregate(strict_cases),
        "queries": results,
    }
    write_new(output, result)
    return result


def compare_keyword(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    identity_keys = (
        "protocol_sha256",
        "oracle_identity_sha256",
        "dataset_sha256",
        "corpus_sha256",
        "aliases_sha256",
        "baseline_inventory_sha256",
        "k_values",
        "exhaustive_k",
        "workload_count",
    )
    for key in identity_keys:
        if left.get(key) != right.get(key):
            raise ValueError(f"Incompatible comparison identity: {key}")
    for capture in (left, right):
        if capture.get("engine_sha256_before") != capture.get("engine_sha256_after"):
            raise ValueError("Keyword engine source changed during capture.")
    right_queries = {query["input"]["id"]: query for query in right["queries"]}
    if len(right_queries) != len(right["queries"]):
        raise ValueError("Duplicate candidate workload IDs.")
    comparisons = []
    for before in left["queries"]:
        query_id = before["input"]["id"]
        after = right_queries.pop(query_id, None)
        if after is None or before["input_sha256"] != after["input_sha256"]:
            raise ValueError("Missing or changed compatibility input.")
        old_hits = before["hits"]
        new_hits = after["hits"]
        old_map = {hit["chunk_id"]: hit for hit in old_hits}
        new_map = {hit["chunk_id"]: hit for hit in new_hits}
        changed = sorted(
            chunk_id
            for chunk_id in old_map.keys() & new_map.keys()
            if old_map[chunk_id] != new_map[chunk_id]
        )
        old_ids = [hit["chunk_id"] for hit in old_hits]
        new_ids = [hit["chunk_id"] for hit in new_hits]
        same_set = old_map.keys() == new_map.keys()
        order_equal = old_ids == new_ids
        tie_only = (
            same_set
            and not changed
            and not order_equal
            and [hit["score"] for hit in old_hits] == [hit["score"] for hit in new_hits]
        )
        k_checks = {
            k: {
                "hits_equal": before["at_k"][k]["hits"] == after["at_k"][k]["hits"],
                "metadata_equal": before["at_k"][k]["metadata"] == after["at_k"][k]["metadata"],
                "baseline_ms": before["at_k"][k]["elapsed_ms"],
                "candidate_ms": after["at_k"][k]["elapsed_ms"],
            }
            for k in before["at_k"]
        }
        comparisons.append(
            {
                "id": query_id,
                "baseline_count": len(old_hits),
                "candidate_count": len(new_hits),
                "missing_ids": sorted(old_map.keys() - new_map.keys()),
                "extra_ids": sorted(new_map.keys() - old_map.keys()),
                "changed_hit_ids": changed,
                "ordered_results_equal": order_equal,
                "tie_only_order_change": tie_only,
                "metadata_equal": before["metadata"] == after["metadata"],
                "human_metrics_equal": before["human_metrics"] == after["human_metrics"],
                "all_results_ms": {
                    "baseline": before["all_results_ms"],
                    "candidate": after["all_results_ms"],
                },
                "at_k": k_checks,
                "passed": (
                    old_hits == new_hits
                    and before["metadata"] == after["metadata"]
                    and before["human_metrics"] == after["human_metrics"]
                    and all(v["hits_equal"] and v["metadata_equal"] for v in k_checks.values())
                ),
            }
        )
    if right_queries:
        raise ValueError("Unexpected candidate workload IDs.")
    return {
        "schema_version": 1,
        "scope": "compatibility_not_golden_answer_quality",
        "protocol_sha256": left["protocol_sha256"],
        "passed": all(item["passed"] for item in comparisons),
        "workload_count": len(comparisons),
        "passed_workloads": sum(item["passed"] for item in comparisons),
        "different_workloads": [item["id"] for item in comparisons if not item["passed"]],
        "strict_human_aggregate_before": left["strict_human_aggregate"],
        "strict_human_aggregate_after": right["strict_human_aggregate"],
        "queries": comparisons,
    }


def normalize_execution(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_execution(item)
            for key, item in value.items()
            if key not in VOLATILE_FIELDS
        }
    if isinstance(value, list):
        return [normalize_execution(item) for item in value]
    return value


def capture_e2e(output: Path, *, backend: str, root: Path) -> None:
    """Run the unchanged baseline code in a child process, with no model calls."""
    contract = load_contract(root)
    if output.exists() or output.with_suffix(".partial.json").exists():
        raise FileExistsError("Use a new end-to-end output path.")
    runtime = root / "data/backups/keyword-to-postgres-20261020T061514Z/runtime"
    if backend == "legacy" and not runtime.exists():
        archive = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root.as_posix()}",
                "archive",
                "--format=zip",
                contract["baseline_commit"],
                "app",
            ],
            cwd=root,
            capture_output=True,
            check=True,
        ).stdout
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            for member in source.infolist():
                if not (runtime / member.filename).resolve().is_relative_to(runtime.resolve()):
                    raise ValueError("Unsafe archive member.")
            source.extractall(runtime)
    child = """
import importlib.util, sys
from pathlib import Path
root, output, backend, runtime, snapshot = map(Path, sys.argv[1:])
sys.path.insert(0, str((runtime if str(backend) == "legacy" else root) / "app"))
spec = importlib.util.spec_from_file_location(
    "migration_capture", root / "app/history_agent/evaluation/keyword_migration.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.capture_e2e_runtime(root, output, str(backend), runtime, snapshot)
"""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(root),
            str(output.resolve()),
            backend,
            str(runtime),
            str(root / contract["frozen_artifacts"]["sqlite_index"]),
        ],
        cwd=root,
        env=environment,
        check=True,
    )


def capture_e2e_runtime(
    root: Path, output: Path, backend: str, runtime: Path, snapshot: Path
) -> None:
    """Compatibility inputs are not asserted to be current Golden quality labels."""
    import asyncio

    from history_agent.answering.models import QuestionRequest
    from history_agent.answering.service import PROMPT_VERSION, answer_question
    from history_agent.evaluation import pilot
    from history_agent.evaluation.pilot_protocols import capture_contract
    from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime
    from history_agent.retrieval.hybrid import search_hybrid_index

    class FrozenSettings(Settings):
        @property
        def keyword_index_path(self) -> Path:
            return snapshot

    settings = (FrozenSettings if backend == "legacy" else Settings)(
        project_root=root, llm_api_key=None
    )
    inputs = load_inputs(root / DATASET, root / CASE_PROTOCOLS)
    corpus = corpus_snapshot(settings)
    validation_error = None
    try:
        pilot.validate_anchors(inputs.dataset, settings, corpus)
    except ValueError as exc:
        validation_error = str(exc)
    results: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    source_root = runtime if backend == "legacy" else root
    source_before = pilot.source_fingerprint(source_root)
    for case in inputs.dataset.cases:
        for index, variant in enumerate(inputs.variants[case.id]):
            print(f"compatibility {backend}: {case.id}/{variant['id']}", flush=True)
            begin = perf_counter()
            response = search_hybrid_index(
                keyword_index_path=(
                    snapshot if backend == "legacy" else settings.keyword_index_target
                ),
                vector_index_path=settings.vector_index_target,
                model_cache_dir=settings.model_cache_dir / "fastembed",
                aliases_path=settings.person_aliases_path,
                query=variant["question"],
                top_k=20,
                candidate_k=30,
                capture_trace=True,
            )
            retrieval_ms = (perf_counter() - begin) * 1000
            trace = [item.model_dump(mode="json") for item in response.trace or []]
            request = QuestionRequest(
                question=variant["question"], history=variant["history"], top_k=10
            )
            recorder = RecordedLLMRuntime(settings.llm_max_concurrency)
            begin = perf_counter()
            try:
                answer = answer_question(settings, request, runtime=recorder).model_dump(
                    mode="json"
                )
            finally:
                asyncio.run(recorder.aclose())
            item = {
                "case_id": case.id,
                "input_variant_id": variant["id"],
                "input_sha256": digest(
                    {"question": variant["question"], "history": variant["history"]}
                ),
                "request": request.model_dump(mode="json"),
                "retrieval": response.model_dump(mode="json"),
                "stages": trace,
                "production_stages": pilot.production_stages(recorder.retrieval_calls),
                "generation_contexts": pilot.generation_contexts(
                    recorder.calls, corpus["documents"]
                ),
                "answer": answer,
                "llm_calls": recorder.calls,
                "retrieval_ms": retrieval_ms,
                "answer_ms": (perf_counter() - begin) * 1000,
            }
            (results if index == 0 else controls).append(item)
    report = {
        "schema_version": 1,
        "scope": "deterministic_no_llm_storage_compatibility",
        "backend": backend,
        "dataset_sha256": inputs.dataset_sha256,
        "execution_contract": capture_contract(inputs),
        "corpus": corpus,
        "config": {
            "candidate_k": 30,
            "top_k": 20,
            "answer_top_k": 10,
            "with_llm": False,
            "component_query": "raw_question",
            "prompt_version": PROMPT_VERSION,
        },
        "source_sha256": source_before,
        "source_sha256_after_collection": pilot.source_fingerprint(source_root),
        "annotation_validation_error": validation_error,
        "quality_limit": (
            "This capture compares execution behavior only. Historical refusal project-file "
            "hashes may no longer match; no semantic, factual, or refusal quality is inferred."
        ),
        "cases": results,
        "control_cases": controls,
    }
    write_new(output, report)


def compare_e2e(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    for key in ("dataset_sha256", "execution_contract", "config", "corpus"):
        if left.get(key) != right.get(key):
            raise ValueError(f"End-to-end input/config identity differs: {key}")
    for capture in (left, right):
        if capture.get("source_sha256") != capture.get("source_sha256_after_collection"):
            raise ValueError("Agent source changed during capture.")
    if left["config"].get("with_llm") or right["config"].get("with_llm"):
        raise ValueError("Deterministic parity requires with_llm=false on both captures.")
    candidates = {
        (case["case_id"], case["input_variant_id"]): case
        for case in [*right["cases"], *right.get("control_cases", [])]
    }
    reports = []
    for before in [*left["cases"], *left.get("control_cases", [])]:
        identity = (before["case_id"], before["input_variant_id"])
        after = candidates.pop(identity, None)
        if after is None or before["input_sha256"] != after["input_sha256"]:
            raise ValueError("End-to-end input missing or changed.")
        checks = {
            key: normalize_execution(before.get(key)) == normalize_execution(after.get(key))
            for key in (
                "request",
                "retrieval",
                "stages",
                "production_stages",
                "generation_contexts",
                "answer",
            )
        }
        reports.append(
            {
                "case_id": identity[0],
                "variant_id": identity[1],
                "checks": checks,
                "passed": all(checks.values()),
                "final_answer_quality": None,
                "quality_reason": "new_answer_has_no_human_review_and_llm_is_disabled",
            }
        )
    if candidates:
        raise ValueError("Unexpected end-to-end inputs.")
    return {
        "scope": "deterministic_no_llm_execution_compatibility",
        "passed": all(row["passed"] for row in reports),
        "independent_cases": len(left["cases"]),
        "executions": len(reports),
        "actual_model_context": None,
        "semantic_answer_quality": None,
        "cases": reports,
    }


def score_e2e_availability(capture: dict[str, Any], *, root: Path) -> dict[str, Any]:
    """Report trace evidence recall; unreviewed candidate/answer quality stays unavailable."""
    contract = load_contract(root)
    inputs = load_inputs(root / DATASET, root / CASE_PROTOCOLS)
    if capture["dataset_sha256"] != inputs.dataset_sha256:
        raise ValueError("Capture dataset differs from frozen annotations.")
    definitions = {case.id: case.model_dump(mode="json") for case in inputs.dataset.cases}
    hashes = {item["document_id"]: item["sha256"] for item in capture["corpus"]["documents"]}
    k_values = tuple(contract["keyword_compatibility"]["k_values"])
    aggregates: dict[str, list[dict[str, Any]]] = {}
    cases = []
    for item in [*capture["cases"], *capture.get("control_cases", [])]:
        stages = {}
        for stage in [*item["stages"], *item["production_stages"]]:
            if stage["status"] != "ok":
                stages[stage["stage"]] = {"unavailable_reason": stage["status"], "metrics": None}
                continue
            report = evaluate_stage(
                definitions[item["case_id"]],
                stage["hits"],
                hashes,
                k_values,
                label_mode="approved",
            )
            report.pop("units", None)
            report["metrics"] = {
                name: metric
                for name, metric in report["metrics"].items()
                if not name.startswith("annotated_mrr_lower_bound")
            }
            stages[stage["stage"]] = report
            if item in capture["cases"]:
                aggregates.setdefault(stage["stage"], []).append(report)
        cases.append(
            {
                "case_id": item["case_id"],
                "variant_id": item["input_variant_id"],
                "stages": stages,
                "answer_semantic_quality": None,
                "answer_quality_reason": "no_human_review_of_new_capture_no_llm",
            }
        )
    return {
        "scope": "approved_evidence_recall_and_metric_availability_by_execution_stage",
        "dataset_sha256": inputs.dataset_sha256,
        "k_values": k_values,
        "annotation_validation_error": capture["annotation_validation_error"],
        "annotation_limit": (
            "Eight approved case definitions support anchored evidence recall only; "
            "candidate grades remain agent_review and new answers have no human review. "
            "Historical project-file refusal basis failures are not scored."
        ),
        "stage_aggregates": {
            stage: strict_aggregate(records) for stage, records in aggregates.items()
        },
        "cases": cases,
        "model_prompt_context": None,
        "external_model_calls": sum(
            len(item["llm_calls"])
            for item in [*capture["cases"], *capture.get("control_cases", [])]
        ),
    }


def synthetic_metrics(ranked_ids: list[str], grades: dict[str, int], k: int) -> dict[str, Any]:
    """Metrics over a fully specified artificial universe, never historical labels."""
    if k < 1 or len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("Require positive K and unique returned units.")
    if any(unit not in grades for unit in ranked_ids):
        raise ValueError("Unjudged synthetic candidate.")
    relevant = {unit for unit, grade in grades.items() if grade > 0}
    selected = ranked_ids[:k]
    positive = sum(unit in relevant for unit in selected)
    first = next((index for index, unit in enumerate(selected, 1) if unit in relevant), None)
    gain = sum(
        (2 ** grades[unit] - 1) / math.log2(rank + 1) for rank, unit in enumerate(selected, 1)
    )
    ideal = sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(sorted(grades.values(), reverse=True)[:k], 1)
    )
    return {
        "recall": {
            "value": positive / len(relevant) if relevant else None,
            "numerator": positive,
            "denominator": len(relevant),
        },
        "precision": {"value": positive / k, "numerator": positive, "denominator": k},
        "mrr": {
            "value": (1 / first if first else 0.0) if relevant else None,
            "first_relevant_rank": first,
            "denominator": 1 if relevant else 0,
        },
        "ndcg": {"value": gain / ideal if ideal else None, "numerator": gain, "denominator": ideal},
    }


def capture_synthetic(
    output: Path, *, backend: str, work_dir: Path, target: Path | str, root: Path
) -> dict[str, Any]:
    """Caller owns the isolated target; this function never drops a database."""
    from history_agent.processing.models import ChunkRecord

    if output.exists() or work_dir.exists():
        raise FileExistsError("Use new synthetic output and work directories.")
    contract = load_contract(root)
    fixture = read_json(root / SYNTHETIC)
    engine = (
        legacy_module(root, contract)
        if backend == "legacy"
        else importlib.import_module("history_agent.retrieval.keyword")
    )
    chunks = work_dir / "chunks"
    chunks.mkdir(parents=True)
    for index, item in enumerate(fixture["records"]):
        record = ChunkRecord(
            chunk_id=item["id"],
            document_id=item["document_id"],
            file_sha256="0" * 64,
            title="Synthetic contract corpus",
            filename=item["document_id"] + ".pdf",
            creators=item["people"],
            source_type="synthetic",
            verification_status="fixture",
            chunk_index=index,
            page_chunk_index=0,
            pdf_page_start=index + 1,
            pdf_page_end=index + 1,
            section_path=[item["section"]],
            text=item["text"],
            search_text=item["text"],
            character_count=len(item["text"]),
            year_mentions=item["years"],
            people=item["people"],
            scope_status=item["scope"],
            extraction_methods=["synthetic"],
            content_hash=digest(item["text"]),
            cleaner_version="synthetic-v1",
            chunker_version="synthetic-v1",
        )
        with (chunks / "synthetic.jsonl").open("a", encoding="utf8") as stream:
            stream.write(record.model_dump_json() + "\n")
    engine.build_keyword_index(
        chunks_dir=chunks,
        index_path=target,
        reports_dir=work_dir / "reports",
        run_id="synthetic-v1",
        project_root=root,
    )
    results = []
    for query in fixture["queries"]:
        options = dict(query["options"])
        if "plan" in options:
            options["plan"] = RetrievalPlan.model_validate(options["plan"])
        rows = {}
        for k in fixture["k_values"]:
            response = engine.search_keyword_index(
                index_path=target,
                aliases_path=root / "config/person_aliases.json",
                query=query["question"],
                top_k=k,
                **options,
            )
            metadata, hits = public_response(response)
            rows[str(k)] = {
                "hits": [hit_signature(hit) for hit in hits],
                "metadata": metadata,
                "metrics": synthetic_metrics([hit["chunk_id"] for hit in hits], query["grades"], k),
            }
        results.append({"id": query["id"], "at_k": rows})
    report = {
        "scope": "fully_specified_synthetic_contract_not_historical_golden",
        "backend": backend,
        "fixture_sha256": file_sha(root / SYNTHETIC),
        "queries": results,
        "records": len(fixture["records"]),
    }
    write_new(output, report)
    return report


def capture_synthetic_pair(output_dir: Path, *, root: Path) -> dict[str, Any]:
    """Use an explicitly configured test database and a fresh disposable schema."""
    import psycopg
    from psycopg import sql

    url = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    if not url:
        raise ValueError("Set HISTORY_AGENT_TEST_POSTGRES_URL to a test database.")
    output_dir.mkdir(parents=True, exist_ok=False)
    schema = "keyword_evaluation_" + uuid4().hex
    parsed = urlsplit(url)
    parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
    parameters["options"] = (parameters.get("options", "") + f" -csearch_path={schema}").strip()
    target = urlunsplit(parsed._replace(query=urlencode(parameters)))
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            before = capture_synthetic(
                output_dir / "baseline.json",
                backend="legacy",
                work_dir=output_dir / "legacy-work",
                target=output_dir / "legacy.sqlite",
                root=root,
            )
            after = capture_synthetic(
                output_dir / "candidate.json",
                backend="candidate",
                work_dir=output_dir / "postgres-work",
                target=target,
                root=root,
            )
        finally:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
    result = {
        "scope": "synthetic_not_historical_golden",
        "fixture_sha256": before["fixture_sha256"],
        "passed": (
            before["fixture_sha256"] == after["fixture_sha256"]
            and before["queries"] == after["queries"]
        ),
        "queries": len(before["queries"]),
        "records": before["records"],
        "baseline": "baseline.json",
        "candidate": "candidate.json",
    }
    write_new(output_dir / "comparison.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--backend", choices=("legacy", "candidate"), required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture_end = sub.add_parser("capture-e2e")
    capture_end.add_argument("--backend", choices=("legacy", "candidate"), required=True)
    capture_end.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    e2e = sub.add_parser("compare-e2e")
    e2e.add_argument("left", type=Path)
    e2e.add_argument("right", type=Path)
    e2e.add_argument("--output", type=Path, required=True)
    synthetic = sub.add_parser("capture-synthetic")
    synthetic.add_argument("--output-dir", type=Path, required=True)
    score = sub.add_parser("score-e2e")
    score.add_argument("capture", type=Path)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score-e2e":
        result = score_e2e_availability(read_json(args.capture), root=get_settings().project_root)
        write_new(args.output, result)
        print(json.dumps({"cases": len(result["cases"]), "output": str(args.output)}))
    elif args.command == "capture-synthetic":
        result = capture_synthetic_pair(args.output_dir, root=get_settings().project_root)
        print(json.dumps({"passed": result["passed"], "output": str(args.output_dir)}))
        if not result["passed"]:
            raise SystemExit(1)
    elif args.command == "capture-e2e":
        capture_e2e(args.output, backend=args.backend, root=get_settings().project_root)
    elif args.command == "capture":
        settings = get_settings()
        target = getattr(settings, "keyword_index_target", None)
        result = capture_keyword(
            args.output, backend=args.backend, target=target, settings=settings
        )
        print(json.dumps({"workloads": result["workload_count"], "output": str(args.output)}))
    else:
        function = compare_keyword if args.command == "compare" else compare_e2e
        result = function(read_json(args.left), read_json(args.right))
        write_new(args.output, result)
        print(json.dumps({"passed": result["passed"], "output": str(args.output)}))
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
