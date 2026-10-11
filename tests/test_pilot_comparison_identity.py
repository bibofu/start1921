from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from history_agent.evaluation.pilot_comparison import compare


def _report(*branches: str) -> dict[str, Any]:
    branches = branches or ("keyword", "vector")
    chunking = {"version": "chunk-v1", "target_chars": 650, "max_chars": 900, "overlap": 0}
    indexes = {}
    for branch in ("keyword", "vector"):
        indexes[f"{branch}_index"] = {
            "manifest": {
                "chunk_artifact_sha256": "chunks",
                "index_artifact_sha256": f"{branch}-artifact",
                "build_run_id": f"{branch}-build",
                "chunk_build_run_id": "chunks-build",
                "git_commit": "index-builder-commit",
                "chunking": deepcopy(chunking),
                f"{branch}_index_version": f"{branch}-v1",
                "embedding_model": "embedding-v1" if branch == "vector" else None,
            },
            "artifact_verified": True,
            "actual_index_artifact_sha256": f"{branch}-artifact",
        }
    return {
        "evaluator_version": "reviewable-pilot-v2",
        "dataset_sha256": "dataset",
        "corpus_sha256": "corpus",
        "source_sha256": "source",
        "k_values": [1, 5],
        "cases": [
            {
                "case_id": "p1",
                "stages": [
                    {"stage": f"{branch}_candidates", "scope": "component"} for branch in branches
                ],
            }
        ],
        "config": {"candidate_k": 30, "top_k": 10},
        "index_metadata": {"reports": indexes},
        "index_attribution": {"attribution_safe": True},
        "component_candidate_fingerprints": {
            "p1": {f"{branch}_candidates": f"{branch}-candidates" for branch in branches}
        },
        "provisional_aggregate": {
            "final.precision@5": {"value": 0.5, "evaluable_case_ids": ["p1"]}
        },
    }


def _assert_descriptive_only(result: dict[str, Any]) -> None:
    assert result["compatible"]
    assert result["metrics"]["final.precision@5"]["comparable"]
    assert not result["attribution_safe"]
    assert result["attribution_unsafe_reasons"]


@pytest.mark.parametrize("top_k", [10, 20])
def test_verified_identical_indexes_allow_control_and_top_k_comparison(top_k: int) -> None:
    left, right = _report(), _report()
    right["config"]["top_k"] = top_k
    right["provisional_aggregate"]["final.precision@5"]["value"] = 0.7
    result = compare(left, right)
    assert result["attribution_safe"]
    assert result["index_identity_comparison"]["equal"] is True
    assert result["metrics"]["final.precision@5"]["delta"] == pytest.approx(0.2)
    assert result["attribution_scope"] == "component_retrieval"


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("embedding_model", "embedding-v2"),
        ("vector_index_version", "vector-v2"),
        ("chunk_artifact_sha256", "different-chunks"),
        ("build_run_id", "different-build"),
        ("chunk_build_run_id", "different-chunk-build"),
        ("git_commit", "different-index-builder"),
    ],
)
def test_changed_identity_keeps_metric_delta_but_denies_attribution(
    field: str, changed: Any
) -> None:
    left, right = _report(), _report()
    right["config"]["top_k"] = 20
    right["index_metadata"]["reports"]["vector_index"]["manifest"][field] = changed
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert f"vector.{field}" in result["index_identity_comparison"]["changes"]


def test_changed_actual_artifact_detected_even_when_each_run_verified_it() -> None:
    left, right = _report(), _report()
    raw = right["index_metadata"]["reports"]["keyword_index"]
    raw["manifest"]["index_artifact_sha256"] = "rebuilt-keyword-artifact"
    raw["actual_index_artifact_sha256"] = "rebuilt-keyword-artifact"
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert "keyword.actual_index_artifact_sha256" in result["index_identity_comparison"]["changes"]


def test_changed_chunking_parameters_detected_even_if_chunks_and_candidates_match() -> None:
    left, right = _report(), _report()
    for branch in ("keyword", "vector"):
        right["index_metadata"]["reports"][f"{branch}_index"]["manifest"]["chunking"]["overlap"] = (
            50
        )
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert result["index_identity_comparison"]["changes"]["vector.chunking.overlap"] == [0, 50]


@pytest.mark.parametrize(
    "missing",
    [
        "index_metadata",
        "manifest",
        "embedding_model",
        "actual_index_artifact_sha256",
        "index_artifact_sha256",
        "chunking",
        "chunking.overlap",
    ],
)
def test_matching_missing_identity_never_counts_as_verified_equal(missing: str) -> None:
    left, right = _report(), _report()
    for report in (left, right):
        if missing == "index_metadata":
            report.pop(missing)
            continue
        raw = report["index_metadata"]["reports"]["vector_index"]
        if missing in {"manifest", "actual_index_artifact_sha256"}:
            raw.pop(missing)
        elif missing == "chunking.overlap":
            raw["manifest"]["chunking"].pop("overlap")
        else:
            raw["manifest"].pop(missing)
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert result["index_identity_comparison"]["equal"] is None
    assert result["index_identity_comparison"]["left"]["missing"]


@pytest.mark.parametrize("verified", [False, None])
def test_current_artifact_requires_explicit_verification(verified: bool | None) -> None:
    left, right = _report(), _report()
    right["index_metadata"]["reports"]["keyword_index"]["artifact_verified"] = verified
    _assert_descriptive_only(compare(left, right))


def test_verification_boolean_cannot_mask_artifact_manifest_mismatch() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["index_metadata"]["reports"]["vector_index"]["actual_index_artifact_sha256"] = (
            "different-actual-artifact"
        )
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert any("disagrees with manifest" in text for text in result["attribution_unsafe_reasons"])


def test_unused_vector_metadata_does_not_block_keyword_only_experiment() -> None:
    left, right = _report("keyword"), _report("keyword")
    left["index_metadata"]["reports"].pop("vector_index")
    right["index_metadata"]["reports"]["vector_index"] = {"manifest": {"embedding_model": "new"}}
    result = compare(left, right)
    assert result["attribution_safe"]
    assert result["index_identity_comparison"]["left"]["branches"] == ["keyword"]


def test_production_only_active_branch_is_still_checked() -> None:
    left, right = _report("keyword"), _report("keyword")
    for report in (left, right):
        report["cases"][0]["stages"].append(
            {"stage": "production_1_vector_candidates", "scope": "production_retrieval"}
        )
    right["index_metadata"]["reports"]["vector_index"]["manifest"]["embedding_model"] = "new"
    _assert_descriptive_only(compare(left, right))


def test_same_nonempty_fingerprints_do_not_prove_successful_branch_usage() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["cases"][0]["stages"] = []
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert any("usage is missing" in text for text in result["attribution_unsafe_reasons"])


def test_changed_per_case_usage_unsafe_even_when_union_of_branches_matches() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        second_case = deepcopy(report["cases"][0])
        second_case["case_id"] = "p2"
        report["cases"].append(second_case)
    right["cases"][0]["stages"] = [{"stage": "keyword_candidates", "scope": "component"}]
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert not result["index_identity_comparison"]["branch_usage_equal"]


def test_degraded_run_is_unsafe_even_if_legacy_attribution_boolean_says_safe() -> None:
    left, right = _report(), _report()
    right["degraded_cases"] = {"p1": ["vector"]}
    _assert_descriptive_only(compare(left, right))


def test_summary_model_and_manifest_disagreement_is_not_silently_accepted() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["index_metadata"]["reports"]["vector_index"]["summary"] = {
            "model_name": "different-summary-model"
        }
    _assert_descriptive_only(compare(left, right))


def test_failed_candidate_trace_does_not_activate_unused_branch() -> None:
    left, right = _report("keyword"), _report("keyword")
    for report in (left, right):
        report["cases"][0]["stages"].append(
            {"stage": "vector_candidates", "scope": "component", "status": "unavailable"}
        )
        report["index_metadata"]["reports"].pop("vector_index")
    assert compare(left, right)["attribution_safe"]


def test_equal_partial_candidate_fingerprints_do_not_prove_fixed_pools() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["component_candidate_fingerprints"]["p1"].pop("vector_candidates")
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert result["ordered_branch_candidates_equal"] is None


def test_inactive_branch_fingerprint_does_not_affect_active_pool_comparison() -> None:
    left, right = _report("keyword"), _report("keyword")
    right["component_candidate_fingerprints"]["p1"]["vector_candidates"] = "unused"
    assert compare(left, right)["attribution_safe"]


@pytest.mark.parametrize("missing", ["candidate_k", "top_k"])
def test_matching_unknown_component_config_cannot_be_attributed(missing: str) -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["config"].pop(missing)
    _assert_descriptive_only(compare(left, right))


def test_summary_without_stage_trace_keeps_scores_but_cannot_prove_isolation() -> None:
    left, right = _report(), _report()
    right["cases"][0].pop("stages")
    result = compare(left, right)
    _assert_descriptive_only(result)
    assert result["index_identity_comparison"]["equal"] is None
    assert any("usage is missing" in text for text in result["attribution_unsafe_reasons"])


@pytest.mark.parametrize("invalid", [True, ["unexpected"], "unexpected", 10])
@pytest.mark.parametrize(
    "level", ["index_metadata", "reports", "vector_index", "manifest", "summary"]
)
def test_invalid_index_metadata_shapes_do_not_crash_or_prove_isolation(
    level: str, invalid: Any
) -> None:
    left, right = _report(), _report()
    for report in (left, right):
        if level == "index_metadata":
            report[level] = invalid
        elif level == "reports":
            report["index_metadata"][level] = invalid
        elif level == "vector_index":
            report["index_metadata"]["reports"][level] = invalid
        else:
            report["index_metadata"]["reports"]["vector_index"][level] = invalid
    _assert_descriptive_only(compare(left, right))


@pytest.mark.parametrize(
    "field", ["embedding_model", "index_artifact_sha256", "chunking", "chunking.overlap"]
)
def test_boolean_identity_values_are_invalid_even_when_both_runs_match(field: str) -> None:
    left, right = _report(), _report()
    for report in (left, right):
        manifest = report["index_metadata"]["reports"]["vector_index"]["manifest"]
        if field == "chunking.overlap":
            manifest["chunking"]["overlap"] = False
        else:
            manifest[field] = True
    _assert_descriptive_only(compare(left, right))


def test_matching_duplicate_cases_reject_score_comparison_and_attribution() -> None:
    left, right = _report(), _report()
    for report in (left, right):
        report["cases"].append(deepcopy(report["cases"][0]))
    result = compare(left, right)
    assert not result["compatible"]
    assert not result["attribution_safe"]
    assert result["metrics"]["final.precision@5"]["delta"] is None
    assert any("duplicate case IDs" in reason for reason in result["reasons"])


@pytest.mark.parametrize("cases", [[], True, [True], [{"case_id": None}]])
def test_missing_or_malformed_cases_reject_comparison(cases: Any) -> None:
    left, right = _report(), _report()
    left["cases"] = right["cases"] = cases
    result = compare(left, right)
    assert not result["compatible"]
    assert not result["attribution_safe"]
