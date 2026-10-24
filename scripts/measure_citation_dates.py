"""Offline calibration for delivery-time date checks.

Replays a frozen evaluation capture against the chunk artifacts so a proposed
date rule can be measured without a model call or a running service.

For every full date the model wrote, this compares:

* ``old`` - what the offline validator did: look for the month/day inside the
  420-character citation excerpt;
* ``new`` - look for the date in the cited chunk's full text, and accept an
  answer that is less precise than the evidence (year-only evidence still
  supports a year, but not a month).

The output separates "contradicted" (a date the evidence actively refutes) from
"unverifiable" (the cited chunk has no dates at all), because only the former is
a candidate for enforcement.

Usage:
    python scripts/measure_citation_dates.py \
        --capture data/reports/eval_observation_20261005/live_capture.json \
        --output data/reports/citation_date_calibration
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
from history_agent.answering.models import Citation  # noqa: E402

ELLIPSIS = re.compile(r"[……]+")
WHITESPACE = re.compile(r"\s+")
CJK_WITH_YEAR = re.compile(r"(?P<year>[〇零一二三四五六七八九]{4})\s*年")
MONTH_DAY = re.compile(
    r"(?<!\d)(?P<month>0?[1-9]|1[0-2])\s*月(?:\s*(?P<day>3[01]|[12]\d|0?[1-9])\s*日)?"
)


def _normalize(text: str) -> str:
    return WHITESPACE.sub("", ELLIPSIS.sub("", text))


def _chunk_index(chunks_dir: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    index: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for path in sorted(chunks_dir.glob("*.jsonl")):
        with path.open(encoding="utf8") as handle:
            for line in handle:
                record = json.loads(line)
                key = (record["document_id"], int(record["pdf_page_start"]))
                index.setdefault(key, []).append(record)
    return index


def _resolve_text(
    citation: Citation,
    index: dict[tuple[str, int], list[dict[str, Any]]],
) -> tuple[str | None, list[str]]:
    candidates = index.get((citation.document_id, int(citation.pdf_page)), [])
    if not candidates:
        return None, []
    sections = [str(item) for item in citation.section]
    first = _normalize(citation.quote).split("……")[0]
    probe = first[:80]
    if probe:
        for record in candidates:
            if probe in _normalize(record["text"]):
                return record["text"], sections
    if len(candidates) == 1:
        return candidates[0]["text"], sections
    return None, sections


def _section_years(sections: list[str]) -> list[int]:
    years: list[int] = []
    for section in sections:
        for match in re.finditer(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", section):
            years.append(int(match.group(1)))
    return sorted(set(years))


def _evidence_dates(text: str, sections: list[str]) -> list[tuple[int | None, int, int | None]]:
    """Return every (year, month, day) the evidence states, with optional year."""

    normalized = validation.normalize_chinese_dates(text)
    dates: list[tuple[int | None, int, int | None]] = []
    for match in validation.FULL_DATE_REFERENCE.finditer(normalized):
        day = int(match["day"]) if match["day"] else None
        dates.append((int(match["year"]), int(match["month"]), day))
    section_year = _section_years(sections)
    fallback = section_year[0] if len(section_year) == 1 else None
    if not dates and fallback is None:
        return []
    covered = {(year, month, day) for year, month, day in dates}
    for match in MONTH_DAY.finditer(normalized):
        month = int(match["month"])
        day = int(match["day"]) if match["day"] else None
        if fallback is not None and (fallback, month, day) in covered:
            continue
        if fallback is not None:
            dates.append((fallback, month, day))
    return dates


def _classify(
    year: int,
    month: int,
    day: int | None,
    evidence: list[tuple[int | None, int, int | None]],
    year_hint: bool,
) -> str:
    if not evidence:
        return "unverifiable" if year_hint else "no_evidence"
    same_year = [item for item in evidence if item[0] is None or item[0] == year]
    month_match = [item for item in same_year if item[1] == month]
    if month_match:
        if day is not None and any(
            item[2] is not None and item[2] != day for item in month_match
        ) and not any(item[2] == day or item[2] is None for item in month_match):
            return "contradicted_day"
        if day is not None and any(item[2] is None for item in month_match):
            return "under_precise"
        return "supported"
    if same_year:
        return "contradicted_month"
    return "contradicted_year"


def _answer_dates(block: str) -> list[tuple[int, int, int | None, str]]:
    normalized = validation.normalize_chinese_dates(block)
    dates: list[tuple[int, int, int | None, str]] = []
    for match in validation.FULL_DATE_REFERENCE.finditer(normalized):
        day = int(match["day"]) if match["day"] else None
        dates.append((int(match["year"]), int(match["month"]), day, match.group(0)))
    return dates


def _evaluate_case(
    case: dict[str, Any],
    index: dict[tuple[str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    answer = case.get("answer") or case.get("response") or {}
    if answer.get("generator_mode") != "llm":
        return {"case_id": case["case_id"], "skipped": answer.get("generator_mode")}
    citations = {
        item["evidence_id"]: Citation.model_validate(item)
        for item in answer.get("citations") or []
    }
    blocks = validation._claim_blocks(answer.get("answer") or "")
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    full_text_cache: dict[str, tuple[str | None, list[str]]] = {}
    for block in blocks:
        markers = validation.EVIDENCE_MARKER.findall(block.text)
        if not markers:
            continue
        for year, month, day, raw in _answer_dates(block.text):
            old_ok = any(
                validation._citation_supports_date(citations[marker], year, month, day)
                for marker in markers
                if marker in citations
            )
            outcomes: list[str] = []
            for marker in dict.fromkeys(markers):
                citation = citations.get(marker)
                if citation is None:
                    continue
                if marker not in full_text_cache:
                    full_text_cache[marker] = _resolve_text(citation, index)
                text, sections = full_text_cache[marker]
                if text is None:
                    outcomes.append("unresolved_text")
                    continue
                evidence = _evidence_dates(text, sections)
                year_hint = year in citation.year_mentions
                outcomes.append(_classify(year, month, day, evidence, year_hint))
            best = _best(outcomes)
            rows.append(
                {
                    "raw": raw,
                    "year": year,
                    "month": month,
                    "day": day,
                    "markers": markers,
                    "old_ok": old_ok,
                    "new": best,
                    "outcomes": outcomes,
                    "block": block.text[:200],
                }
            )
            if best == "unresolved_text":
                unresolved.append(block.text[:80])
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "dates": rows,
        "unresolved": unresolved,
    }


_PRIORITY = (
    "supported",
    "under_precise",
    "contradicted_day",
    "contradicted_month",
    "contradicted_year",
    "unverifiable",
    "no_evidence",
    "unresolved_text",
)


def _best(outcomes: list[str]) -> str:
    if not outcomes:
        return "no_evidence"
    for level in _PRIORITY:
        if level in outcomes:
            return level
    return outcomes[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument(
        "--chunks", type=Path, default=PROJECT_ROOT / "data" / "processed" / "chunks"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    capture = json.loads(args.capture.read_text(encoding="utf8"))
    index = _chunk_index(args.chunks)
    results = [_evaluate_case(case, index) for case in capture["cases"]]

    rows = [row for result in results for row in result.get("dates") or []]
    old_flagged = [row for row in rows if not row["old_ok"]]
    new_enforced = [
        row for row in rows
        if row["new"] in {"contradicted_day", "contradicted_month", "contradicted_year"}
    ]
    old_only = [
        row
        for row in old_flagged
        if row["new"] in {"supported", "under_precise", "unverifiable"}
    ]
    new_only = [row for row in new_enforced if row["old_ok"]]
    totals = {
        "cases": len(results),
        "dates": len(rows),
        "old_flagged": len(old_flagged),
        "new_contradicted": len(new_enforced),
        "old_false_alarm_candidates": len(old_only),
        "new_only_findings": len(new_only),
        "by_outcome": dict(Counter(row["new"] for row in rows)),
        "unresolved_citations": sum(len(result.get("unresolved") or []) for result in results),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(
        json.dumps({"totals": totals, "cases": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (args.output / "summary.md").write_text(
        _render_summary(totals, old_flagged, old_only, new_enforced, new_only),
        encoding="utf8",
    )
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


def _render_summary(
    totals: dict[str, Any],
    old_flagged: list[dict[str, Any]],
    old_only: list[dict[str, Any]],
    new_enforced: list[dict[str, Any]],
    new_only: list[dict[str, Any]],
) -> str:
    lines = ["# 日期校验校准回放", "", "## 总计", ""]
    for key, value in totals.items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## 旧规则标记、新规则认为可接受（疑似误伤）", ""]
    lines += [_row(item) for item in old_only[:40]] or ["- 无"]
    lines += ["", "## 新规则判定为矛盾（候选拦截）", ""]
    lines += [_row(item) for item in new_enforced[:40]] or ["- 无"]
    lines += ["", "## 仅新规则发现（旧规则漏掉）", ""]
    lines += [_row(item) for item in new_only[:40]] or ["- 无"]
    lines.append("")
    return "\n".join(lines)


def _row(item: dict[str, Any]) -> str:
    return (
        f"- `{item['raw']}` old_ok={item['old_ok']} new={item['new']} "
        f"markers={item['markers']}：{item['block'][:90]}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
