"""Explicit protocol checks and case-specific diagnostics, never automatic judging.

Specialist observations are separate from the main case aggregate. In particular,
a conversation control arm and six yearly strata do not become additional cases.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import HumanReview, case_definition
from history_agent.evaluation.pilot_process import BRANCH_UNION, LAST_CONTEXT, SOURCE_UNION

MODES = ("provisional", "approved")
RUBRIC_VERSION = "explicit-specialist-review-v1"
MUTABLE_ROW = {"basis", "reviewer", "reviewed_at"}


def _protocol_map(protocols: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = protocols.get("cases", [])
    result = {row["case_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate specialist protocol case IDs")
    return result


def _specs(protocol: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Keep declared item lists and their denominators; never split prose into checks."""
    specialist = protocol.get("specialist_protocol") or {}
    result = {}
    for section in ("dimensions", "stage_criteria", "stages"):
        for name, value in specialist.get(section, {}).items():
            if not isinstance(value, dict) or value.get("applicable") is False:
                continue
            checks = value.get("criteria") or value.get("checks")
            if not checks and value.get("pass_rule"):
                checks = [value["pass_rule"]]
            if checks:
                if not isinstance(checks, list) or not all(
                    isinstance(check, str) and check.strip() for check in checks
                ):
                    raise ValueError("specialist checks must be explicit nonempty strings")
                denominator = value.get("denominator")
                if section == "stages" and denominator is None:
                    candidates = [
                        metric["denominator"]
                        for metric in value.get("metrics", [])
                        if "checks" in metric.get("name", "")
                    ]
                    denominator = candidates[0] if len(candidates) == 1 else None
                if type(denominator) is int and denominator != len(checks):
                    raise ValueError(f"specialist check denominator mismatch: {name}")
                result[f"{section}.{name}"] = {
                    "denominator": len(checks),
                    "declared_denominator": denominator,
                    "checks": checks,
                }
            # Some refusal protocols declare a one-decision routing/refusal rubric
            # as a metric rule. Their one-item denominator must remain one.
            if section == "stages":
                for metric in value.get("metrics", []):
                    if (
                        metric.get("name")
                        not in {
                            "routing_validity",
                            "safe_refusal",
                            "scope_explanation",
                            "source_constraint",
                            "false_refusal",
                        }
                        or metric.get("denominator") != 1
                        or not metric.get("rule")
                    ):
                        continue
                    result[f"{section}.{name}.{metric['name']}"] = {
                        "denominator": 1,
                        "declared_denominator": 1,
                        "checks": [metric["rule"]],
                    }
    return result


def _dimensions(specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        name: {
            "denominator": spec["denominator"],
            "declared_denominator": spec.get("declared_denominator"),
            "checks": [
                {
                    "check_id": f"{name}.{i}",
                    "criterion": criterion,
                    "status": "unknown",
                    "reason": "awaiting_explicit_specialist_review",
                }
                for i, criterion in enumerate(spec["checks"], 1)
            ],
        }
        for name, spec in specs.items()
    }


def _raw_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in rows:
        key = f"{row['case_id']}::{row.get('input_variant_id', 'single_turn')}"
        if key in result:
            raise ValueError("duplicate specialist input observation")
        if "request" in row and row.get("input_sha256") != fingerprint(
            {field: row["request"][field] for field in ("question", "history")}
        ):
            raise ValueError("specialist observation input hash mismatch")
        result[key] = row
    return result


def _binding(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_variant_id": raw.get("input_variant_id", "single_turn"),
        "input_sha256": raw.get("input_sha256"),
    }


def prepare_specialist_reviews(
    cases: list[dict[str, Any]], protocols: dict[str, Any], capture: dict[str, Any]
) -> dict[str, Any]:
    """Create capture-bound pending checks for every observed protocol input arm."""
    by_protocol = _protocol_map(protocols)
    by_case = {case["id"]: case for case in cases}
    if len(by_case) != len(cases):
        raise ValueError("duplicate specialist dataset cases")
    raw = _raw_map([*capture.get("cases", []), *capture.get("control_cases", [])])
    rows = []
    for observation in raw.values():
        cid = observation["case_id"]
        if cid not in by_case or cid not in by_protocol:
            raise ValueError(f"missing specialist case or protocol: {cid}")
        definition_hash = fingerprint(case_definition(by_case[cid]))
        if observation["case_definition_sha256"] != definition_hash or (
            by_protocol[cid].get("case_definition_sha256") != definition_hash
        ):
            raise ValueError(f"specialist case definition changed: {cid}")
        if "request" in observation:
            variant = next(
                (
                    item
                    for item in by_protocol[cid].get("input_variants", [])
                    if item["id"] == observation.get("input_variant_id")
                ),
                None,
            )
            if variant is None or any(
                observation["request"].get(field) != variant[field]
                for field in ("question", "history")
            ):
                raise ValueError(f"specialist input differs from protocol: {cid}")
        specs = _specs(by_protocol[cid])
        if specs:
            rows.append(
                {
                    "case_id": cid,
                    "case_definition_sha256": definition_hash,
                    **_binding(observation),
                    "basis": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "dimensions": _dimensions(specs),
                }
            )
    paired = []
    for cid, case in by_case.items():
        protocol = by_protocol.get(cid, {}).get("specialist_protocol") or {}
        conversation = protocol.get("conversation_protocol") or {}
        checks = conversation.get("primary_isolation_checks")
        if not checks:
            continue
        if conversation.get("isolation_denominator") != len(checks):
            raise ValueError("paired isolation denominator mismatch")
        paired.append(
            {
                "case_id": cid,
                "case_definition_sha256": fingerprint(case_definition(case)),
                "input_bindings": [_binding(row) for row in raw.values() if row["case_id"] == cid],
                "basis": None,
                "reviewer": None,
                "reviewed_at": None,
                "dimensions": _dimensions(
                    {
                        "history_isolation": {
                            "denominator": len(checks),
                            "declared_denominator": len(checks),
                            "checks": checks,
                        }
                    }
                ),
            }
        )
    return {
        "schema_version": 1,
        "rubric_version": RUBRIC_VERSION,
        "capture_sha256": fingerprint(capture),
        "protocols_sha256": fingerprint(protocols),
        "cases": rows,
        "paired_isolation": paired,
    }


def _validate_packet(payload: dict[str, Any], expected: dict[str, Any]) -> None:
    if set(payload) != set(expected):
        raise ValueError("specialist packet fields differ")
    for field in set(expected) - {"cases", "paired_isolation"}:
        if payload[field] != expected[field]:
            raise ValueError(f"specialist review binding differs: {field}")
    for section in ("cases", "paired_isolation"):
        rows = payload[section]
        if not isinstance(rows, list) or len(rows) != len(expected[section]):
            raise ValueError("specialist review rows differ")
        for row, template in zip(rows, expected[section], strict=True):
            if set(row) != set(template):
                raise ValueError("specialist review fields differ")
            for field in set(template) - MUTABLE_ROW - {"dimensions"}:
                if row[field] != template[field]:
                    raise ValueError(f"specialist row binding differs: {field}")
            if set(row["dimensions"]) != set(template["dimensions"]):
                raise ValueError("specialist dimensions differ")
            decided = False
            for name, dimension in row["dimensions"].items():
                target = template["dimensions"][name]
                if (
                    set(dimension) != set(target)
                    or any(dimension[field] != target[field] for field in set(target) - {"checks"})
                    or len(dimension["checks"]) != len(target["checks"])
                ):
                    raise ValueError("specialist dimension denominator or checks changed")
                for check, original in zip(dimension["checks"], target["checks"], strict=True):
                    if set(check) != set(original) or any(
                        check[field] != original[field] for field in ("check_id", "criterion")
                    ):
                        raise ValueError("specialist check criterion changed")
                    if check["status"] not in {"pass", "fail", "unknown"}:
                        raise ValueError("specialist check status invalid")
                    if not isinstance(check["reason"], str) or len(check["reason"].strip()) < 2:
                        raise ValueError("specialist check needs a reason")
                    decided |= check["status"] != "unknown"
            if decided:
                if (
                    row["basis"] not in {"agent_review", "human_review"}
                    or not (isinstance(row["reviewer"], str) and row["reviewer"].strip())
                    or not isinstance(row["reviewed_at"], str)
                ):
                    raise ValueError("specialist decisions require reviewer, basis and timestamp")
                date = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
                if date.tzinfo is None:
                    raise ValueError("specialist review timestamp must include timezone")


def _metric(numerator: float | None, denominator: int, reason: str | None = None) -> dict[str, Any]:
    available = numerator is not None and reason is None and denominator > 0
    return {
        "value": numerator / denominator if available and numerator is not None else None,
        "evaluable": available,
        "numerator": numerator if available else None,
        "denominator": denominator,
        "expected_denominator": denominator,
        "reason": reason if not available else None,
    }


def _approved(case: dict[str, Any]) -> bool:
    return HumanReview.model_validate(case.get("human_review", {})).status == "approved"


def _review_metric(
    case: dict[str, Any],
    row: dict[str, Any],
    dimension: dict[str, Any],
    mode: str,
    trace_reason: str | None = None,
) -> dict[str, Any]:
    reason = trace_reason
    if mode == "approved" and (not _approved(case) or row.get("basis") != "human_review"):
        reason = "human_case_and_specialist_review_required"
    if not reason and any(check["status"] == "unknown" for check in dimension["checks"]):
        reason = "unknown_specialist_checks"
    metric = _metric(
        sum(check["status"] == "pass" for check in dimension["checks"]),
        dimension["denominator"],
        reason,
    )
    metric["check_ids"] = [check["check_id"] for check in dimension["checks"]]
    return metric


def _trace_reason(name: str, raw: dict[str, Any]) -> str | None:
    answer = raw.get("answer") or {}
    if "context_selection" in name and not raw.get("generation_contexts"):
        return "generation_context_not_captured"
    if any(
        part in name for part in ("query_understanding", "understanding_and_routing", "routing")
    ):
        if not answer.get("query_plan") and not raw.get("production_stages"):
            return "query_understanding_trace_unavailable"
    elif not isinstance(answer.get("answer"), str) or not answer["answer"].strip():
        return "answer_not_captured"
    return None


def _report_case(report: dict[str, Any], cid: str) -> dict[str, Any]:
    return next((row for row in report.get("cases", []) if row["case_id"] == cid), {})


def _process_case(report: dict[str, Any], cid: str) -> dict[str, Any]:
    return next(
        (
            row
            for row in report.get("process_summary", {}).get("per_case", [])
            if row["case_id"] == cid
        ),
        {},
    )


def _paired_reason(cid: str, raw: dict[str, dict[str, Any]]) -> str | None:
    treatment = raw.get(f"{cid}::with_history")
    control = raw.get(f"{cid}::without_history_control")
    if not treatment or not control:
        return "paired_arm_missing"
    a, b = treatment.get("request", {}), control.get("request", {})
    if (
        not a.get("history")
        or b.get("history") != []
        or any(a.get(field) != b.get(field) for field in ("question", "top_k", "session_id"))
    ):
        return "paired_inputs_not_controlled"
    if any(
        not (arm.get("answer") or {}).get("query_plan")
        or not any(stage.get("status") == "ok" for stage in arm.get("production_stages", []))
        for arm in (treatment, control)
    ):
        return "paired_plan_or_production_trace_unavailable"
    return None


def _delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    a, b = left.get("value"), right.get("value")
    comparable = left.get("evaluable") is True and right.get("evaluable") is True
    comparable &= a is not None and b is not None
    comparable &= left.get("denominator") == right.get("denominator")
    return {
        "with_history": left,
        "without_history_control": right,
        "difference_with_minus_without": a - b
        if comparable and isinstance(a, (int, float)) and isinstance(b, (int, float))
        else None,
        "comparable": bool(comparable),
        "reason": None if comparable else "paired_metric_missing_or_denominator_differs",
    }


def _paired_quality(cid: str, main: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for mode in MODES:
        a = (
            _report_case(main, cid)
            .get("generation_assessment", {})
            .get(mode, {})
            .get("metrics", {})
        )
        b = (
            _report_case(control, cid)
            .get("generation_assessment", {})
            .get(mode, {})
            .get("metrics", {})
        )
        result[mode] = {
            name: _delta(a.get(name, {}), b.get(name, {}))
            for name in ("required_fact_recall", "citation_support", "answer_pass")
        }
        pa = _process_case(main, cid).get("production_phase_union_diagnostics", {}).get(mode, {})
        pb = _process_case(control, cid).get("production_phase_union_diagnostics", {}).get(mode, {})
        result[mode].update(
            {
                name: _delta(pa.get(name, {}), pb.get(name, {}))
                for name in (BRANCH_UNION, SOURCE_UNION, LAST_CONTEXT)
            }
        )
    return result


def _year_groups(
    years: list[dict[str, Any]], metric: dict[str, Any], matched: list[str] | None
) -> dict[str, Any]:
    reason = (
        None
        if metric.get("evaluable") and matched is not None
        else (metric.get("reason") or "stage_group_diagnostics_unavailable")
    )
    matched_ids = set(matched or [])
    rows = [
        {
            "year": year["year"],
            "required_group_ids": year["required_evidence_group_ids"],
            "required_group_recall": _metric(
                len(matched_ids & set(year["required_evidence_group_ids"])),
                len(year["required_evidence_group_ids"]),
                reason,
            ),
        }
        for year in years
    ]
    return {
        "years": rows,
        "year_hit_rate": _metric(
            sum(bool(matched_ids & set(year["required_evidence_group_ids"])) for year in years),
            len(years),
            reason,
        ),
        "year_macro_recall": _metric(
            sum(row["required_group_recall"]["value"] or 0 for row in rows),
            len(years),
            reason,
        ),
    }


def _year_answers(years: list[dict[str, Any]], assessment: dict[str, Any]) -> dict[str, Any]:
    statuses = assessment.get("fact_statuses") or {}
    aggregate_reason = assessment.get("metrics", {}).get("required_fact_recall", {}).get("reason")
    # Unknowns in one year do not erase a fully reviewed different year. Formal
    # review gates still apply to every year, including apparently known facts.
    gate = aggregate_reason if aggregate_reason not in {None, "unknown_fact_judgments"} else None
    rows = []
    for year in years:
        ids = year["required_fact_ids"]
        reason = gate or (
            "unknown_year_fact_judgments"
            if any(
                statuses.get(fid, "unknown")
                not in {"covered", "partial", "missing", "contradicted"}
                for fid in ids
            )
            else None
        )
        rows.append(
            {
                "year": year["year"],
                "required_fact_ids": ids,
                "required_fact_recall": _metric(
                    sum(statuses.get(fid) == "covered" for fid in ids), len(ids), reason
                ),
            }
        )
    incomplete = any(not row["required_fact_recall"]["evaluable"] for row in rows)
    reason = "incomplete_fixed_year_review" if incomplete else None
    complete = sum(row["required_fact_recall"]["value"] == 1 for row in rows)
    return {
        "years": rows,
        "complete_years": _metric(complete, len(years), reason),
        "year_macro_fact_recall": _metric(
            sum(row["required_fact_recall"]["value"] or 0 for row in rows),
            len(years),
            reason,
        ),
    }


def _yearly(
    case: dict[str, Any], protocol: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any] | None:
    boundary = (protocol.get("specialist_protocol") or {}).get("answer_boundary", {})
    years = boundary.get("years")
    if not years:
        return None
    if len({year["year"] for year in years}) != len(years) or (
        boundary.get("year_coverage_denominator") != len(years)
    ):
        raise ValueError("fixed year denominator differs from protocol")
    for key, items in (
        ("required_fact_ids", case["facts"]),
        ("required_evidence_group_ids", case["evidence_groups"]),
    ):
        ids = [item for year in years for item in year[key]]
        if len(ids) != len(set(ids)) or set(ids) != {item["id"] for item in items}:
            raise ValueError("yearly fact/group partition differs from case definition")
    row = _report_case(report, case["id"])
    process = _process_case(report, case["id"])
    components = []
    for stage in row.get("stages", []):
        for mode in MODES:
            details = stage.get(mode, {})
            for k, diagnostics in details.get("diagnostics", {}).get("at_k", {}).items():
                components.append(
                    {
                        "stage": stage["stage"],
                        "scope": stage.get("scope"),
                        "k": int(k),
                        "mode": mode,
                        **_year_groups(
                            years,
                            details.get("metrics", {}).get(f"required_group_recall@{k}", {}),
                            diagnostics.get("matched_groups"),
                        ),
                    }
                )
    return {
        "case_id": case["id"],
        "independent_case_count": 1,
        "year_denominator": len(years),
        "stage_metrics": components,
        "production_metrics": {
            mode: {
                name: _year_groups(years, metric, metric.get("matched_groups"))
                for name, metric in process.get("production_phase_union_diagnostics", {})
                .get(mode, {})
                .items()
            }
            for mode in MODES
        },
        "answer_metrics": {
            mode: _year_answers(years, row.get("generation_assessment", {}).get(mode, {}))
            for mode in MODES
        },
    }


def evaluate_specialist_reviews(
    payload: dict[str, Any] | None,
    cases: list[dict[str, Any]],
    protocols: dict[str, Any],
    capture: dict[str, Any],
    main_report: dict[str, Any],
    control_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Score bound explicit reviews and already validated stage/fact observations."""
    expected = prepare_specialist_reviews(cases, protocols, capture)
    packet = deepcopy(expected) if payload is None else payload
    _validate_packet(packet, expected)
    by_case = {case["id"]: case for case in cases}
    by_protocol = _protocol_map(protocols)
    raw = _raw_map([*capture.get("cases", []), *capture.get("control_cases", [])])
    rows = []
    for row in packet["cases"]:
        observation = raw[f"{row['case_id']}::{row['input_variant_id']}"]
        rows.append(
            {
                "case_id": row["case_id"],
                "input_variant_id": row["input_variant_id"],
                "basis": row["basis"],
                "dimensions": {
                    name: {
                        "checks": dimension["checks"],
                        **{
                            mode: _review_metric(
                                by_case[row["case_id"]],
                                row,
                                dimension,
                                mode,
                                _trace_reason(name, observation),
                            )
                            for mode in MODES
                        },
                    }
                    for name, dimension in row["dimensions"].items()
                },
            }
        )
    pairs = []
    for row in packet["paired_isolation"]:
        cid = row["case_id"]
        control = control_reports.get("without_history_control", control_reports.get(cid, {}))
        pairs.append(
            {
                "case_id": cid,
                "independent_case_count": 1,
                "checks": row["dimensions"]["history_isolation"]["checks"],
                "isolation": {
                    mode: _review_metric(
                        by_case[cid],
                        row,
                        row["dimensions"]["history_isolation"],
                        mode,
                        _paired_reason(cid, raw),
                    )
                    for mode in MODES
                },
                "quality": _paired_quality(cid, main_report, control),
                "caveat": "Paired quality differences are diagnostic; one run does not "
                "establish history leakage.",
            }
        )
    yearly = [_yearly(case, by_protocol.get(case["id"], {}), main_report) for case in cases]
    return {
        "schema_version": 1,
        "rubric_version": RUBRIC_VERSION,
        "review_sha256": fingerprint(payload) if payload else None,
        "cases": rows,
        "paired_cases": pairs,
        "yearly_cases": [row for row in yearly if row is not None],
        "aggregation_policy": "Separate diagnostic strata; controls and years never increase "
        "the independent-case denominator.",
    }
