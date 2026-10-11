from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from history_agent.evaluation.pilot import score
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_review_bundle import import_reviews, read_bundle
from history_agent.evaluation.pilot_workflow import build_review_artifacts, prepare_reviews
from test_pilot_development_execution import DATASET, PROTOCOLS, _fake_collection
from test_pilot_scoring_v2 import _scoring_inputs


def _write(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")
    return path


def _legacy_bundle(work_path: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    paths = _scoring_inputs(work_path)
    files = build_review_artifacts(paths["dataset"], paths["capture"])
    return paths, files["review_bundle.json"]


def _identity(row: dict[str, Any]) -> None:
    row.update(
        basis="agent_review", reviewer="synthetic-reviewer", reviewed_at="2026-10-11T12:00:00+08:00"
    )


def test_unknown_bundle_roundtrip_keeps_all_pending_and_scores_na(work_path: Path) -> None:
    paths, bundle = _legacy_bundle(work_path)
    original_dataset = paths["dataset"].read_bytes()
    original_capture = paths["capture"].read_bytes()
    prepared = work_path / "prepared"
    prepare_reviews(paths["dataset"], paths["capture"], prepared)
    assert (prepared / "index.html").is_file()
    assert (prepared / "calibration.json").is_file()
    assert read_bundle(prepared / "review_bundle.json") == bundle
    imported = work_path / "imported"
    result = import_reviews(
        paths["dataset"], paths["capture"], prepared / "review_bundle.json", imported
    )
    assert result["review_files"] == 2
    answer = json.loads((imported / "answer_reviews.json").read_text(encoding="utf8"))
    assert answer["calibration_sha256"] == bundle["calibration_sha256"]
    assert answer["cases"][0]["basis"] is None
    assert answer["cases"][0]["facts"][0]["status"] == "unknown"
    assert all(d["status"] == "unknown" for d in answer["cases"][0]["dimensions"].values())
    report = score(paths["dataset"], paths["capture"], paths["output"], reviews_dir=imported)
    assert report["provisional_answer_aggregate"]["required_fact_recall"]["value"] is None
    assert report["approved_answer_aggregate"]["answer_pass"]["value"] is None
    assert report["cases"][0]["human_review"]["status"] == "pending"
    assert paths["dataset"].read_bytes() == original_dataset
    assert paths["capture"].read_bytes() == original_capture


@pytest.mark.parametrize("status,expected_recall", [("covered", 1.0), ("partial", 0.0)])
def test_one_explicit_fact_import_preserves_other_pending_judgments(
    work_path: Path, status: str, expected_recall: float
) -> None:
    paths, bundle = _legacy_bundle(work_path)
    row = bundle["files"]["answer_reviews.json"]["cases"][0]
    _identity(row)
    row["facts"][0].update(
        status=status,
        reason="测试用明确复核，正文职务表达及交付引用分别核对。",
        answer_excerpt="他出任总理。",
        cited_evidence_ids=["E1"],
        support_status="supported",
    )
    bundle["exported_at"] = "2026-10-11T04:01:00Z"
    imported = work_path / "imported"
    import_reviews(
        paths["dataset"], paths["capture"], _write(work_path / "bundle.json", bundle), imported
    )
    report = score(paths["dataset"], paths["capture"], paths["output"], reviews_dir=imported)
    assessment = report["cases"][0]["generation_assessment"]
    assert assessment["provisional"]["metrics"]["required_fact_recall"]["value"] == expected_recall
    assert assessment["provisional"]["metrics"]["citation_support"]["value"] is None
    assert assessment["approved"]["metrics"]["required_fact_recall"]["value"] is None
    process = json.loads((imported / "process_reviews.json").read_text(encoding="utf8"))
    assert process["cases"][0]["status"] == "unknown"
    assert process["cases"][0]["basis"] is None


@pytest.mark.parametrize(
    "change",
    [
        "capture_hash",
        "dataset_hash",
        "calibration_hash",
        "template_hash",
        "answer_hash",
        "question",
        "process_snapshot",
        "process_denominator",
        "missing_row",
        "duplicate_row",
        "extra_path",
        "missing_file",
        "new_field",
        "naive_export_time",
    ],
)
def test_immutable_bundle_changes_rejected_before_output(work_path: Path, change: str) -> None:
    paths, bundle = _legacy_bundle(work_path)
    answer = bundle["files"]["answer_reviews.json"]["cases"][0]
    process = bundle["files"]["process_reviews.json"]["cases"][0]
    if change in {"capture_hash", "dataset_hash", "calibration_hash", "template_hash"}:
        bundle[change.replace("_hash", "_sha256")] = "0" * 64
    elif change == "answer_hash":
        answer["answer_sha256"] = "0" * 64
    elif change == "question":
        answer["question"] = "Changed question cannot be smuggled into a review."
    elif change == "process_snapshot":
        process["executed_query_plan"] = {"normalized_question": "Changed observation"}
    elif change == "process_denominator":
        process["denominator"] = 2
    elif change == "missing_row":
        bundle["files"]["answer_reviews.json"]["cases"].clear()
    elif change == "duplicate_row":
        bundle["files"]["answer_reviews.json"]["cases"].append(deepcopy(answer))
    elif change == "extra_path":
        bundle["files"]["../outside.json"] = deepcopy(bundle["files"]["answer_reviews.json"])
    elif change == "missing_file":
        del bundle["files"]["process_reviews.json"]
    elif change == "new_field":
        bundle["force_approve"] = True
    elif change == "naive_export_time":
        bundle["exported_at"] = "2026-10-11T12:00:00"
    output = work_path / "rejected"
    with pytest.raises(ValueError):
        import_reviews(
            paths["dataset"], paths["capture"], _write(work_path / "bundle.json", bundle), output
        )
    assert not output.exists()
    assert not (work_path / "outside.json").exists()


@pytest.mark.parametrize(
    "change", ["invented_excerpt", "missing_excerpt", "invented_citation", "no_identity"]
)
def test_decisions_require_actual_answer_evidence_and_review_identity(
    work_path: Path, change: str
) -> None:
    paths, bundle = _legacy_bundle(work_path)
    row = bundle["files"]["answer_reviews.json"]["cases"][0]
    _identity(row)
    row["facts"][0].update(
        status="covered",
        reason="逐项核对测试回答。",
        answer_excerpt="他出任总理。",
        cited_evidence_ids=["E1"],
        support_status="supported",
    )
    if change == "invented_excerpt":
        row["facts"][0]["answer_excerpt"] = "他出任副总理。"
    elif change == "missing_excerpt":
        row["facts"][0]["answer_excerpt"] = None
    elif change == "invented_citation":
        row["facts"][0]["cited_evidence_ids"] = ["E99"]
    else:
        row["basis"] = None
    output = work_path / "rejected"
    with pytest.raises(ValueError):
        import_reviews(
            paths["dataset"], paths["capture"], _write(work_path / "bundle.json", bundle), output
        )
    assert not output.exists()


def test_existing_review_directory_is_never_overwritten(work_path: Path) -> None:
    paths, bundle = _legacy_bundle(work_path)
    output = work_path / "existing"
    output.mkdir()
    marker = output / "answer_reviews.json"
    marker.write_text("human work in progress", encoding="utf8")
    with pytest.raises(FileExistsError):
        import_reviews(
            paths["dataset"], paths["capture"], _write(work_path / "bundle.json", bundle), output
        )
    assert marker.read_text(encoding="utf8") == "human work in progress"
    assert list(output.iterdir()) == [marker]


@pytest.mark.parametrize(
    "change", ["citation_na", "expressed_fact_support_na", "placeholder_reason"]
)
def test_pending_or_applicable_checks_cannot_be_hidden_by_na_or_template_reason(
    work_path: Path, change: str
) -> None:
    paths, bundle = _legacy_bundle(work_path)
    row = bundle["files"]["answer_reviews.json"]["cases"][0]
    _identity(row)
    if change == "citation_na":
        row["dimensions"]["citation_support"].update(
            status="not_applicable", reason="故意以N/A跳过已经交付的历史事实。"
        )
    else:
        row["facts"][0].update(status="covered", answer_excerpt="他出任总理。")
        if change == "expressed_fact_support_na":
            row["facts"][0].update(
                reason="故意跳过正文明确事实的支持核对。", support_status="not_applicable"
            )
    output = work_path / "rejected"
    with pytest.raises(ValueError):
        import_reviews(
            paths["dataset"], paths["capture"], _write(work_path / "bundle.json", bundle), output
        )
    assert not output.exists()


@pytest.mark.parametrize(
    "raw", ['{"files":{},"files":{}}', '{"files":{"a":{"status":"pass","status":"fail"}}}']
)
def test_duplicate_json_keys_are_rejected_even_when_nested(work_path: Path, raw: str) -> None:
    path = work_path / "duplicate.json"
    path.write_text(raw, encoding="utf8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        read_bundle(path)


@pytest.mark.parametrize(
    "change", ["missing_control", "swapped_answer", "swapped_process", "paired_denominator"]
)
def test_twenty_case_bundle_rejects_arm_or_specialist_mutation(
    work_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    _, capture_path, _ = _fake_collection(work_path, monkeypatch)
    bundle = build_review_artifacts(DATASET, capture_path, protocol_path=PROTOCOLS)[
        "review_bundle.json"
    ]
    control = "controls/without_history_control/"
    if change == "missing_control":
        for name in list(bundle["files"]):
            if name.startswith(control):
                del bundle["files"][name]
    elif change.startswith("swapped_"):
        name = change.removeprefix("swapped_") + "_reviews.json"
        bundle["files"][control + name] = deepcopy(bundle["files"][name])
    else:
        paired = bundle["files"]["specialist_reviews.json"]["paired_isolation"][0]
        paired["dimensions"]["history_isolation"]["denominator"] = 3
    output = work_path / "rejected"
    with pytest.raises(ValueError):
        import_reviews(
            DATASET,
            capture_path,
            _write(work_path / "bundle.json", bundle),
            output,
            protocol_path=PROTOCOLS,
        )
    assert not output.exists()


def test_twenty_case_bundle_preserves_main_control_and_specialist_pending_state(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, capture_path, _ = _fake_collection(work_path, monkeypatch)
    files = build_review_artifacts(DATASET, capture_path, protocol_path=PROTOCOLS)
    bundle = files["review_bundle.json"]
    assert len(bundle["files"]) == 5
    output = work_path / "imported"
    import_reviews(
        DATASET,
        capture_path,
        _write(work_path / "bundle.json", bundle),
        output,
        protocol_path=PROTOCOLS,
    )
    report = score(
        DATASET,
        capture_path,
        work_path / "report.json",
        protocols_path=PROTOCOLS,
        reviews_dir=output,
    )
    assert len(report["cases"]) == 20
    assert len(report["control_reports"]["without_history_control"]["cases"]) == 1
    assert report["execution_accounting"]["execution_count"] == 21
    assert report["provisional_answer_aggregate"]["required_fact_recall"]["value"] is None
    assert report["approved_answer_aggregate"]["answer_pass"]["value"] is None
    receipt = json.loads((output / "import_receipt.json").read_text(encoding="utf8"))
    assert receipt["bundle_sha256"] == fingerprint(bundle)
    for name, original in bundle["files"].items():
        assert json.loads((output / name).read_text(encoding="utf8")) == original


def test_partial_process_and_specialist_reviews_import_together_without_approving_answers(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, capture_path, _ = _fake_collection(work_path, monkeypatch)
    bundle = build_review_artifacts(DATASET, capture_path, protocol_path=PROTOCOLS)[
        "review_bundle.json"
    ]
    process = bundle["files"]["process_reviews.json"]["cases"][0]
    _identity(process)
    process.update(status="pass", reason="合成轨迹保留了本题的原始问题。")
    specialist = bundle["files"]["specialist_reviews.json"]["cases"][0]
    _identity(specialist)
    check = next(iter(specialist["dimensions"].values()))["checks"][0]
    check.update(status="fail", reason="合成测试未满足此项专项检查，不代表真实模型表现。")
    output = work_path / "imported"
    import_reviews(
        DATASET,
        capture_path,
        _write(work_path / "bundle.json", bundle),
        output,
        protocol_path=PROTOCOLS,
    )
    restored = read_bundle(output / "review_bundle.json")
    assert restored == bundle
    main = restored["files"]["answer_reviews.json"]
    assert all(row["basis"] is None for row in main["cases"])
    assert all(fact["status"] == "unknown" for row in main["cases"] for fact in row["facts"])


def test_protocol_path_labels_are_portable_but_actual_protocol_bytes_remain_bound(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, capture_path, _ = _fake_collection(work_path, monkeypatch)
    bundle = build_review_artifacts(DATASET, capture_path, protocol_path=PROTOCOLS)[
        "review_bundle.json"
    ]
    bundle["files"]["process_reviews.json"]["protocol_file"] = (
        "evals/golden/development_protocols_v3.json"
    )
    bundle["files"]["controls/without_history_control/process_reviews.json"]["protocol_file"] = (
        "../unavailable-on-this-machine/protocols.json"
    )
    supplied_protocol = work_path / "copied-protocols.json"
    supplied_protocol.write_bytes(PROTOCOLS.read_bytes())
    bundle_path = _write(work_path / "bundle.json", bundle)
    output = work_path / "imported"
    import_reviews(DATASET, capture_path, bundle_path, output, protocol_path=supplied_protocol)
    assert (output / "import_receipt.json").exists()
    report = score(
        DATASET,
        capture_path,
        work_path / "report.json",
        protocols_path=supplied_protocol,
        reviews_dir=output,
    )
    assert report["provisional_answer_aggregate"]["answer_pass"]["value"] is None
    supplied_protocol.write_bytes(PROTOCOLS.read_bytes() + b"\n")
    rejected = work_path / "changed-protocol-rejected"
    with pytest.raises(ValueError):
        import_reviews(
            DATASET, capture_path, bundle_path, rejected, protocol_path=supplied_protocol
        )
    assert not rejected.exists()
