from typing import Any

from history_agent.evaluation.pilot_reporting import markdown_report


def _report() -> dict[str, Any]:
    return {
        "run_name": "offline",
        "capture_sha256": "capture",
        "dataset_sha256": "dataset",
        "provisional_aggregate": {
            f"final.{metric}@{k}": {
                "value": 0.5 if k == 3 else None,
                "evaluable_cases": 1 if k == 3 else 0,
                "total_cases": 2,
            }
            for k in (3, 10)
            for metric in ("required_group_recall", "precision", "mrr", "pool_ndcg")
        },
        "cases": [
            {
                "case_id": "case",
                "question": "哪项|结论？\n<script>不执行</script>",
                "generation_assessment": {
                    "provisional": {
                        "fact_status_counts": {
                            "covered": 1,
                            "partial": 2,
                            "missing": 3,
                            "contradicted": 4,
                            "unknown": 5,
                        },
                        "metrics": {
                            "answer_pass": {"value": None, "reason": "answer_not_reviewed"}
                        },
                    }
                },
            }
        ],
        "query_understanding": {
            "cases": [
                {
                    "case_id": "case",
                    "query_understanding": {
                        "provisional": {"value": None, "reason": "process_not_reviewed"}
                    },
                }
            ]
        },
        "process_summary": {
            "production_phase_summary": {
                "provisional": {
                    "last_generation_call_context": {
                        "observed_subset_macro_value": None,
                        "fixed_target_macro_value": None,
                        "observed_subset_evidence_groups_matched": None,
                        "observed_subset_evidence_group_denominator": None,
                        "evaluable_case_count": 0,
                        "target_case_count": 1,
                        "unevaluable_cases": [
                            {"case_id": "case", "reason": "summary_or_unmapped_context"}
                        ],
                    }
                }
            },
            "cost": {
                "all": {
                    "calls": 2,
                    "usage_complete_calls": 1,
                    "tokens": {"total_tokens": {"value": None, "known_sum": 12}},
                    "unknown_usage_calls": [{"call_index": 2}],
                },
                "by_stage": {"generation_repair": {"calls": 1, "tokens": {}}},
            },
            "http": {
                "calls": 2,
                "observed_calls": 2,
                "success_count": 1,
                "failure_count": 1,
                "unknown_count": 0,
            },
            "latency": {
                "answer_ms": {
                    "evaluable_cases": 1,
                    "total_cases": 1,
                    "mean_ms": 80,
                    "median_ms": 80,
                    "max_ms": 80,
                    "total_ms": 80,
                }
            },
        },
    }


def test_report_renders_multi_k_and_denominators_without_filling_unknowns_with_zero() -> None:
    rendered = markdown_report(_report())
    assert "固定池 nDCG" in rendered
    assert "| 暂定 | 最终候选 | 3 | 0.500 (1/2)" in rendered
    assert "| 暂定 | 最终候选 | 10 | N/A (0/2)" in rendered
    assert "摘要上下文无法映射到原文（1题）" in rendered
    assert "1 / 2 / 3 / 4 / 5" in rendered
    assert "N/A（本次答案尚未复核）" in rendered
    assert "N/A（本次查询理解尚未复核）" in rendered
    assert "| 全部 | 2 | 1 | N/A | N/A | N/A | 12 | 1 |" in rendered
    assert "| 完整回答墙钟 | 1/1 | 80 | 80 | 80 | 80 |" in rendered
    assert "生成修复" in rendered


def test_absent_process_summary_is_not_reported_as_zero_requests() -> None:
    rendered = markdown_report({})
    assert "HTTP 请求总数：N/A；已记录 N/A 次，成功 N/A、失败 N/A、状态未知 N/A" in rendered
    assert "N/A（无生产过程汇总）" in rendered


def test_markdown_tables_keep_consistent_column_counts_and_escape_user_content() -> None:
    rendered = markdown_report(_report())
    expected_columns = None
    for line in rendered.splitlines():
        if not line.startswith("|"):
            expected_columns = None
            continue
        columns = line.replace("\\|", "ESCAPED").count("|")
        if expected_columns is None:
            expected_columns = columns
        assert columns == expected_columns
    assert "哪项\\|结论？ &lt;script&gt;不执行&lt;/script&gt;" in rendered
