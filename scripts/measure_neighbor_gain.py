"""Measure what neighbour-chunk expansion would actually buy.

Before changing retrieval, answer two questions on frozen data:

1. Page-level recall: how many required evidence pages would become reachable
   only by following ``previous_chunk_id`` / ``next_chunk_id`` from a retrieved
   chunk?
2. Date coverage: how many dates the cited chunk does not support are present in
   a neighbouring chunk of that same citation?

Usage:
    python scripts/measure_neighbor_gain.py \
        --capture data/reports/eval_observation_20261005/live_capture.json \
        --annotations evals/golden/development_v2.json \
        --answers data/reports/citation_date_calibration/live_answers.json \
        --output data/reports/neighbor_gain
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from history_agent.answering import validation  # noqa: E402
from history_agent.answering.citation_check import _evidence_dates  # noqa: E402
from history_agent.answering.models import Citation  # noqa: E402

ELLIPSIS = re.compile(r"[……]+")
WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return WHITESPACE.sub("", ELLIPSIS.sub("", text))


def _load_chunks(chunks_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(chunks_dir.glob("*.jsonl")):
        with path.open(encoding="utf8") as handle:
            for line in handle:
                record = json.loads(line)
                records[record["chunk_id"]] = record
    return records


def _required_pages(annotations: dict[str, Any]) -> dict[str, list[set[tuple[str, int]]]]:
    """Each evidence group is a set of acceptable (document, page) alternatives."""

    groups: dict[str, list[set[tuple[str, int]]]] = {}
    for case in annotations["cases"]:
        entries: list[set[tuple[str, int]]] = []
        for group in case.get("evidence_groups") or []:
            pages = {
                (alt["document_id"], int(alt["pdf_page"]))
                for alt in group.get("alternatives") or []
            }
            if pages:
                entries.append(pages)
        groups[case["id"]] = entries
    return groups


def _hit_pages(hits: list[dict[str, Any]]) -> set[tuple[str, int]]:
    pages: set[tuple[str, int]] = set()
    for hit in hits:
        start = int(hit["pdf_page_start"])
        end = int(hit.get("pdf_page_end") or start)
        for page in range(start, end + 1):
            pages.add((hit["document_id"], page))
    return pages


def _neighbour_pages(
    hits: list[dict[str, Any]], chunks: dict[str, dict[str, Any]]
) -> set[tuple[str, int]]:
    pages: set[tuple[str, int]] = set()
    for hit in hits:
        record = chunks.get(hit["chunk_id"])
        if record is None:
            continue
        for key in ("previous_chunk_id", "next_chunk_id"):
            neighbour = chunks.get(record.get(key) or "")
            if neighbour is None:
                continue
            pages.add((neighbour["document_id"], int(neighbour["pdf_page_start"])))
    return pages


def _recall(
    capture: dict[str, Any],
    annotations: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required = _required_pages(annotations)
    cases: list[dict[str, Any]] = []
    totals = Counter()
    for case in capture["cases"]:
        case_id = case["case_id"]
        groups = required.get(case_id)
        if not groups:
            continue
        hits = (case.get("retrieval") or {}).get("hits") or []
        pages = _hit_pages(hits)
        neighbours = _neighbour_pages(hits, chunks)
        now = sum(1 for group in groups if group & pages)
        expanded = sum(1 for group in groups if group & (pages | neighbours))
        gained = [
            sorted(group & (pages | neighbours)) for group in groups if not group & pages
        ]
        totals["groups"] += len(groups)
        totals["now"] += now
        totals["expanded"] += expanded
        totals["newly_reachable"] += sum(
            1 for group in groups if not group & pages and group & neighbours
        )
        cases.append(
            {
                "case_id": case_id,
                "groups": len(groups),
                "now": now,
                "expanded": expanded,
                "newly_reachable": sum(
                    1 for group in groups if not group & pages and group & neighbours
                ),
                "gained": [[list(item) for item in value] for value in gained if value],
            }
        )
    return {"cases": cases, "totals": dict(totals)}


def _date_gain(
    answers: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """For each date the cited chunk misses, look for it in that chunk's neighbours."""

    rows: list[dict[str, Any]] = []
    for case in answers["cases"]:
        response = case.get("response") or {}
        if response.get("generator_mode") != "llm":
            continue
        citations = {
            item["evidence_id"]: Citation.model_validate(item)
            for item in response.get("citations") or []
        }
        for block in validation._claim_blocks(response.get("answer") or ""):
            markers = validation.EVIDENCE_MARKER.findall(block.text)
            if not markers:
                continue
            for match in validation.FULL_DATE_REFERENCE.finditer(
                validation.normalize_chinese_dates(block.text)
            ):
                day = int(match["day"]) if match["day"] else None
                year, month = int(match["year"]), int(match["month"])
                for marker in dict.fromkeys(markers):
                    citation = citations.get(marker)
                    if citation is None:
                        continue
                    record = _find_chunk(citation, chunks)
                    if record is None:
                        continue
                    own = _evidence_dates(record["text"], citation)
                    if any(
                        (item[0] in (None, year)) and item[1] == month and item[2] in (None, day)
                        for item in own
                    ):
                        continue
                    neighbour_hit = False
                    for key in ("previous_chunk_id", "next_chunk_id"):
                        neighbour = chunks.get(record.get(key) or "")
                        if neighbour is None:
                            continue
                        dates = _evidence_dates(neighbour["text"], citation)
                        if any(
                            (item[0] in (None, year))
                            and item[1] == month
                            and item[2] in (None, day)
                            for item in dates
                        ):
                            neighbour_hit = True
                            break
                    rows.append(
                        {
                            "case_id": case["case_id"],
                            "date": match.group(0),
                            "evidence": marker,
                            "document": citation.document,
                            "page": citation.pdf_page,
                            "neighbour_recovers": neighbour_hit,
                            "neighbour_pages": [
                                int(chunks[record[key]]["pdf_page_start"])
                                for key in ("previous_chunk_id", "next_chunk_id")
                                if record.get(key) in chunks
                            ],
                        }
                    )
    totals = {
        "dates_missing_in_own_chunk": len(rows),
        "recovered_by_neighbour": sum(1 for row in rows if row["neighbour_recovers"]),
    }
    return {"rows": rows, "totals": totals}


def _find_chunk(
    citation: Citation, chunks: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    candidates = [
        record
        for record in chunks.values()
        if record["document_id"] == citation.document_id
        and int(record["pdf_page_start"]) == citation.pdf_page
    ]
    probe = _normalize(citation.quote).split("……")[0][:80]
    for record in candidates:
        if probe and probe in _normalize(record["text"]):
            return record
    return candidates[0] if len(candidates) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--answers", type=Path)
    parser.add_argument(
        "--chunks", type=Path, default=PROJECT_ROOT / "data" / "processed" / "chunks"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    chunks = _load_chunks(args.chunks)
    capture = json.loads(args.capture.read_text(encoding="utf8"))
    annotations = json.loads(args.annotations.read_text(encoding="utf8"))
    report: dict[str, Any] = {"recall": _recall(capture, annotations, chunks)}
    if args.answers:
        report["dates"] = _date_gain(
            json.loads(args.answers.read_text(encoding="utf8")), chunks
        )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    lines = ["# 邻居扩展收益测量", "", "## 页级召回", ""]
    for key, value in report["recall"]["totals"].items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## 日期覆盖", ""]
    for key, value in (report.get("dates") or {}).get("totals", {}).items():
        lines.append(f"- {key}: {value}")
    (args.output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print(
        json.dumps(
            {
                "recall": report["recall"]["totals"],
                "dates": (report.get("dates") or {}).get("totals"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
