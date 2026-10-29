"""Compare archived migration reports and evaluate PostgreSQL keyword fixtures.

The retired source-database capture runner is intentionally unavailable. Existing
JSON captures remain readable without loading the retired backend or its code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from history_agent.config import get_settings
from history_agent.errors import RetrievalError
from history_agent.evaluation.pilot_metrics import evaluate_stage
from history_agent.evaluation.pilot_protocols import load_inputs
from history_agent.retrieval import keyword
from history_agent.retrieval.models import RetrievalPlan

PROTOCOL = Path("evals/keyword_migration/protocol_v1.json")
DATASET = Path("evals/golden/development_annotations_v6.json")
CASE_PROTOCOLS = Path("evals/golden/development_protocols_v6.json")
SYNTHETIC = Path("evals/keyword_migration/synthetic_v1.json")
VOLATILE_FIELDS = {"elapsed_ms", "retrieval_ms", "answer_ms", "latency_ms"}


def file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")
    ).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load_contract(root: Path) -> dict[str, Any]:
    """Verify frozen annotation inputs without opening retired storage artifacts."""
    contract: dict[str, Any] = read_json(root / PROTOCOL)
    for artifact in contract["annotation_inputs"]:
        if file_sha(root / artifact["path"]) != artifact["sha256"]:
            raise ValueError(f"Frozen annotation changed: {artifact['path']}")
    return contract


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
    output: Path, *, work_dir: Path, target: str, root: Path
) -> dict[str, Any]:
    """Caller owns the isolated target; this function never drops a database."""
    from history_agent.processing.models import ChunkRecord

    if output.exists() or work_dir.exists():
        raise FileExistsError("Use new synthetic output and work directories.")
    fixture = read_json(root / SYNTHETIC)
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
    keyword.build_keyword_index(
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
            response = keyword.search_keyword_index(
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
        "backend": "postgresql",
        "fixture_sha256": file_sha(root / SYNTHETIC),
        "queries": results,
        "records": len(fixture["records"]),
    }
    write_new(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("compare", "compare-e2e"):
        command = sub.add_parser(name)
        command.add_argument("left", type=Path)
        command.add_argument("right", type=Path)
        command.add_argument("--output", type=Path, required=True)
    score = sub.add_parser("score-e2e")
    score.add_argument("capture", type=Path)
    score.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score-e2e":
        result = score_e2e_availability(read_json(args.capture), root=get_settings().project_root)
        write_new(args.output, result)
        print(json.dumps({"cases": len(result["cases"]), "output": str(args.output)}))
    else:
        function = compare_keyword if args.command == "compare" else compare_e2e
        result = function(read_json(args.left), read_json(args.right))
        write_new(args.output, result)
        print(json.dumps({"passed": result["passed"], "output": str(args.output)}))
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
