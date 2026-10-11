"""Portable review edits, validated against regenerated immutable observations."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from history_agent.evaluation.pilot_answers import AnswerReviews, fingerprint, validate_reviews
from history_agent.evaluation.pilot_process_reviews import evaluate_process_reviews
from history_agent.evaluation.pilot_protocols import load_inputs
from history_agent.evaluation.pilot_specialist import validate_specialist_reviews
from history_agent.evaluation.pilot_variants import list_control_variants, project_control_capture

REVIEW_NAMES = {"answer_reviews.json", "process_reviews.json", "specialist_reviews.json"}
IDENTITY_FIELDS = {"basis", "reviewer", "reviewed_at"}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_bundle(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf8"), object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("review bundle must be an object")
    return value


def _portable(files: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(files)
    # The caller supplies the real protocol path. This saved path is only a label.
    for name, payload in result.items():
        if name.endswith("process_reviews.json"):
            payload["protocol_file"] = None
    return result


def make_review_bundle(
    files: dict[str, Any], calibration: dict[str, Any], *, protocol_sha256: str | None
) -> dict[str, Any]:
    reviews = {
        name: deepcopy(payload)
        for name, payload in files.items()
        if name.rsplit("/", 1)[-1] in REVIEW_NAMES
    }
    packet = files["review_packet.json"]
    return {
        "schema_version": 1,
        "kind": "pilot-review-bundle",
        "capture_sha256": packet["capture_sha256"],
        "dataset_sha256": packet["dataset_sha256"],
        "protocol_sha256": protocol_sha256,
        "calibration_sha256": fingerprint(calibration),
        "template_sha256": fingerprint(_portable(reviews)),
        "exported_at": None,
        "files": reviews,
    }


def _immutable(payload: dict[str, Any], name: str) -> dict[str, Any]:
    result = deepcopy(payload)
    if name.endswith("process_reviews.json"):
        result["protocol_file"] = None
    for section in ("cases", "paired_isolation"):
        for row in result.get(section, []):
            for field in IDENTITY_FIELDS:
                row.pop(field, None)
            if name.endswith("answer_reviews.json"):
                for fact in row["facts"]:
                    for field in (
                        "status",
                        "reason",
                        "answer_excerpt",
                        "cited_evidence_ids",
                        "support_status",
                    ):
                        fact.pop(field, None)
                for dimension in row["dimensions"].values():
                    dimension.pop("status", None)
                    dimension.pop("reason", None)
            elif name.endswith("process_reviews.json"):
                for field in ("status", "reason", "raw_planner_semantic_note"):
                    row.pop(field, None)
            else:
                for dimension in row["dimensions"].values():
                    for check in dimension["checks"]:
                        check.pop("status", None)
                        check.pop("reason", None)
    return result


def validate_bundle_structure(payload: dict[str, Any], expected: dict[str, Any]) -> None:
    """Allow decisions only, never edits to a question, hash, observation or denominator."""
    if set(payload) != set(expected):
        raise ValueError("review bundle fields differ")
    for key in set(expected) - {"files", "exported_at"}:
        if type(payload[key]) is not type(expected[key]) or payload[key] != expected[key]:
            raise ValueError(f"review bundle binding differs: {key}")
    if payload["exported_at"] is not None:
        value = payload["exported_at"]
        if (
            not isinstance(value, str)
            or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None
        ):
            raise ValueError("bundle export timestamp must include timezone")
    if not isinstance(payload["files"], dict) or set(payload["files"]) != set(expected["files"]):
        raise ValueError("review bundle files differ; retain every arm and unknown row")
    for name, original in expected["files"].items():
        try:
            immutable = _immutable(payload["files"][name], name)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"invalid review structure: {name}") from exc
        if fingerprint(immutable) != fingerprint(_immutable(original, name)):
            raise ValueError(f"immutable review fields changed: {name}")
        _check_reasons(payload["files"][name], original)


def _check_reasons(value: Any, original: Any) -> None:
    if isinstance(value, dict) and isinstance(original, dict):
        decided = (
            "status" in value
            and value["status"] != "unknown"
            or "support_status" in value
            and value["support_status"] != "unknown"
        )
        if decided and "reason" in original:
            reason = value.get("reason")
            if (
                not isinstance(reason, str)
                or len(reason.strip()) < 2
                or reason.strip() == original["reason"]
                or reason.strip().startswith(("待", "awaiting_"))
            ):
                raise ValueError("explicit decisions require a specific review reason")
        for key in set(value) & set(original):
            _check_reasons(value[key], original[key])
    elif isinstance(value, list) and isinstance(original, list):
        # Decision-row identities/lengths were checked above. Mutable citation ID
        # lists may grow; they have no nested reason fields and validate separately.
        for item, source in zip(value, original, strict=False):
            _check_reasons(item, source)


def import_reviews(
    dataset_path: Path,
    capture_path: Path,
    bundle_path: Path,
    output_dir: Path,
    *,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    """Validate the entire bundle before writing a fresh directory; never merge in place."""
    from history_agent.evaluation.pilot_calibration import validate_review_decisions
    from history_agent.evaluation.pilot_workflow import (
        build_review_artifacts,
        write_review_artifacts,
    )

    if output_dir.exists():
        raise FileExistsError("review output directory already exists")
    inputs = load_inputs(dataset_path, protocol_path)
    cases = [case.model_dump(mode="json") for case in inputs.dataset.cases]
    capture = json.loads(capture_path.read_text(encoding="utf8"))
    files = build_review_artifacts(dataset_path, capture_path, protocol_path=protocol_path)
    bundle = read_bundle(bundle_path)
    validate_bundle_structure(bundle, files["review_bundle.json"])
    arms = {"": capture}
    arms.update(
        {
            f"controls/{name}/": project_control_capture(capture, name)
            for name in list_control_variants(capture)
        }
    )
    for prefix, arm in arms.items():
        ids = {row["case_id"] for row in arm["cases"]}
        definitions = [case for case in cases if case["id"] in ids]
        answers = AnswerReviews.model_validate(bundle["files"][f"{prefix}answer_reviews.json"])
        validate_reviews(answers, arm, definitions)
        validate_review_decisions(answers, arm, definitions, inputs.protocols)
        evaluate_process_reviews(
            bundle["files"][f"{prefix}process_reviews.json"],
            definitions,
            arm,
            inputs.dataset_sha256,
            protocol_path=protocol_path,
        )
    if inputs.is_protocol_release:
        assert inputs.protocols is not None
        validate_specialist_reviews(
            bundle["files"]["specialist_reviews.json"], cases, inputs.protocols, capture
        )
    # Only allowlisted, regenerated paths are used; no path from the bundle is opened.
    files.update(deepcopy(bundle["files"]))
    files["review_bundle.json"] = bundle
    files["import_receipt.json"] = {
        "schema_version": 1,
        "bundle_sha256": fingerprint(bundle),
        "capture_sha256": bundle["capture_sha256"],
        "calibration_sha256": bundle["calibration_sha256"],
        "note": "Imported explicit reviews only; no Golden case approval is granted.",
    }
    write_review_artifacts(files, output_dir)
    return {"output_dir": str(output_dir), "review_files": len(bundle["files"])}
