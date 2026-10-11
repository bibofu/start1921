"""Render compact, denominator-aware pilot reports without copying source text."""

from __future__ import annotations

import html
from collections import Counter
from typing import Any

from history_agent.evaluation.pilot_process import BRANCH_UNION, LAST_CONTEXT, SOURCE_UNION

MODES = (("provisional", "暂定"), ("approved", "正式"))
PHASE_NAMES = {
    "keyword_candidates": "关键词候选",
    "vector_candidates": "向量候选",
    "rrf_fusion": "融合",
    "rule_ranking": "规则排序",
    "career_filter": "任职过滤",
    "page_deduplication": "页级去重",
    "congress_coverage": "大会覆盖补充",
    "query_final": "单查询最终候选",
    "variants_rrf_fusion": "改写查询融合",
    "variants_career_filter": "改写查询任职过滤",
    "variants_page_deduplication": "改写查询页级去重",
    "final": "最终候选",
    "after_reflection": "反思后候选",
    "after_timeline_filter": "时间线过滤后候选",
    BRANCH_UNION: "各轮各分支召回并集",
    SOURCE_UNION: "各次生成已映射原文并集",
    LAST_CONTEXT: "末次生成上下文",
}
DIMENSIONS = {
    "required_fact_recall": "必要事实覆盖",
    "factual_accuracy": "事实正确性",
    "citation_support": "引用支持",
    "scope_compliance": "约束遵守",
    "source_constraint": "来源约束",
    "time_constraint": "时间约束",
    "routing": "路由选择",
    "scope_explanation": "回答范围说明",
    "safe_refusal": "安全拒答",
    "answer_pass": "整题通过",
}
CALL_NAMES = {
    "planner": "查询理解",
    "retrieval_reflection": "检索反思",
    "generation_direct": "直接生成",
    "generation_group": "分组生成",
    "generation_repair": "生成修复",
    "generation_synthesis": "摘要综合",
    "unknown": "无法识别请求阶段",
}
REASONS = {
    "case_human_review_not_approved": "整题尚未人工批准",
    "human_case_and_answer_review_required": "缺整题或答案人工复核",
    "human_case_and_process_review_required": "缺整题或过程人工复核",
    "phase_not_captured_or_not_executed": "阶段未采集或未执行",
    "incomplete_or_failed_stage_trace": "阶段轨迹缺失或失败",
    "summary_or_unmapped_context": "摘要上下文无法映射到原文",
    "no_mapped_successful_generation_context": "无成功且可映射的原文上下文",
    "generation_context_not_captured": "生成上下文未采集",
    "generation_http_not_successful": "该次生成请求未成功",
    "no_generation_call": "未执行生成请求",
    "invalid_captured_evidence": "采集证据身份或页码无效",
    "invalid_evidence_groups": "必要证据标注身份或锚点无效",
    "not_applicable_no_evidence_groups": "无适用必要证据组",
    "answer_not_reviewed": "本次答案尚未复核",
    "process_not_reviewed": "本次查询理解尚未复核",
    "query_understanding_trace_unavailable": "无查询理解轨迹",
    "no_evaluable_process_reviews": "无可评过程复核",
    "no_required_facts": "无适用必要事实",
    "unknown_fact_judgments": "存在未裁定事实",
    "unknown_applicable_judgments": "适用维度尚未裁定",
    "not_applicable": "不适用",
    "unknown": "尚未裁定",
    "wall_clock_measurement_missing_or_invalid": "墙钟耗时未采集或无效",
    "no_llm_calls": "未执行 LLM 请求",
    "llm_calls_not_captured": "请求记录缺失",
    "missing_or_invalid_usage": "Token usage 缺失或无效",
}


def _text(value: Any) -> str:
    return html.escape(str(value), quote=False).replace("|", "\\|").replace("\n", " ")


def _value(value: Any, *, percent: bool = False) -> str:
    if value is None:
        return "N/A"
    if percent:
        return f"{value:.1%}"
    return f"{value:.3f}" if isinstance(value, float) else _text(value)


def _reason(value: Any) -> str:
    return _text(REASONS.get(value, value or "未提供可评数据"))


def _metric(metric: dict[str, Any] | None, *, percent: bool = True) -> str:
    metric = metric or {}
    value = metric.get("value")
    if value is None:
        return f"N/A（{_reason(metric.get('reason'))}）"
    return _value(value, percent=percent)


def _ratio(metric: dict[str, Any]) -> str:
    return f"{_value(metric.get('numerator'))}/{_value(metric.get('denominator'))}"


def _counts(counts: dict[str, Any] | None) -> str:
    if counts is None:
        return "N/A（未完成适用复核）"
    return " / ".join(
        str(counts.get(name, 0))
        for name in ("covered", "partial", "missing", "contradicted", "unknown")
    )


def _reason_counts(items: list[dict[str, Any]]) -> str:
    counts = Counter(item.get("reason") for item in items)
    return "；".join(f"{_reason(reason)}（{count}题）" for reason, count in counts.items()) or "—"


def _answer_reasons(report: dict[str, Any], mode: str, dimension: str) -> str:
    items = []
    for case in report.get("cases", []):
        metric = (
            case.get("generation_assessment", {}).get(mode, {}).get("metrics", {}).get(dimension)
        )
        if metric and metric.get("value") is None:
            items.append({"reason": metric.get("reason")})
    return _reason_counts(items)


def _component_tables(report: dict[str, Any], lines: list[str]) -> None:
    lines += [
        "## 组件检索：多 K 指标",
        "",
        "各格为“宏平均（有效题数/该阶段题数）”。未知候选不当作不相关；"
        "固定池 nDCG 仅在候选池及相关性标注满足条件时计算。",
        "",
        "| 口径 | 阶段 | K | 必要证据 Recall | Precision | MRR | 固定池 nDCG |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    any_rows = False
    for mode, label in MODES:
        aggregate = report.get(f"{mode}_aggregate", {})
        combinations = set()
        for key in aggregate:
            if "." in key and "@" in key:
                stage, name = key.rsplit(".", 1)
                if name.split("@", 1)[0] in {
                    "required_group_recall",
                    "precision",
                    "mrr",
                    "pool_ndcg",
                }:
                    try:
                        combinations.add((stage, int(name.rsplit("@", 1)[1])))
                    except ValueError:
                        continue
        for stage, k in sorted(combinations):
            any_rows = True
            cells = []
            for name in ("required_group_recall", "precision", "mrr", "pool_ndcg"):
                metric = aggregate.get(f"{stage}.{name}@{k}", {})
                cells.append(
                    f"{_value(metric.get('value'))} "
                    f"({metric.get('evaluable_cases', 0)}/{metric.get('total_cases', 0)})"
                )
            lines.append(
                f"| {label} | {_text(PHASE_NAMES.get(stage, stage))} | {k} | "
                + " | ".join(cells)
                + " |"
            )
    if not any_rows:
        lines.append("| — | N/A（无组件评分） | — | N/A | N/A | N/A | N/A |")
    lines += [
        "",
        "同一运行的多 K 是排序前缀诊断；不等于重新执行不同生产 Top-K。"
        "有效题 ID、未知候选、未标注/失效池原因见 JSON 的阶段诊断。",
        "",
    ]


def _answer_tables(report: dict[str, Any], lines: list[str]) -> None:
    lines += [
        "## 最终答案与查询理解",
        "",
        "| 口径 | 维度 | 分数 | 通过数/有效分母 | 有效题数/目标题数 | N/A 原因 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    count = len(report.get("cases", []))
    for mode, label in MODES:
        for name, metric in report.get(f"{mode}_answer_aggregate", {}).items():
            lines.append(
                f"| {label} | {_text(DIMENSIONS.get(name, name))} | "
                f"{_value(metric.get('value'), percent=True)} | {_ratio(metric)} | "
                f"{len(metric.get('evaluable_case_ids', []))}/{count} | "
                f"{_answer_reasons(report, mode, name)} |"
            )
        query = report.get("query_understanding", {}).get(f"{mode}_aggregate", {})
        reasons = [{"reason": reason} for reason in query.get("unevaluable_reasons", {}).values()]
        lines.append(
            f"| {label} | 查询理解 | {_value(query.get('value'), percent=True)} | "
            f"{_ratio(query)} | {query.get('evaluable_cases', 0)}/{query.get('total_cases', count)}"
            f" | {_reason_counts(reasons) if query else 'N/A（未提供过程复核）'} |"
        )
    lines += [
        "",
        "必要事实覆盖按事实数作分母，其余维度按适用且已复核的题数作分母。"
        "整题通过要求所有适用维度通过；有部分可用内容不等于整题通过。",
        "",
    ]


def _process_tables(process: dict[str, Any], lines: list[str]) -> None:
    lines += [
        "## 生产过程：必要证据组覆盖",
        "",
        "以下覆盖合并同题各轮/查询变体；并集不参与 Precision、MRR 或 nDCG。"
        "固定目标均值只在全部适用题可评时显示。",
        "",
        "| 口径 | 阶段 | 有效子集宏平均 | 命中组/有效组分母 | 有效题/目标题 | "
        "固定目标均值 | N/A 原因 |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for mode, label in MODES:
        for phase, metric in process.get("production_phase_summary", {}).get(mode, {}).items():
            lines.append(
                f"| {label} | {_text(PHASE_NAMES.get(phase, phase))} | "
                f"{_value(metric.get('observed_subset_macro_value'), percent=True)} | "
                f"{_value(metric.get('observed_subset_evidence_groups_matched'))}/"
                f"{_value(metric.get('observed_subset_evidence_group_denominator'))} | "
                f"{metric.get('evaluable_case_count', 0)}/{metric.get('target_case_count', 0)} | "
                f"{_value(metric.get('fixed_target_macro_value'), percent=True)} | "
                f"{_reason_counts(metric.get('unevaluable_cases', []))} |"
            )
    if not process.get("production_phase_summary"):
        lines.append("| — | N/A（无生产过程汇总） | N/A | N/A | 0/0 | N/A | 未采集 |")
    lines += [
        "",
        "原文并集包含成功请求中可映射的分组生成和修复输入；"
        "末次请求若使用摘要，不能反推成原文上下文。缺轨迹保持 N/A。"
        "原文裁剪会改变证据身份，覆盖下降也可能来自新片段尚未补标。",
        "",
    ]


def _cost_tables(process: dict[str, Any], lines: list[str]) -> None:
    http = process.get("http", {})
    lines += [
        "## 请求、Token 与耗时",
        "",
        f"HTTP 请求总数：{_value(http.get('calls'))}；"
        f"已记录 {_value(http.get('observed_calls'))} 次，"
        f"成功 {_value(http.get('success_count'))}、失败 {_value(http.get('failure_count'))}、"
        f"状态未知 {_value(http.get('unknown_count'))}。重试逐次计入。",
        "",
        "| 请求阶段 | 已记录调用数 | 完整 usage 调用 | 输入 Token | 输出 Token | 总 Token | "
        "已知总 Token | 缺 usage 调用数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    cost = process.get("cost", {})
    entries = [("全部", cost.get("all", {}))] + [
        (CALL_NAMES.get(name, name), value) for name, value in cost.get("by_stage", {}).items()
    ]
    for label, row in entries:
        tokens = row.get("tokens", {})
        cells = [
            _value(tokens.get(field, {}).get("value"))
            for field in ("prompt_tokens", "completion_tokens", "total_tokens")
        ]
        lines.append(
            f"| {_text(label)} | {_value(row.get('calls'))} | "
            f"{_value(row.get('usage_complete_calls'))} | "
            + " | ".join(cells)
            + f" | {_value(tokens.get('total_tokens', {}).get('known_sum'))} | "
            f"{len(row.get('unknown_usage_calls', []))} |"
        )
    missing = http.get("missing_capture_case_ids", [])
    lines += [
        "",
        "usage 缺失时完整总量为 N/A，已知量仅是可观测子集；未调用 LLM 不填虚构 Token。"
        "累计请求耗时可能包含并发重叠，不能当作回答墙钟耗时。",
    ]
    if missing:
        lines.append("请求采集缺失题目：" + "、".join(_text(cid) for cid in missing) + "。")
    lines += [
        "",
        "| 实测路径 | 有效题/总题 | 均值 ms | 中位数 ms | 最大值 ms | 完整累计 ms | N/A 原因 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for field, label in (("retrieval_ms", "组件检索墙钟"), ("answer_ms", "完整回答墙钟")):
        row = process.get("latency", {}).get(field, {})
        cells = [_value(row.get(name)) for name in ("mean_ms", "median_ms", "max_ms", "total_ms")]
        lines.append(
            f"| {label} | {row.get('evaluable_cases', 0)}/{row.get('total_cases', 0)} | "
            + " | ".join(cells)
            + f" | {_reason_counts(row.get('unevaluable_cases', []))} |"
        )
    lines += ["", "每题仅一次实测，组件检索和完整回答是分别计时的路径。", ""]


def _per_case_table(report: dict[str, Any], process: dict[str, Any], lines: list[str]) -> None:
    rows = {row["case_id"]: row for row in process.get("per_case", [])}
    queries = {
        row["case_id"]: row for row in report.get("query_understanding", {}).get("cases", [])
    }
    lines += [
        "## 逐题结果",
        "",
        "事实状态按“覆盖 / 部分 / 缺失 / 矛盾 / 未裁定”排列；以下按暂定口径展示，"
        "正式有效分母见前表及 JSON。",
        "",
        "| 题目 ID | 事实状态 | 事实覆盖 | 整题通过 | 查询理解 | 召回并集 | "
        "原文输入并集 | 末次上下文 | HTTP 次数 | 总 Token | 回答 ms |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in report.get("cases", []):
        cid = case["case_id"]
        row = rows.get(cid, {})
        assessment = case.get("generation_assessment", {}).get("provisional", {})
        metrics = assessment.get("metrics", {})
        query = queries.get(cid, {}).get("query_understanding", {}).get("provisional", {})
        coverage = row.get("production_phase_union_diagnostics", {}).get("provisional", {})
        tokens = row.get("cost", {}).get("tokens", {}).get("total_tokens", {})
        lines.append(
            f"| {_text(cid)} | {_counts(assessment.get('fact_status_counts'))} | "
            f"{_metric(metrics.get('required_fact_recall'))} | "
            f"{_metric(metrics.get('answer_pass'))} | {_metric(query)} | "
            f"{_metric(coverage.get(BRANCH_UNION))} | {_metric(coverage.get(SOURCE_UNION))} | "
            f"{_metric(coverage.get(LAST_CONTEXT))} | {_value(row.get('http', {}).get('calls'))}"
            f" | {_value(tokens.get('value'))} | "
            f"{_value(row.get('latency', {}).get('answer_ms', {}).get('value'))} |"
        )
    lines += ["", "题目与过程复核说明：", ""]
    for case in report.get("cases", []):
        cid = case["case_id"]
        query = queries.get(cid, {}).get("query_understanding", {}).get("provisional", {})
        lines.append(f"- `{_text(cid)}`：{_text(case.get('question', ''))}")
        if query.get("review_reason"):
            lines.append(f"  查询理解复核：{_text(query['review_reason'])}")
    lines.append("")


def markdown_report(report: dict[str, Any]) -> str:
    """Render complete diagnostic summaries while retaining honest N/A gates."""
    process = report.get("process_summary", {})
    lines = [
        "# 开发集评测报告",
        "",
        f"运行：`{_text(report.get('run_name', 'unknown'))}`",
        "",
        "暂定分数允许 Agent 复核标签，用于诊断；正式分数要求适用的人工作业批准。"
        "未知、未标注、不适用与缺采集均保持 N/A，不能按零分处理。",
        "",
        f"采集指纹：`{_text(report.get('capture_sha256', 'N/A'))}`  ",
        f"题集指纹：`{_text(report.get('dataset_sha256', 'N/A'))}`  ",
        f"代码指纹：`{_text(report.get('source_sha256') or 'N/A')}`  ",
        f"答案复核指纹：`{_text(report.get('answer_reviews_sha256') or 'N/A')}`  ",
        f"过程复核指纹：`{_text(report.get('process_reviews_sha256') or 'N/A')}`  ",
        f"协议文件指纹：`{_text(report.get('protocol_file_sha256') or 'N/A')}`",
        "",
    ]
    _component_tables(report, lines)
    _answer_tables(report, lines)
    _process_tables(process, lines)
    _cost_tables(process, lines)
    _per_case_table(report, process, lines)
    lines += [
        "完整逐题分母、有效/不可评题 ID、逐调用 usage、候选身份、N/A 原因及"
        "索引/模型/参数版本见同名 JSON；紧凑 JSON 保留汇总与逐题结果。",
        "",
    ]
    return "\n".join(lines)
