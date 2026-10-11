"""Offline production-path and cost diagnostics from recorded pilot requests.

The unions below are coverage diagnostics, never invented ranked lists. This
module neither calls the Agent nor infers source pages from generated summaries.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from statistics import mean, median
from typing import Any

from history_agent.evaluation.pilot_metrics import evaluate_stage, evidence_unit

MODES = ("provisional", "approved")
BRANCH_UNION = "recall_branch_union_all_variants_rounds"
SOURCE_UNION = "mapped_source_inputs_union_any_generation_call"
LAST_CONTEXT = "last_generation_call_context"
TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)
BASE_PHASES = (
    "keyword_candidates",
    "vector_candidates",
    "final",
    BRANCH_UNION,
    SOURCE_UNION,
    LAST_CONTEXT,
)


def _na(reason: str) -> dict[str, Any]:
    return {
        "value": None,
        "evaluable": False,
        "reason": reason,
        "numerator": None,
        "denominator": None,
        "matched_groups": [],
    }


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _phase(stage: dict[str, Any]) -> str:
    return re.sub(r"^production_\d+_", "", str(stage.get("stage", "")))


def _coverage(
    case: dict[str, Any],
    hits: list[dict[str, Any]],
    hashes: dict[str, str],
    mode: str,
    reason: str | None = None,
) -> dict[str, Any]:
    if mode == "approved" and case.get("human_review", {}).get("status") != "approved":
        return _na("case_human_review_not_approved")
    if not case.get("evidence_groups"):
        return _na("not_applicable_no_evidence_groups")
    if reason:
        return _na(reason)
    try:
        unique = {evidence_unit(hit, hashes)["unit_id"]: hit for hit in hits}
        k = max(1, len(unique))
        result = evaluate_stage(case, list(unique.values()), hashes, (k,), label_mode=mode)
    except (ValueError, TypeError, KeyError) as exc:
        return {**_na("invalid_captured_evidence"), "detail": str(exc)}
    metric = result["metrics"][f"required_group_recall@{k}"]
    return {
        **metric,
        "matched_groups": result["diagnostics"]["at_k"][str(k)]["matched_groups"],
        "returned_count": len(hits),
        "unique_unit_count": len(unique),
        "missing_group_ids": sorted(
            set(g["id"] for g in case["evidence_groups"])
            - set(result["diagnostics"]["at_k"][str(k)]["matched_groups"])
        )
        if metric["evaluable"]
        else None,
    }


def _role(call: dict[str, Any]) -> str:
    """Classify observed request structure, not the configured model or answer."""
    messages = call.get("request", {}).get("messages", [])
    systems = [m.get("content", "") for m in messages if m.get("role") == "system"]
    system = "\n".join(s for s in systems if isinstance(s, str))
    if system.startswith("你是中国近现代史本地知识库的查询理解器"):
        return "planner"
    if system.startswith("你是本地史料检索的证据充分性评估器"):
        return "retrieval_reflection"
    users = [m.get("content", "") for m in messages if m.get("role") == "user"]
    prompts = [
        s
        for s in users
        if isinstance(s, str) and s.startswith("问题：") and "\n\n仅可使用的本地证据：\n" in s
    ]
    if not prompts:
        return "unknown"
    if any(m.get("role") == "assistant" for m in messages):
        return "generation_repair"
    preamble, evidence = prompts[0].split("\n\n仅可使用的本地证据：\n", 1)
    if evidence.startswith("以下是分组证据经逐组引用校验后的摘要"):
        return "generation_synthesis"
    if "\n\n这是覆盖检索的第 " in preamble:
        return "generation_group"
    return "generation_direct"


def _call_usage(case_id: str, call: dict[str, Any], position: int) -> dict[str, Any]:
    summary = call.get("response_summary") or {}
    raw_usage = summary.get("usage") or {}
    usage = {
        key: raw_usage[key]
        for key in TOKEN_FIELDS
        if type(raw_usage.get(key)) is int and raw_usage[key] >= 0
    }
    # Inconsistent provider usage is not a complete billable-token measurement.
    consistent = not all(k in usage for k in TOKEN_FIELDS[:3]) or (
        usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
    )
    if not consistent:
        usage = {}
    http_status = call.get("http_status")
    outcome = (
        "success"
        if type(http_status) is int and 200 <= http_status < 300
        else "failure"
        if call.get("status") == "failed" or type(http_status) is int
        else "unknown"
    )
    return {
        "case_id": case_id,
        "call_index": call.get("call_index"),
        "record_position": position,
        "role": _role(call),
        "status": call.get("status"),
        "http_status": http_status,
        "http_outcome": outcome,
        "error_type": call.get("error_type"),
        "request_model": call.get("request", {}).get("model"),
        "response_model": summary.get("model"),
        "elapsed_ms": call.get("elapsed_ms") if _number(call.get("elapsed_ms")) else None,
        "usage": usage,
        "usage_complete": all(k in usage for k in TOKEN_FIELDS[:3]),
        "usage_reason": "inconsistent_provider_usage"
        if not consistent
        else "missing_or_partial_provider_usage"
        if not all(k in usage for k in TOKEN_FIELDS[:3])
        else None,
    }


def _cost(calls: list[dict[str, Any]], missing_case_ids: list[str]) -> dict[str, Any]:
    tokens = {}

    def refs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "case_id": c["case_id"],
                "call_index": c["call_index"],
                "record_position": c["record_position"],
            }
            for c in rows
        ]

    for field in TOKEN_FIELDS:
        valid = [c for c in calls if field in c["usage"]]
        missing = [c for c in calls if field not in c["usage"]]
        known_sum = sum(c["usage"][field] for c in valid) if valid else None
        tokens[field] = {
            "value": known_sum if calls and not missing and not missing_case_ids else None,
            "known_sum": known_sum,
            "evaluable_calls": len(valid),
            "total_calls": len(calls),
            "unknown_calls": refs(missing),
            "missing_capture_case_ids": missing_case_ids,
            "reason": "llm_calls_not_captured"
            if missing_case_ids
            else "no_llm_calls"
            if not calls
            else "missing_or_invalid_usage"
            if missing
            else None,
        }
    timed = [c for c in calls if c["elapsed_ms"] is not None]
    return {
        "calls": len(calls),
        "usage_complete_calls": sum(c["usage_complete"] for c in calls),
        "unknown_usage_calls": refs([c for c in calls if not c["usage_complete"]]),
        "missing_capture_case_ids": missing_case_ids,
        "tokens": tokens,
        "known_usage_totals": {field: metric["known_sum"] for field, metric in tokens.items()},
        "sum_call_elapsed_ms": sum(c["elapsed_ms"] for c in timed) if timed else None,
        "timed_call_count": len(timed),
        "untimed_calls": refs([c for c in calls if c["elapsed_ms"] is None]),
        "latency_note": "Sum of request durations, including retries; not wall-clock latency "
        "because requests may overlap.",
    }


def _http(calls: list[dict[str, Any]], missing_case_ids: list[str]) -> dict[str, Any]:
    counts = Counter(c["http_outcome"] for c in calls)
    return {
        "calls": len(calls) if not missing_case_ids else None,
        "observed_calls": len(calls),
        "success_count": counts["success"],
        "failure_count": counts["failure"],
        "unknown_count": counts["unknown"],
        "missing_capture_case_ids": missing_case_ids,
        "status_counts": dict(
            Counter(str(c["http_status"]) for c in calls if c["http_status"] is not None)
        ),
        "failures": [
            {
                k: c[k]
                for k in (
                    "case_id",
                    "call_index",
                    "record_position",
                    "status",
                    "http_status",
                    "error_type",
                )
            }
            for c in calls
            if c["http_outcome"] == "failure"
        ],
    }


def _aggregate(items: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    valid = [(case_id, metric) for case_id, metric in items if metric["evaluable"]]
    numerator = sum(metric["numerator"] for _, metric in valid)
    denominator = sum(metric["denominator"] for _, metric in valid)
    macro = mean(metric["value"] for _, metric in valid) if valid else None
    return {
        "target_case_count": len(items),
        "target_case_ids": [case_id for case_id, _ in items],
        "evaluable_case_count": len(valid),
        "evaluable_case_ids": [cid for cid, _ in valid],
        "unevaluable_cases": [
            {"case_id": cid, "reason": m["reason"]} for cid, m in items if not m["evaluable"]
        ],
        "fixed_target_macro_value": macro if len(valid) == len(items) else None,
        "fixed_target_macro_reason": None
        if items and len(valid) == len(items)
        else "not_all_target_cases_evaluable"
        if items
        else "no_target_cases",
        "observed_subset_macro_value": macro,
        "observed_subset_micro_value": numerator / denominator if denominator else None,
        "observed_subset_evidence_groups_matched": numerator if valid else None,
        "observed_subset_evidence_group_denominator": denominator if valid else None,
    }


def _latency(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    valid = [r for r in rows if r["latency"][field]["evaluable"]]
    values = [r["latency"][field]["value"] for r in valid]
    return {
        "total_cases": len(rows),
        "evaluable_cases": len(valid),
        "evaluable_case_ids": [r["case_id"] for r in valid],
        "unevaluable_cases": [
            {"case_id": r["case_id"], "reason": r["latency"][field]["reason"]}
            for r in rows
            if not r["latency"][field]["evaluable"]
        ],
        "mean_ms": mean(values) if values else None,
        "median_ms": median(values) if values else None,
        "max_ms": max(values) if values else None,
        "known_sum_ms": sum(values) if values else None,
        "total_ms": sum(values) if values and len(valid) == len(rows) else None,
        "note": "Separately measured per-case wall-clock path; one observation per case.",
    }


def _contexts(
    case: dict[str, Any],
    raw: dict[str, Any],
    hashes: dict[str, str],
    calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    sources = raw.get("generation_contexts")
    sources = sources if isinstance(sources, list) else []
    details = []
    direct_hits: list[dict[str, Any]] = []
    mapped_count = 0
    for context in sources:
        matching = [c for c in calls if c["call_index"] == context.get("call_index")]
        reason = (
            "ambiguous_or_missing_generation_call"
            if len(matching) != 1
            else "generation_http_not_successful"
            if matching[0]["http_outcome"] != "success"
            else "summary_or_unmapped_context"
            if context.get("mapping_complete") is not True
            else "context_hits_missing"
            if not isinstance(context.get("hits"), list)
            else None
        )
        hits = context.get("hits") if isinstance(context.get("hits"), list) else []
        if reason is None:
            direct_hits.extend(hits)
            mapped_count += 1
        details.append(
            {
                "call_index": context.get("call_index"),
                "role": matching[0]["role"] if len(matching) == 1 else "unknown",
                "mapping_complete": context.get("mapping_complete"),
                "http_status": matching[0]["http_status"] if len(matching) == 1 else None,
                "required_group_recall": {
                    mode: _coverage(case, hits, hashes, mode, reason) for mode in MODES
                },
                "notes": context.get("notes", []),
            }
        )
    generation_calls = [
        c
        for c in calls
        if c["role"].startswith("generation_")
        or any(s.get("call_index") == c["call_index"] for s in sources)
    ]
    # Recorder indices identify request-start order, even if a serialized list was reordered.
    ordered = sorted(
        generation_calls,
        key=lambda c: c["call_index"] if type(c["call_index"]) is int else c["record_position"],
    )
    last_call = ordered[-1] if ordered else None
    latest = [s for s in sources if last_call and s.get("call_index") == last_call["call_index"]]
    last_reason = (
        "generation_context_not_captured"
        if generation_calls and not latest
        else "no_generation_call"
        if not generation_calls
        else "ambiguous_generation_context"
        if len(latest) != 1
        else None
    )
    result = {}
    for mode in MODES:
        last = next(
            (
                d["required_group_recall"][mode]
                for d in details
                if last_call and d["call_index"] == last_call["call_index"]
            ),
            None,
        )
        result[mode] = {
            SOURCE_UNION: _coverage(
                case,
                direct_hits,
                hashes,
                mode,
                None if mapped_count else "no_mapped_successful_generation_context",
            ),
            LAST_CONTEXT: _coverage(case, [], hashes, mode, last_reason) if last_reason else last,
        }
    return details, result


def summarize_process(cases: list[dict[str, Any]], capture: dict[str, Any]) -> dict[str, Any]:
    """Summarize any recorded case set; unknown trace/usage is explicitly N/A."""
    ids = [c["id"] for c in cases]
    recorded = capture.get("cases", [])
    captured_ids = [c["case_id"] for c in recorded]
    if len(set(ids)) != len(ids) or len(set(captured_ids)) != len(captured_ids):
        raise ValueError("duplicate process case IDs")
    if set(captured_ids) - set(ids):
        raise ValueError("capture contains cases outside the supplied dataset")
    captured = {c["case_id"]: c for c in recorded}
    hashes = {d["document_id"]: d["sha256"] for d in capture.get("corpus", {}).get("documents", [])}
    phases = sorted(
        set(BASE_PHASES) | {_phase(s) for r in recorded for s in r.get("production_stages") or []}
    )
    rows = []
    all_calls = []
    missing_calls = []
    for case in cases:
        case_id = case["id"]
        raw = captured.get(case_id, {})
        raw_calls = raw.get("llm_calls")
        missing = [] if isinstance(raw_calls, list) else [case_id]
        missing_calls.extend(missing)
        calls = [
            _call_usage(case_id, c, i)
            for i, c in enumerate(raw_calls if isinstance(raw_calls, list) else [], 1)
        ]
        all_calls.extend(calls)
        traces = raw.get("production_stages") or []
        context_details, context_unions = _contexts(case, raw, hashes, calls)
        coverage: dict[str, dict[str, Any]] = {mode: {} for mode in MODES}
        for phase in phases:
            if phase in (SOURCE_UNION, LAST_CONTEXT):
                for mode in MODES:
                    coverage[mode][phase] = context_unions[mode][phase]
                continue
            selected = (
                [s for s in traces if _phase(s) in {"keyword_candidates", "vector_candidates"}]
                if phase == BRANCH_UNION
                else [s for s in traces if _phase(s) == phase]
            )
            reason = (
                "phase_not_captured_or_not_executed"
                if not selected
                else "incomplete_or_failed_stage_trace"
                if any(
                    s.get("status") != "ok" or not isinstance(s.get("hits"), list) for s in selected
                )
                else None
            )
            hits = [h for s in selected for h in s.get("hits", [])] if not reason else []
            for mode in MODES:
                coverage[mode][phase] = _coverage(case, hits, hashes, mode, reason)
        latency = {
            field: {"value": raw[field], "evaluable": True, "reason": None}
            if _number(raw.get(field))
            else _na("wall_clock_measurement_missing_or_invalid")
            for field in ("retrieval_ms", "answer_ms")
        }
        rows.append(
            {
                "case_id": case_id,
                "answerability": case.get("answerability"),
                "production_phase_union_diagnostics": coverage,
                "generation_contexts": context_details,
                "latency": latency,
                "cost": _cost(calls, missing),
                "http": _http(calls, missing),
            }
        )
    target = [row for row in rows if row["answerability"] == "answerable"]
    return {
        "schema_version": 1,
        "basis": "recorded_capture_with_separate_annotation_gates",
        "target_cases": len(cases),
        "answerable_cases": len(target),
        "production_phase_summary": {
            mode: {
                phase: _aggregate(
                    [
                        (row["case_id"], row["production_phase_union_diagnostics"][mode][phase])
                        for row in target
                    ]
                )
                for phase in phases
            }
            for mode in MODES
        },
        "cost": {
            "all": _cost(all_calls, missing_calls),
            "by_stage": {
                role: _cost([c for c in all_calls if c["role"] == role], missing_calls)
                for role in sorted({c["role"] for c in all_calls})
            },
        },
        "latency": {field: _latency(rows, field) for field in ("retrieval_ms", "answer_ms")},
        "http": _http(all_calls, missing_calls),
        "call_usage": all_calls,
        "per_case": rows,
        "caveats": [
            "Phase unions merge variants and rounds for required-evidence coverage only; "
            "they are not rankings for Precision/MRR/nDCG.",
            "Mapped-source union includes successful direct source prompts, including group "
            "summaries and repairs; it does not map a synthesis summary back to source pages.",
            "Last context means the last recorded generation attempt, not proof that its draft "
            "became the final answer. Missing/failed/unmapped final context remains N/A.",
            "Required evidence uses exact frozen anchors or reviewed span-identity labels. "
            "Cropping creates a new span identity; lower coverage need not imply semantic loss.",
            "HTTP counts include every recorded attempt, including retries. Unknown usage "
            "is excluded from known sums and invalidates complete totals. "
            "No price estimate is made.",
        ],
    }
