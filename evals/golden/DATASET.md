# 当前评测集索引（20 题，2026-10-29）

按用户 2026-10-29 裁定，从 29 题中删除 9 题并两次改写交集题后，当前工作集为 **20 题**。旧 v3–v6 标注、协议、29 题集、旧复核队列和旧观测已清理；本文件是当前唯一数据集索引。

## 总量

| 分层 | 题数 | 可答 / 拒答 | 必要事实 | 证据组 | 人工批准 |
|---|---:|---:|---:|---:|---:|
| 开发集 | 15 | 13 / 2 | 76 | 81 | 15 |
| 保留集 | 5 | 5 / 0 | 15 | 16 | 5 |
| **合计** | **20** | **18 / 2** | **91** | **97** | **20 / 20** |

- 当前数据集：[golden_dataset.json](golden_dataset.json)
- 逐题原文与状态：[CASE_INVENTORY.md](CASE_INVENTORY.md)
- LLM 标签抽检：[LLM_LABEL_REVIEW.md](LLM_LABEL_REVIEW.md)
- 72 条待抽检标签：[LLM_LABELS_PENDING.md](LLM_LABELS_PENDING.md)（原文摘录）、[LLM_LABELS_CHECKLIST.md](LLM_LABELS_CHECKLIST.md)（紧凑复核表）
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
| 语义改写/观点 | 3 | 1 | 4 |
| 多证据/跨期/比较 | 3 | 1 | 4 |
| 人物交集/困难负例 | 1 | 2 | 3 |
| 约束/路由/多轮 | 2 | 0 | 2 |
| 拒答/错误前提/材料不足 | 2 | 0 | 2 |
| **合计** | **15** | **5** | **20** |

删除后 **保留集没有约束题和拒答题**；这两类只在开发集。若要做独立验收，需要在保留集补题。

## 指标可计算性

| 指标 | 当前可评范围 | 说明 |
|---|---|---|
| 必要证据组 Recall@K | **18 道可答题** | 15 开发 + 5 保留；拒答 2 题无正向分母 |
| Precision@K | **18 道可答题，K≤5 稳定** | 192 条判断：95 条 Agent + 72 条 LLM + 25 条人工处理（23 通过、2 改判）；K=10/20 受池大小/池外候选限制 |
| MRR@K | 18 道可答题，K≤5 | 同上 |
| 固定池 nDCG@K | 18 道可答题，K≤5 | 18 个固定池；不是全语料理想排序 |
| Fact/Cit | 旧 13 题中剩余的 8 道可答题 + 2024 拒答（Agent 评审） | 其余题没有可评真实答案 |
| 正式 R | **18 道可答题**（20 道批准题去掉 2 道拒答） | 全部题目定义已批准 |
| 正式 P@5 / MRR@5 | **1 题 / 5 题** | 只有这些题同时具备人工批准定义和人工候选标签；分母太小，不应当作稳定结论 |
| 正式 nDCG / Fact / Cit | **0 题** | 无人工作为基准的完整排序/答案复核 |

18 道可答题都有固定池。其中 8 题的候选标签是 `agent_review`，10 题共 97 条模型标签：25 条已由用户人工处理（23 条通过、2 条改判为 rel=1；basis=`human_review`），72 条仍是 `llm_judge`。人工抽检不改变题目定义的 pending 状态。

## 本次本地运行

详见 [Golden 20 题本地基线](observations/20261029_golden20_local/README.md)（完整 capture/report 留在本地忽略目录 `data/reports/golden20_r2_20261029/`）：

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 60.4%（18 题宏平均；微平均 48/97 组） |
| Precision@5 | 58.9%（18 题） |
| MRR@5 | 0.861（18 题） |
| 固定池 nDCG@5 | 0.669（18 题） |
| 正式 Recall@20 | 52.0%（18 题宏平均；微平均 41/97 组） |
| 正式 Precision@5 / MRR@5 | 1 题 / 5 题，分母过小 |
| 生成模型调用 / Token | 0 / N/A |

注意：60.4% 的暂定 Recall 包含 97 条 LLM/人工 `supported_groups` 匹配；与上一版 63.1% 不可直接比较，因为两道交集题重写、固定池重建。部分题的池内没有 gold 锚点页，LLM 标签只覆盖返回候选，池外召回缺失不会被补回。

## 距离正式 Golden 还差什么

1. 剩余 72 条 `llm_judge` 候选标签的人工抽检/校准。
2. K=10/20 的完整候选标注（当前 18 题、池 6–19 个成员，K≤5 稳定）。
3. 至少一次 20 题真实答案的逐事实/引用/来源/时间/拒答复核。
4. 保留集补约束题和拒答题；当前保留集没有这两类。
5. Qdrant 服务 artifact manifest 绑定，才能对 embedding/切分/rerank 做可归因实验。
