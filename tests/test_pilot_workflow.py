import json
import subprocess
import sys
from pathlib import Path

import pytest
from history_agent.evaluation.pilot import collect, score
from history_agent.evaluation.pilot_answers import AnswerReviews
from history_agent.evaluation.pilot_workflow import prepare_reviews
from test_pilot_scoring_v2 import _scoring_inputs, _write


def test_prepare_then_score_unknown_reviews_is_offline_and_never_invents_judgments(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _scoring_inputs(work_path)

    def reject_live_call(*args: object, **kwargs: object) -> None:
        pytest.fail("offline workflow must not call Agent or retrieval")

    monkeypatch.setattr("history_agent.evaluation.pilot.answer_question", reject_live_call)
    monkeypatch.setattr("history_agent.evaluation.pilot.search_hybrid_index", reject_live_call)
    review_dir = work_path / "reviews"
    prepare_reviews(paths["dataset"], paths["capture"], review_dir)
    answers_path, process_path = (
        review_dir / "answer_reviews.json",
        review_dir / "process_reviews.json",
    )
    answers = json.loads(answers_path.read_text(encoding="utf8"))
    process = json.loads(process_path.read_text(encoding="utf8"))
    assert answers["cases"][0]["basis"] is None
    assert all(d["status"] == "unknown" for d in answers["cases"][0]["dimensions"].values())
    assert process["cases"][0]["status"] == "unknown"
    result = score(
        paths["dataset"],
        paths["capture"],
        paths["output"],
        (2, 1, 2),
        ranking_pools_path=paths["pools"],
        assessments_path=answers_path,
        process_reviews_path=process_path,
    )
    assert result["k_values"] == [1, 2]
    assert result["query_understanding"]["provisional_aggregate"]["value"] is None
    assert result["provisional_answer_aggregate"]["answer_pass"]["value"] is None
    assert result["process_summary"]["cost"]["all"]["tokens"]["total_tokens"]["value"] is None
    compact = json.loads(paths["output"].with_suffix(".summary.json").read_text(encoding="utf8"))
    assert compact["capture_sha256"] == result["capture_sha256"]
    assert compact["process_summary"] == result["process_summary"]
    assert "stages" not in compact["cases"][0]
    before = answers_path.read_bytes()
    with pytest.raises(FileExistsError):
        prepare_reviews(paths["dataset"], paths["capture"], review_dir)
    assert answers_path.read_bytes() == before


def test_fresh_template_rejects_unattributed_judgment(work_path: Path) -> None:
    paths = _scoring_inputs(work_path)
    review_dir = work_path / "reviews"
    prepare_reviews(paths["dataset"], paths["capture"], review_dir)
    data = json.loads((review_dir / "answer_reviews.json").read_text(encoding="utf8"))
    data["cases"][0]["facts"][0]["status"] = "covered"
    with pytest.raises(ValueError, match="require basis, reviewer"):
        AnswerReviews.model_validate(data)


@pytest.mark.parametrize("kind", ["answer", "process"])
def test_new_capture_cannot_reuse_old_reviews(work_path: Path, kind: str) -> None:
    paths = _scoring_inputs(work_path)
    review_dir = work_path / "reviews"
    prepare_reviews(paths["dataset"], paths["capture"], review_dir)
    capture = json.loads(paths["capture"].read_text(encoding="utf8"))
    capture["cases"][0]["answer"]["answer"] = "另一份回答"
    _write(paths["capture"], capture)
    kwargs = (
        {"assessments_path": review_dir / "answer_reviews.json"}
        if kind == "answer"
        else {"process_reviews_path": review_dir / "process_reviews.json"}
    )
    with pytest.raises(ValueError, match="different capture"):
        score(paths["dataset"], paths["capture"], paths["output"], **kwargs)
    assert not paths["output"].exists()


def test_score_cannot_overwrite_inputs_or_silently_drop_duplicate_capture(work_path: Path) -> None:
    paths = _scoring_inputs(work_path)
    original = paths["capture"].read_bytes()
    with pytest.raises(ValueError, match="overwrite an input"):
        score(paths["dataset"], paths["capture"], paths["capture"])
    assert paths["capture"].read_bytes() == original
    capture = json.loads(original)
    capture["cases"].append(capture["cases"][0])
    _write(paths["capture"], capture)
    with pytest.raises(ValueError, match="duplicate capture"):
        score(paths["dataset"], paths["capture"], paths["output"])


def test_cli_prepare_score_and_compare_offline(work_path: Path) -> None:
    paths = _scoring_inputs(work_path)
    reviews = work_path / "reviews"
    prefix = [sys.executable, "-B", "-m", "history_agent.evaluation.pilot"]
    common = ["--dataset", str(paths["dataset"]), "--capture", str(paths["capture"])]
    commands = [
        ["prepare-reviews", *common, "--output-dir", str(reviews)],
        [
            "score",
            *common,
            "--output",
            str(paths["output"]),
            "--k-values",
            "1",
            "2",
            "--ranking-pools",
            str(paths["pools"]),
            "--assessments",
            str(paths["assessments"]),
            "--process-reviews",
            str(reviews / "process_reviews.json"),
        ],
        [
            "compare",
            str(paths["output"]),
            str(paths["output"]),
            "--output",
            str(work_path / "comparison.json"),
        ],
    ]
    for command in commands:
        result = subprocess.run(prefix + command, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    comparison = json.loads((work_path / "comparison.json").read_text(encoding="utf8"))
    assert comparison["compatible"]
    assert not comparison["attribution_safe"]  # Synthetic capture has no verified index manifest.
    assert comparison["answer_metrics"]["answer_pass"]["comparable"]


def test_collect_protects_existing_capture_before_any_agent_work(work_path: Path) -> None:
    dataset, output = work_path / "dataset.json", work_path / "capture.json"
    dataset.write_text("dataset sentinel", encoding="utf8")
    with pytest.raises(ValueError, match="overwrite an input"):
        collect(dataset, dataset)
    output.with_suffix(".partial.json").write_text("partial sentinel", encoding="utf8")
    with pytest.raises(FileExistsError, match="already exists"):
        collect(dataset, output)
    assert dataset.read_text(encoding="utf8") == "dataset sentinel"
    assert output.with_suffix(".partial.json").read_text(encoding="utf8") == "partial sentinel"
