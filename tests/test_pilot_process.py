from copy import deepcopy
from typing import Any

import pytest
from history_agent.evaluation.pilot_process import (
    BRANCH_UNION,
    LAST_CONTEXT,
    SOURCE_UNION,
    summarize_process,
)

HASH = "a" * 64
MARKER = "\n\n仅可使用的本地证据：\n"


def _case(case_id: str = "case") -> dict[str, Any]:
    return {
        "id": case_id,
        "answerability": "answerable",
        "human_review": {"status": "pending"},
        "evidence_groups": [
            {
                "id": f"g{page}",
                "alternatives": [
                    {"document_id": "doc", "file_sha256": HASH, "pdf_page": page, "quote": quote}
                ],
            }
            for page, quote in [(1, "主持会议"), (2, "提出建议")]
        ],
        "judgments": [],
    }


def _hit(page: int = 1) -> dict[str, Any]:
    return {
        "document_id": "doc",
        "pdf_page_start": page,
        "pdf_page_end": page,
        "text": "主持会议" if page == 1 else "提出建议",
    }


def _stage(name: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stage": name, "hits": hits, "status": "ok"}


def _call(index: int = 1, kind: str = "generation_direct") -> dict[str, Any]:
    system = {
        "planner": "你是中国近现代史本地知识库的查询理解器",
        "retrieval_reflection": "你是本地史料检索的证据充分性评估器",
    }.get(kind, "助手")
    prompt = "问题：介绍会议"
    if kind == "generation_group":
        prompt += "\n\n这是覆盖检索的第 1/2 组证据。"
    prompt += MARKER
    if kind == "generation_synthesis":
        prompt += "以下是分组证据经逐组引用校验后的摘要。"
    else:
        prompt += "原文材料"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    if kind == "generation_repair":
        messages += [
            {"role": "assistant", "content": "旧答案"},
            {"role": "user", "content": "修复"},
        ]
    return {
        "call_index": index,
        "request": {"model": "model", "messages": messages},
        "http_status": 200,
        "status": "response",
        "elapsed_ms": 80,
        "response_summary": {
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
        },
    }


def _context(index: int = 1, page: int = 1) -> dict[str, Any]:
    return {"call_index": index, "mapping_complete": True, "http_status": 200, "hits": [_hit(page)]}


def _capture() -> dict[str, Any]:
    return {
        "corpus": {"documents": [{"document_id": "doc", "sha256": HASH}]},
        "cases": [
            {
                "case_id": "case",
                "production_stages": [
                    _stage("production_1_keyword_candidates", [_hit()]),
                    _stage("production_1_vector_candidates", [_hit(2)]),
                    _stage("production_1_final", [_hit()]),
                ],
                "llm_calls": [_call()],
                "generation_contexts": [_context()],
                "retrieval_ms": 10,
                "answer_ms": 100,
            }
        ],
    }


def _metric(result: dict[str, Any], phase: str, mode: str = "provisional") -> dict[str, Any]:
    return result["per_case"][0]["production_phase_union_diagnostics"][mode][phase]


def test_unions_preserve_rounds_branches_and_fixed_groups_without_duplicate_credit() -> None:
    capture = _capture()
    capture["cases"][0]["production_stages"] += [
        _stage("production_2_keyword_candidates", [_hit(), _hit(2)]),
        _stage("production_2_final", [_hit(2)]),
    ]
    result = summarize_process([_case()], capture)
    metric = _metric(result, BRANCH_UNION)
    assert metric["value"] == 1
    assert metric["numerator"] == metric["denominator"] == 2
    assert metric["returned_count"] == 4
    assert metric["unique_unit_count"] == 2
    assert _metric(result, "final")["matched_groups"] == ["g1", "g2"]
    assert _metric(result, SOURCE_UNION)["missing_group_ids"] == ["g2"]


def test_approved_gate_cannot_be_bypassed_by_exact_quote_matches() -> None:
    case = _case()
    result = summarize_process([case], _capture())
    assert _metric(result, BRANCH_UNION)["value"] == 1
    assert _metric(result, BRANCH_UNION, "approved")["reason"] == "case_human_review_not_approved"
    assert _metric(result, SOURCE_UNION, "approved")["value"] is None
    case["human_review"]["status"] = "approved"
    approved = summarize_process([case], _capture())
    assert _metric(approved, BRANCH_UNION, "approved")["value"] == 1


def test_missing_trace_and_missing_case_are_unknown_not_zero_or_component_fallback() -> None:
    capture = _capture()
    capture["cases"][0]["stages"] = capture["cases"][0].pop("production_stages")
    result = summarize_process([_case(), _case("missing")], capture)
    assert _metric(result, BRANCH_UNION)["value"] is None
    summary = result["production_phase_summary"]["provisional"][BRANCH_UNION]
    assert summary["target_case_ids"] == ["case", "missing"]
    assert summary["evaluable_case_count"] == 0
    assert summary["observed_subset_macro_value"] is None
    assert result["http"]["calls"] is None
    assert result["http"]["observed_calls"] == 1
    assert result["cost"]["all"]["tokens"]["total_tokens"]["value"] is None
    assert result["cost"]["all"]["tokens"]["total_tokens"]["known_sum"] == 12


def test_empty_successful_trace_is_known_zero_but_failed_trace_is_not() -> None:
    capture = _capture()
    capture["cases"][0]["production_stages"] = [_stage("production_1_final", [])]
    result = summarize_process([_case()], capture)
    assert _metric(result, "final")["value"] == 0
    capture["cases"][0]["production_stages"][0]["status"] = "failed"
    result = summarize_process([_case()], capture)
    assert _metric(result, "final")["reason"] == "incomplete_or_failed_stage_trace"


def test_synthesis_summary_is_not_mapped_to_source_by_earlier_group_context() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"] = [
        _call(1, "generation_group"),
        _call(2, "generation_group"),
        _call(3, "generation_synthesis"),
    ]
    raw["generation_contexts"] = [
        _context(1),
        _context(2, 2),
        {"call_index": 3, "mapping_complete": False, "http_status": 200, "hits": []},
    ]
    result = summarize_process([_case()], capture)
    assert _metric(result, SOURCE_UNION)["value"] == 1
    assert _metric(result, LAST_CONTEXT)["reason"] == "summary_or_unmapped_context"
    assert result["cost"]["by_stage"]["generation_group"]["calls"] == 2
    assert result["cost"]["by_stage"]["generation_synthesis"]["calls"] == 1


def test_final_generation_selected_by_request_index_and_missing_context_not_skipped() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"] = [_call(2, "generation_repair"), _call(1)]
    result = summarize_process([_case()], capture)
    assert _metric(result, SOURCE_UNION)["value"] == 0.5
    assert _metric(result, LAST_CONTEXT)["reason"] == "generation_context_not_captured"
    raw["generation_contexts"].append(_context(2, 2))
    result = summarize_process([_case()], capture)
    assert _metric(result, LAST_CONTEXT)["matched_groups"] == ["g2"]


def test_failed_last_attempt_does_not_fall_back_to_successful_context_for_coverage() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"].append(_call(2, "generation_repair"))
    raw["llm_calls"][1]["http_status"] = 503
    raw["llm_calls"][1].pop("response_summary")
    raw["generation_contexts"].append(_context(2, 2))
    result = summarize_process([_case()], capture)
    assert _metric(result, LAST_CONTEXT)["reason"] == "generation_http_not_successful"
    assert _metric(result, SOURCE_UNION)["value"] == 0.5
    assert result["http"]["calls"] == 2
    assert result["http"]["success_count"] == result["http"]["failure_count"] == 1
    tokens = result["cost"]["all"]["tokens"]["total_tokens"]
    assert tokens["value"] is None
    assert tokens["known_sum"] == 12
    assert tokens["unknown_calls"] == [{"case_id": "case", "call_index": 2, "record_position": 2}]


def test_every_http_attempt_including_retries_is_counted_and_call_time_is_not_wall_time() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"] = [
        _call(1, "planner"),
        _call(2, "planner"),
        _call(3, "retrieval_reflection"),
        _call(4),
    ]
    raw["generation_contexts"] = [_context(4)]
    result = summarize_process([_case()], capture)
    assert result["http"]["calls"] == 4
    assert result["cost"]["all"]["tokens"]["total_tokens"]["value"] == 48
    assert result["cost"]["by_stage"]["planner"]["calls"] == 2
    assert result["cost"]["by_stage"]["retrieval_reflection"]["calls"] == 1
    assert result["cost"]["all"]["sum_call_elapsed_ms"] == 320
    assert result["latency"]["answer_ms"]["total_ms"] == 100
    # Optional cache usage is unknown rather than silently zero.
    assert result["cost"]["all"]["tokens"]["prompt_cache_hit_tokens"]["value"] is None


def test_missing_and_partial_usage_have_explicit_denominators_without_estimates() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"].append(_call(2))
    raw["llm_calls"][1]["response_summary"]["usage"] = {"prompt_tokens": 10}
    result = summarize_process([_case()], capture)
    cost = result["cost"]["all"]
    assert cost["usage_complete_calls"] == 1
    assert cost["tokens"]["prompt_tokens"]["value"] == 20
    assert cost["tokens"]["completion_tokens"]["known_sum"] == 2
    assert cost["tokens"]["completion_tokens"]["value"] is None
    assert cost["tokens"]["completion_tokens"]["evaluable_calls"] == 1
    assert cost["tokens"]["completion_tokens"]["total_calls"] == 2


def test_network_exception_and_unfinished_attempt_are_separate_http_outcomes() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"] = [
        {"call_index": 1, "status": "failed", "error_type": "ConnectTimeout", "request": {}},
        {"call_index": 2, "status": "started", "request": {}},
    ]
    raw["generation_contexts"] = []
    result = summarize_process([_case()], capture)
    assert result["http"]["failure_count"] == result["http"]["unknown_count"] == 1
    assert result["cost"]["all"]["tokens"]["total_tokens"]["known_sum"] is None
    assert result["cost"]["all"]["sum_call_elapsed_ms"] is None
    assert result["cost"]["by_stage"]["unknown"]["calls"] == 2


def test_inconsistent_usage_is_unknown_and_invalid_latency_is_excluded() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"][0]["response_summary"]["usage"]["total_tokens"] = 999
    raw["llm_calls"][0]["elapsed_ms"] = float("nan")
    raw["answer_ms"] = -10
    result = summarize_process([_case()], capture)
    assert result["call_usage"][0]["usage_reason"] == "inconsistent_provider_usage"
    assert result["cost"]["all"]["tokens"]["total_tokens"]["value"] is None
    assert result["latency"]["answer_ms"]["evaluable_cases"] == 0
    assert result["latency"]["answer_ms"]["mean_ms"] is None


def test_no_llm_is_explicitly_na_but_zero_http_attempts_is_known() -> None:
    capture = _capture()
    raw = capture["cases"][0]
    raw["llm_calls"] = []
    raw["generation_contexts"] = []
    result = summarize_process([_case()], capture)
    assert result["http"]["calls"] == 0
    assert result["cost"]["all"]["tokens"]["total_tokens"]["reason"] == "no_llm_calls"
    assert _metric(result, SOURCE_UNION)["value"] is None
    assert _metric(result, LAST_CONTEXT)["reason"] == "no_generation_call"


def test_aggregate_retains_missing_case_ids_and_excludes_refusal_from_recall_targets() -> None:
    cases = [_case(), _case("missing"), _case("refusal")]
    cases[-1].update(answerability="refuse", evidence_groups=[])
    capture = _capture()
    refusal = deepcopy(capture["cases"][0])
    refusal["case_id"] = "refusal"
    capture["cases"].append(refusal)
    result = summarize_process(cases, capture)
    summary = result["production_phase_summary"]["provisional"][BRANCH_UNION]
    assert summary["target_case_count"] == 2
    assert summary["evaluable_case_ids"] == ["case"]
    assert summary["unevaluable_cases"][0]["case_id"] == "missing"
    assert summary["fixed_target_macro_value"] is None
    assert summary["observed_subset_macro_value"] == 1
    assert summary["observed_subset_evidence_group_denominator"] == 2


def test_stale_source_identity_and_duplicate_dataset_ids_are_rejected_or_na() -> None:
    capture = _capture()
    capture["cases"][0]["production_stages"][0]["hits"][0]["file_sha256"] = "stale"
    result = summarize_process([_case()], capture)
    assert _metric(result, BRANCH_UNION)["reason"] == "invalid_captured_evidence"
    with pytest.raises(ValueError, match="duplicate"):
        summarize_process([_case(), _case()], capture)
    capture["cases"][0]["case_id"] = "unknown"
    with pytest.raises(ValueError, match="outside"):
        summarize_process([_case()], capture)
