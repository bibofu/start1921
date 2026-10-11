"""Compare evaluation scores separately from evidence for experiment isolation."""

from __future__ import annotations

import re
from typing import Any, TypeGuard

from history_agent.evaluation.pilot_answers import fingerprint

BRANCH_STAGE = re.compile(r"(?:production_\d+_)?(keyword|vector)_candidates\Z")
CHUNKING_FIELDS = ("version", "target_chars", "max_chars", "overlap")
COMMON_IDENTITY_FIELDS = (
    "chunk_artifact_sha256",
    "index_artifact_sha256",
    "build_run_id",
    "git_commit",
)


def _known(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and value != "" and value != [] and value != {}


def _known_text(value: Any) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _positive_integer(value: Any) -> bool:
    return type(value) is int and value > 0


def _case_ids(report: dict[str, Any], side: str) -> tuple[list[str], list[str]]:
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases:
        return [], [f"{side}: cases are missing or invalid"]
    ids = []
    reasons = []
    for case in cases:
        case_id = _mapping(case).get("case_id")
        if not _known_text(case_id):
            reasons.append(f"{side}: a case ID is missing or invalid")
        else:
            ids.append(case_id)
    if len(ids) != len(set(ids)):
        reasons.append(f"{side}: duplicate case IDs")
    return ids, reasons


def _mode_branches(mode: Any) -> list[str]:
    if not isinstance(mode, str):
        return []
    if "keyword_only" in mode:
        return ["keyword"]
    if "vector_only" in mode:
        return ["vector"]
    if "hybrid" in mode:
        return ["keyword", "vector"]
    return [branch for branch in ("keyword", "vector") if branch in mode]


def _branch_usage(report: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Use successful traces, not fingerprint keys (failed branches have keys too)."""
    usage: dict[str, Any] = {}
    issues: list[str] = []
    cases = report.get("cases")
    for case in cases if isinstance(cases, list) else []:
        case = _mapping(case)
        case_id = case.get("case_id")
        if not _known_text(case_id):
            issues.append("case branch usage has an invalid case ID")
            continue
        if case_id in usage:
            issues.append(f"{case_id}: duplicate case branch usage")
            continue
        component: set[str] = set()
        production: set[str] = set()
        stages = case.get("stages")
        if stages is not None and not isinstance(stages, list):
            issues.append(f"{case_id}: stage records are invalid")
        for stage in stages if isinstance(stages, list) else []:
            stage = _mapping(stage)
            name = stage.get("stage", "")
            if not _known_text(name):
                issues.append(f"{case_id}: a stage name is missing or invalid")
                continue
            match = BRANCH_STAGE.fullmatch(name)
            # Scored reports contain only successful stages; raw status, if present,
            # must also be successful before it can establish actual branch use.
            if match and stage.get("status", "ok") == "ok":
                target = production if name.startswith("production_") else component
                target.add(match.group(1))
        answer = _mapping(case.get("answer"))
        mode = answer.get("retrieval_mode")
        # The final mode identifies branches only when no detailed production
        # trace survived. A failed vector branch must not become active merely
        # because a generic hybrid mode was retained by the answer object.
        if not production:
            production.update(_mode_branches(mode))
        if not component:
            issues.append(f"{case_id}: successful component branch usage is missing")
        usage[case_id] = {"component": sorted(component), "production": sorted(production)}
    if not usage:
        issues.append("case branch usage is missing")
    return usage, issues


def _index_identity(report: dict[str, Any]) -> dict[str, Any]:
    usage, issues = _branch_usage(report)
    branches = sorted({branch for case in usage.values() for v in case.values() for branch in v})
    metadata = _mapping(report.get("index_metadata"))
    reports = _mapping(metadata.get("reports"))
    identities: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for branch in branches:
        raw = _mapping(reports.get(f"{branch}_index"))
        manifest = raw.get("manifest")
        if not isinstance(manifest, dict):
            missing.append(f"{branch}.manifest")
            continue
        fields: tuple[str, ...] = (*COMMON_IDENTITY_FIELDS, f"{branch}_index_version")
        if branch == "vector":
            fields = (*fields, "embedding_model")
        identity = {key: manifest.get(key) for key in fields}
        for field in fields:
            if not _known_text(identity[field]):
                missing.append(f"{branch}.{field}")
        chunking = manifest.get("chunking")
        identity["chunking"] = chunking if isinstance(chunking, dict) else None
        for field in CHUNKING_FIELDS:
            value = _mapping(chunking).get(field)
            valid = (
                _known_text(value)
                if field == "version"
                else type(value) is int and value >= (0 if field == "overlap" else 1)
            )
            if not valid:
                missing.append(f"{branch}.chunking.{field}")
        # Build provenance is an additional identity when supplied by the index
        # builder; old manifests are not required to invent a chunk build ID.
        if "chunk_build_run_id" in manifest:
            identity["chunk_build_run_id"] = manifest["chunk_build_run_id"]
            if not _known_text(manifest["chunk_build_run_id"]):
                missing.append(f"{branch}.chunk_build_run_id")
        actual = raw.get("actual_index_artifact_sha256")
        identity["actual_index_artifact_sha256"] = actual
        if not _known_text(actual):
            missing.append(f"{branch}.actual_index_artifact_sha256")
        if raw.get("artifact_verified") is not True:
            issues.append(f"{branch}: queried index artifact was not verified")
        if _known(actual) and actual != manifest.get("index_artifact_sha256"):
            issues.append(f"{branch}: actual artifact hash disagrees with manifest")
        summary = _mapping(raw.get("summary"))
        if raw.get("summary") is not None and not isinstance(raw["summary"], dict):
            issues.append(f"{branch}: index summary is invalid")
        summary_fields = {
            "run_id": "build_run_id",
            "index_version": f"{branch}_index_version",
        }
        if branch == "vector":
            summary_fields["model_name"] = "embedding_model"
        for summary_key, manifest_key in summary_fields.items():
            if _known(summary.get(summary_key)) and summary[summary_key] != manifest.get(
                manifest_key
            ):
                issues.append(f"{branch}: summary.{summary_key} disagrees with manifest")
        identities[branch] = identity
    if len(identities) > 1:
        first = next(iter(identities.values()))
        for field in ("chunk_artifact_sha256", "chunking"):
            if any(identity.get(field) != first.get(field) for identity in identities.values()):
                issues.append(f"active retrieval branches have different {field}")
    if report.get("degraded_cases"):
        issues.append("one or more cases used degraded component retrieval")
    attribution = _mapping(report.get("index_attribution"))
    if attribution.get("attribution_safe") is not True:
        issues.append("captured index attribution was unsafe or not recorded")
        captured_reasons = attribution.get("attribution_unsafe_reasons")
        if isinstance(captured_reasons, list):
            issues.extend(str(reason) for reason in captured_reasons)
    return {
        "branches": branches,
        "case_branch_usage": usage,
        "identities": identities,
        "missing": missing,
        "issues": list(dict.fromkeys(issues)),
    }


def _identity_differences(left: Any, right: Any, prefix: str = "") -> dict[str, Any]:
    """Keep missing-vs-present differences, including explicit null values."""
    if isinstance(left, dict) and isinstance(right, dict):
        changes: dict[str, Any] = {}
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                changes[path] = [left.get(key), right.get(key)]
            else:
                changes.update(_identity_differences(left[key], right[key], path))
        return changes
    return {prefix: [left, right]} if left != right else {}


def _compare_index_identity(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    a, b = _index_identity(left), _index_identity(right)
    changes = _identity_differences(a["identities"], b["identities"])
    usage_equal = a["case_branch_usage"] == b["case_branch_usage"]
    complete = not any(item["missing"] or item["issues"] for item in (a, b))
    return {
        "left": a,
        "right": b,
        "changes": changes,
        "branch_usage_equal": usage_equal,
        "metadata_complete_and_verified": complete,
        "equal": (not changes and usage_equal) if complete else None,
    }


def _candidate_pools_equal(
    left: dict[str, Any], right: dict[str, Any], index_comparison: dict[str, Any]
) -> bool | None:
    pools = []
    for side, report in (("left", left), ("right", right)):
        fingerprints = _mapping(report.get("component_candidate_fingerprints"))
        active = {}
        for case_id, usage in index_comparison[side]["case_branch_usage"].items():
            branches = usage["component"]
            case_pool = _mapping(fingerprints.get(case_id))
            if not branches or any(
                not _known_text(case_pool.get(f"{branch}_candidates")) for branch in branches
            ):
                return None
            active[case_id] = {branch: case_pool[f"{branch}_candidates"] for branch in branches}
        if not active:
            return None
        pools.append(active)
    return bool(pools[0] == pools[1])


def _answer_calibration_comparison(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """Keep answer review policy identity separate from retrieval comparability."""
    values = [report.get("answer_calibration_sha256") for report in (left, right)]
    reasons = []
    for side, value in zip(("left", "right"), values, strict=True):
        if value is not None and (
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        ):
            reasons.append(f"{side}: answer_calibration_sha256 is invalid")
    if values[0] != values[1]:
        reasons.append("answer_calibration_sha256 differs")
    return {
        "compatible": not reasons,
        "left": values[0],
        "right": values[1],
        "reasons": reasons,
    }


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = ("evaluator_version", "dataset_sha256", "corpus_sha256", "k_values")
    reasons = []
    for key in keys:
        if not _known(left.get(key)) or not _known(right.get(key)):
            reasons.append(f"{key} is missing")
        elif left[key] != right[key]:
            reasons.append(f"{key} differs")
    if "execution_contract" in left or "execution_contract" in right:
        contracts = [report.get("execution_contract") for report in (left, right)]
        if any(not isinstance(contract, dict) or not contract for contract in contracts):
            reasons.append("execution_contract is missing or invalid")
        elif fingerprint(contracts[0]) != fingerprint(contracts[1]):
            reasons.append("execution_contract differs")
    if "control_variant_id" in left or "control_variant_id" in right:
        variants = [report.get("control_variant_id") for report in (left, right)]
        if not all(_known_text(variant) for variant in variants):
            reasons.append("control_variant_id is missing or invalid")
        elif variants[0] != variants[1]:
            reasons.append("control_variant_id differs")
    left_ids, left_case_reasons = _case_ids(left, "left")
    right_ids, right_case_reasons = _case_ids(right, "right")
    reasons.extend([*left_case_reasons, *right_case_reasons])
    if left_ids != right_ids:
        reasons.append("case IDs differ")
    metrics = {}
    for name in sorted(set(left["provisional_aggregate"]) & set(right["provisional_aggregate"])):
        a, b = left["provisional_aggregate"][name], right["provisional_aggregate"][name]
        valid = not reasons and a["evaluable_case_ids"] == b["evaluable_case_ids"]
        valid = valid and a["value"] is not None and b["value"] is not None
        if ".pool_ndcg@" in name:
            fingerprints = a.get("pool_fingerprints") or {}
            valid = (
                valid
                and bool(fingerprints)
                and all(fingerprints.get(case_id) for case_id in a["evaluable_case_ids"])
                and fingerprints == b.get("pool_fingerprints")
            )
        metrics[name] = {
            "comparable": valid,
            "delta": b["value"] - a["value"] if valid else None,
            "left_cases": a["evaluable_case_ids"],
            "right_cases": b["evaluable_case_ids"],
        }
    changes = {
        key: [left["config"].get(key), right["config"].get(key)]
        for key in sorted(set(left["config"]) | set(right["config"]))
        if left["config"].get(key) != right["config"].get(key)
    }
    answer_metrics = {}
    answer_calibration = _answer_calibration_comparison(left, right)
    for name in sorted(
        set(left.get("provisional_answer_aggregate", {}))
        & set(right.get("provisional_answer_aggregate", {}))
    ):
        a = left["provisional_answer_aggregate"][name]
        b = right["provisional_answer_aggregate"][name]
        bases = a.get("review_bases") or {}
        case_ids = a.get("evaluable_case_ids") or []
        units = a.get("evaluable_unit_ids") or []
        valid = (
            not reasons
            and answer_calibration["compatible"]
            and bool(left.get("answer_rubric_version"))
            and left.get("answer_rubric_version") == right.get("answer_rubric_version")
            and bool(units)
            and bool(case_ids)
            and units == b.get("evaluable_unit_ids")
            and case_ids == b.get("evaluable_case_ids")
            and bases == b.get("review_bases")
            and all(bases.get(case_id) in {"agent_review", "human_review"} for case_id in case_ids)
            and a["value"] is not None
            and b["value"] is not None
        )
        answer_metrics[name] = {
            "comparable": valid,
            "delta": b["value"] - a["value"] if valid else None,
            "left_units": a.get("evaluable_unit_ids", []),
            "right_units": b.get("evaluable_unit_ids", []),
        }
    index_comparison = _compare_index_identity(left, right)
    pools_equal = _candidate_pools_equal(left, right, index_comparison)
    attribution_reasons = []
    for side, report in (("left", left), ("right", right)):
        for key in ("candidate_k", "top_k"):
            if not _positive_integer(report["config"].get(key)):
                attribution_reasons.append(f"{side}: component config.{key} is missing or invalid")
    if set(changes) - {"top_k"}:
        attribution_reasons.append(
            "Pilot isolation currently verifies only Top-K or repeated-control experiments"
        )
    if pools_equal is not True:
        attribution_reasons.append("Isolation requires identical ordered branch candidates")
    if not _known_text(left.get("source_sha256")) or left.get("source_sha256") != right.get(
        "source_sha256"
    ):
        attribution_reasons.append("Isolation requires identical captured source code")
    for side in ("left", "right"):
        identity = index_comparison[side]
        for field in identity["missing"]:
            attribution_reasons.append(f"{side}: active index identity is missing {field}")
        attribution_reasons.extend(f"{side}: {issue}" for issue in identity["issues"])
    if not index_comparison["branch_usage_equal"]:
        attribution_reasons.append("Actual per-case retrieval branch usage differs")
    for field in index_comparison["changes"]:
        attribution_reasons.append(f"Active index identity differs: {field}")
    return {
        "compatible": not reasons,
        "reasons": reasons,
        "config_changes": changes,
        "basis": "provisional_agent_review",
        "metrics": metrics,
        "answer_metrics": answer_metrics,
        "answer_calibration_comparison": answer_calibration,
        "ordered_branch_candidates_equal": pools_equal,
        "index_identity_comparison": index_comparison,
        "attribution_scope": "component_retrieval",
        "attribution_note": (
            "Isolation applies to component Top-K or repeated-control comparisons. "
            "Production retrieval uses independent budgets; this does not attribute "
            "stochastic answer changes to component Top-K."
        ),
        "attribution_unsafe_reasons": list(dict.fromkeys(attribution_reasons)),
        "attribution_safe": not reasons and not attribution_reasons,
    }
