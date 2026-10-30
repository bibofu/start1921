# 当前评测集索引（20 题，2026-10-30，Golden v1.1）

按用户 2026-10-29 裁定，从 29 题中删除 9 题并两次改写交集题后，当前工作集为 **20 题**。旧 v3–v6 标注、协议、29 题集、旧复核队列和旧观测已清理；本文件是当前唯一数据集索引。

## 总量

| 分层 | 题数 | 可答 / 拒答 | 必要事实 | 证据组 | 人工批准 |
|---|---:|---:|---:|---:|---:|
| 开发集 | 16 | 14 / 2 | 88 | 93 | 16 |
| 保留集 | 4 | 4 / 0 | 10 | 11 | 4 |
| **合计** | **20** | **18 / 2** | **98** | **104** | **20 / 20** |

- 当前数据集：[golden_dataset.json](golden_dataset.json)
- 冻结记录：[RELEASE_v1.1.md](RELEASE_v1.1.md)（v1.0 见 [RELEASE_v1.0.md](RELEASE_v1.0.md)）
- 逐题原文与状态：[CASE_INVENTORY.md](CASE_INVENTORY.md)
- LLM 标签复核记录：[label_reviews/20261030_llm63_reviewed.md](label_reviews/20261030_llm63_reviewed.md)（63 条全部通过）
- Agent 标签复核记录：[label_reviews/20261030_agent95_reviewed.md](label_reviews/20261030_agent95_reviewed.md)（84 通过、1 改判、10 删除）
- 固定池口径确认：[POOL_REVIEW.md](POOL_REVIEW.md)（18 个池）
- 采集/复核/评分流程：[REPEATABLE_WORKFLOW.md](REPEATABLE_WORKFLOW.md)

## 本次删除与改写

删除 9 题：

- `holdout_exact_decision`
- `pilot_semantic_deng_1962_agriculture`
- `pilot_multievidence_zunyi_leadership`
- `holdout_multi_sources`
- `pilot_negative_cppcc_1949`
- `pilot_constraint_deng_1973_march`
- `holdout_constraint_source_month`
- `dev_refusal_source_year`
- `holdout_refusal_insufficient`

2026-10-29 第二次改写（用户复核认为答案不完整）：

- `dev_intersection_mao_zhou_1949` → 扩为 7 次会议：6月7日会见陈嘉庚、7月1日纪念大会、7月9日铁路职工会议、9月8日会见程潜、9月25日座谈会、10月24日接见傅作义、12月1日民主人士座谈；参考答案明确“以年谱明确记载为限，不声称穷尽”。
- `holdout_intersection_positive` → 收窄为 1948.11–1949.12 的三项：淮海战役、渡江战役（京沪杭）、进军西南。

## 题型覆盖

| 类别 | 开发 | 保留 | 合计 |
|---|---:|---:|---:|
| 精确事实/日期/职务 | 4 | 1 | 5 |
| 语义改写/观点 | 4 | 0 | 4 |
| 多证据/跨期/比较 | 3 | 1 | 4 |
| 人物交集/困难负例 | 1 | 2 | 3 |
| 约束/路由/多轮 | 2 | 0 | 2 |
| 拒答/错误前提/材料不足 | 2 | 0 | 2 |
| **合计** | **16** | **4** | **20** |

删除后 **保留集没有约束题和拒答题**；这两类只在开发集。若要做独立验收，需要在保留集补题。

## 指标可计算性

| 指标 | 当前可评范围 | 说明 |
|---|---|---|
| 必要证据组 Recall@K | **18 道可答题** | 主指标 K=10；线上对齐 K=12；K=20 仅诊断；拒答 2 题无正向分母 |
| Precision@K | **18 道可答题，K≤5 稳定** | 182 条判断：全部人工复核（178 通过、4 改判）；池只有 6–14 个成员，K=10/20 不可评 |
| MRR@K | 18 道可答题，K≤10 | 主指标 K=10；K=12/20 仅诊断 |
| 固定池 nDCG@K | 18 道可答题，K≤5 | 主指标 K=5；池规模限制，不能评 K=10/20 |
| Fact/Cit | 旧 13 题中剩余的 8 道可答题 + 2024 拒答（Agent 评审） | 其余题没有可评真实答案 |
| 正式 R | **18 道可答题**（20 道批准题去掉 2 道拒答） | 全部题目定义已批准 |
| 正式 P@5 / MRR@10 | **17 题 / 17 题** | 首题 Top5 含未标注页，按 unknown 处理，不按 0 分 |
| 正式 nDCG@5 | **17 题** | 首题 Top5 含未标注页；池已全部人工批准 |
| 正式 Fact / Cit | **0 题** | 无人工作为基准的完整答案复核 |

18 道可答题都有固定池，182 条候选标签全部为 `human_review`（178 条通过、4 条改判）；`agent_review` 与 `llm_judge` 均已清零。

## 本次本地运行

> 从 2026-10-30 起主表使用 Recall@10、Precision@5、MRR@10、nDCG@5；另列 Recall@12 对齐线上 12 条窗口，Recall@20 仅作诊断。`RELEASE_v1.1.md` 中的 Recall@20 是当日冻结口径，不与本表混用。

详见 [2026-10-30 当前重跑](observations/20261030_current_run/README.md)（逐题报告 [CASES.md](observations/20261030_current_run/CASES.md)；完整 capture/report 在本地 `data/reports/golden20_20261030_congress_fix/`）：

| 指标 | 结果 |
|---|---:|
| 正式 Recall@10（主指标） | 62.6%（18 题宏平均；微平均 51/104 组） |
| 正式 Recall@12（线上对齐） | 62.9%（18 题宏平均；微平均 52/104 组） |
| 正式 Recall@20（诊断） | 64.8%（18 题宏平均；微平均 53/104 组） |
| 正式 Precision@5 | 62.4%（17 题） |
| 正式 MRR@10 | 0.971（17 题） |
| 正式固定池 nDCG@5 | 0.717（17 题） |
| 生成模型调用 / Token | 0 / N/A |

注意：主指标 Recall@10 为 62.6%，线上 12 条窗口为 62.9%，Recall@20 的 64.8% 只作诊断。`dev_semantic_first_congress` 的首题 Top5 仍有未标注页，所以 P/MRR/nDCG 的可评题数是 17。指标包含 182 条人工 `supported_groups` 匹配；v1.0 记录的 63.1% 是 Recall@20 旧口径，不能与这里的 Recall@10 直接比较。部分题的池内没有 gold 锚点页，候选标签只覆盖返回候选，池外召回缺失不会被补回。

## 距离正式 Golden 还差什么

1. 至少一次 20 题真实答案的逐事实/引用/来源/时间/拒答复核；当前 Fact/Cit 无分母。
2. K=10/20 的完整候选标注（当前池 6–14 个成员，K≤5 稳定）；若要评 P@10/nDCG@10，需要扩池补标。
3. 保留集只剩 4 题，缺约束题、拒答题和观察类题；需要补题后再做独立验收。
4. Qdrant 服务 artifact manifest 绑定，才能对 embedding/切分/rerank 做可归因实验。
