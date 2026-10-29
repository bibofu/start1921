"""Build fixed candidate pools and LLM relevance labels for the Golden 20 set.

This is evaluation tooling only. It reads a frozen capture, constructs a
top-5-union pool for cases without candidate labels, asks the configured model
for 0/1/2 judgments (or abstention), and only writes when ``--write`` is given.
LLM labels use basis ``llm_judge`` and are not human approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from history_agent.config import Settings, get_settings
from history_agent.evaluation.candidate_judge import (
    judge_candidates,
    judgment_to_record,
)
from history_agent.evaluation.pilot_metrics import evidence_unit
from history_agent.evaluation.pilot_models import PilotDataset, RankingPool, seal_ranking_pool
from history_agent.log import log_event

LOGGER = logging.getLogger(__name__)
DATASET = Path("evals/golden/golden_dataset.json")
POOLS = Path("evals/golden/ranking_pools.json")
DEFAULT_CAPTURE = Path("data/reports/golden20_r3_20261029/capture.json")
TARGET_CASES = [
    "dev_exact_zunyi_election",
    "dev_multi_meetings",
    "dev_multi_mao_hunan",
    "dev_intersection_mao_zhou_1949",
    "dev_constraint_history_isolation",
    "holdout_exact_date",
    "holdout_semantic_observation",
    "holdout_multi_period",
    "holdout_intersection_negative",
    "holdout_intersection_positive",
]
STAGES = ("keyword_candidates", "vector_candidates", "final")
UNITS_PER_STAGE = 5


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _normalized_hash(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", "", text).encode("utf-8")).hexdigest()


def _pool_entry(case_capture: dict, hit: dict, hashes: dict[str, str]) -> dict:
    key = (
        hit["document_id"],
        hit["pdf_page_start"],
        hit["pdf_page_end"],
        _normalized_hash(str(hit["text"])),
    )
    for entry in case_capture.get("candidate_pool", []):
        entry_key = (
            entry["document_id"],
            entry["pdf_page_start"],
            entry["pdf_page_end"],
            entry["normalized_text_sha256"],
        )
        if entry_key == key:
            return entry
    unit = evidence_unit(hit, hashes)
    return {
        "unit_id": unit["unit_id"],
        "document_id": unit["document_id"],
        "file_sha256": unit["file_sha256"],
        "pdf_page_start": unit["pdf_page_start"],
        "pdf_page_end": unit["pdf_page_end"],
        "normalized_text_sha256": unit["normalized_text_sha256"],
        "identity": unit["identity"],
        "text": unit["text"],
    }


def build_pool(case: dict, case_capture: dict, hashes: dict[str, str], capture_path: Path) -> dict:
    ordered: list[dict] = []
    seen: set[str] = set()
    for stage in STAGES:
        stage_hits = next(
            (
                item.get("hits", [])
                for item in case_capture.get("stages", [])
                if item.get("stage") == stage
            ),
            [],
        )
        for hit in stage_hits[:UNITS_PER_STAGE]:
            entry = _pool_entry(case_capture, hit, hashes)
            if entry["unit_id"] not in seen:
                seen.add(entry["unit_id"])
                ordered.append(entry)
    if not ordered:
        raise ValueError(f"empty candidate pool: {case['id']}")
    payload = {
        "schema_version": 1,
        "pool_id": f"ranking-pool-v1-20261029-{case['id']}",
        "case_id": case["id"],
        "selection_policy": (
            "Frozen union of the first 5 returned spans of the raw-question "
            f"keyword_candidates, vector_candidates and final stages in {capture_path} "
            "(candidate_k=30, top_k=20). Identity deduplication only; no positive "
            "evidence was added to retrieval outputs. This graded pool is not an "
            "exhaustive relevance census; nDCG is relative to this declared pool."
        ),
        "unit_ids": [entry["unit_id"] for entry in ordered],
        "unit_identity_records": ordered,
        "basis": "agent_review",
        "reviewer": "agent:llm_candidate_pool_20261029",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "sha256": None,
    }
    return seal_ranking_pool(payload)


def _judge_case(
    settings: Settings, case: dict, pool: dict,
) -> tuple[list[dict], str | None, dict | None]:
    candidates = [
        {
            "candidate_id": f"C{index}",
            "unit_id": record["unit_id"],
            "document": case["id"],
            "pdf_page_start": record["pdf_page_start"],
            "section_path": [],
            "text": record["text"],
        }
        for index, record in enumerate(pool["unit_identity_records"], start=1)
    ]
    # Use the document title and section from the capture pool entry when available.
    for candidate, record in zip(candidates, pool["unit_identity_records"], strict=True):
        candidate["document"] = record.get("document_id", candidate["document"])
    reviewed_at = datetime.now(UTC).isoformat()
    for attempt in range(2):
        result = judge_candidates(settings, case, candidates)
        if result.status == "used":
            by_id = {item.candidate_id: item for item in result.decisions}
            records = []
            for candidate in candidates:
                judgment = by_id[candidate["candidate_id"]]
                record = judgment_to_record(
                    judgment,
                    unit_id=candidate["unit_id"],
                    model=settings.llm_model,
                    reviewed_at=reviewed_at,
                )
                if record is not None:
                    records.append(record)
            return records, None, result.usage
        if attempt == 0 and result.status in {"invalid_response", "http_error"}:
            continue
        return [], result.error_code or result.status, result.usage
    return [], "invalid_response", None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--pools", type=Path, default=POOLS)
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--case", action="append", dest="cases", default=None)
    parser.add_argument("--replace-pools", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_enabled:
        raise SystemExit("LLM is not configured; set DEEPSEEK_API_KEY before judging.")
    dataset = _load(args.dataset)
    pools = _load(args.pools)
    capture = _load(args.capture)
    by_id = {case["id"]: case for case in dataset["cases"]}
    capture_by_id = {case["case_id"]: case for case in capture["cases"]}
    hashes = {item["document_id"]: item["sha256"] for item in capture["corpus"]["documents"]}
    if args.replace_pools:
        selected = set(args.cases or TARGET_CASES)
        pools["pools"] = [pool for pool in pools["pools"] if pool["case_id"] not in selected]
    existing_pool_cases = {pool["case_id"] for pool in pools["pools"]}

    failures = 0
    for case_id in args.cases or TARGET_CASES:
        case = by_id[case_id]
        if case.get("judgments"):
            print(f"skip {case_id}: already has candidate judgments")
            continue
        if case_id not in capture_by_id:
            print(f"missing capture: {case_id}")
            failures += 1
            continue
        try:
            pool = build_pool(case, capture_by_id[case_id], hashes, args.capture)
        except Exception as exc:
            print(f"pool failed {case_id}: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        print(f"judging {case_id}: {len(pool['unit_ids'])} candidates")
        records, error, usage = _judge_case(settings, case, pool)
        if error:
            print(f"judge failed {case_id}: {error}")
            failures += 1
            continue
        print(f"  labels {len(records)} / {len(pool['unit_ids'])}; usage {usage}")
        case["judgments"] = records
        if case_id not in existing_pool_cases:
            pools["pools"].append(pool)
            existing_pool_cases.add(case_id)

    if not args.write:
        print("dry run only; pass --write to update dataset and pools")
        return
    PilotDataset.model_validate(dataset)
    for pool in pools["pools"]:
        RankingPool.model_validate(pool)
    _write(args.dataset, dataset)
    _write(args.pools, pools)
    print(f"wrote {args.dataset} and {args.pools}; failures={failures}")
    log_event(LOGGER, logging.INFO, "candidate_pools_judged", failures=failures)


if __name__ == "__main__":
    main()
