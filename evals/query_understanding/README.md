# 查询理解评测集（seed v1）

这层评测只看“系统有没有正确理解问题”，不看最终答案。它和 Golden 检索/答案评测分开，避免把意图识别、实体识别、时间解析的问题混进 R@20。

## 文件

- [cases.json](cases.json)：30 条种子用例，24 开发 + 6 保留
- [baselines/rules.md](baselines/rules.md)：确定性规则基线
- [baselines/llm.md](baselines/llm.md)：现有 LLM 规划器基线
- [BASELINE.md](BASELINE.md)：两套基线对比与问题清单
- [ENTITY_LINKING.md](ENTITY_LINKING.md)：实体索引 v1 与 shadow 结果
- [QUERY_ARMS_AB.md](QUERY_ARMS_AB.md)：查询臂在开发题上的 A/B 结论
- [LLM_CANDIDATES.md](LLM_CANDIDATES.md)：LLM 实体候选生成 shadow 结果

## 标注字段

| 字段 | 含义 |
|---|---|
| `intent` | `general / event_overview / timeline / intersection / viewpoint / observation / comparison / causal_analysis / out_of_scope` |
| `route` | `fast_fact / deep / clarify` |
| `flags` | `time_sensitive / multi_entity / multi_hop / follow_up / keyword_dump / negation / source_constraint` |
| `mentions` | 原始提及、类型、规范名（一个提及可对应多个实体） |
| `time` | 起止年份与精度（year/month/day/period） |
| `constraints` | 月份、地点、否定、来源等不能丢的约束 |
| `needs_clarification` | 是否应先澄清 |

`review_status` 目前全部是 `agent_prepared`，不是人工批准；只能用于诊断，不能作为正式 Golden 成绩。

## 运行

```powershell
.\.venv\Scripts\python.exe -B scripts/evaluate_query_understanding.py --mode rules
.\.venv\Scripts\python.exe -B scripts/evaluate_query_understanding.py --mode llm
.\.venv\Scripts\python.exe -B scripts/evaluate_query_understanding.py --mode both
```

输出在 `baselines/{mode}.json`、`baselines/{mode}.md` 和 `summary.json`。

实体链接 shadow：

```powershell
.\.venv\Scripts\python.exe -B scripts/run_entity_linking_shadow.py
```

## 指标

- 意图精确准确率，以及把 `general/event_overview/timeline` 合并为“事实族”后的准确率；
- 路由准确率；
- mention 的 canonical Precision / Recall / F1；规范名先做等价归一（会议全称、书名卷次、运动/时期后缀、多实体分隔）；
- 时间区间精确匹配率；
- 澄清 Precision / Recall / F1。

## 边界

- 这是种子集，不是最终评测集；30 条不足以覆盖全部意图组合。
- 用例和标签由 Agent 起草，需人工复核后才能升级为正式评测。
- LLM 规划器有非确定性，同一批用例重复运行结果会波动；报告中记录的是单次运行。
- 不要用 Golden 保留题调这里暴露的问题。
