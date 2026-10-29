# 当前评测集索引（20 题，2026-10-29）

按用户 2026-10-29 裁定，从 29 题中删除 9 题、改写 2 题后，当前工作集为 **20 题**。旧 v3–v6 标注、协议、29 题集、旧复核队列和旧观测已清理；本文件是当前唯一数据集索引。

## 总量

| 分层 | 题数 | 可答 / 拒答 | 必要事实 | 证据组 | 人工批准 |
|---|---:|---:|---:|---:|---:|
| 开发集 | 15 | 13 / 2 | 72 | 77 | 5 |
| 保留集 | 5 | 5 / 0 | 16 | 16 | 0 |
| **合计** | **20** | **18 / 2** | **88** | **93** | **5 / 20** |

- 当前数据集：[golden_dataset.json](golden_dataset.json)
- 逐题原文与状态：[CASE_INVENTORY.md](CASE_INVENTORY.md)
- LLM 标签抽检：[LLM_LABEL_REVIEW.md](LLM_LABEL_REVIEW.md)
- 88 条待抽检标签：[LLM_LABELS_PENDING.md](LLM_LABELS_PENDING.md)
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

改写 2 题：

- `dev_intersection_mao_zhou_1949` → “毛泽东与周恩来在1949年有哪些有共同出席的会议？”；只保留 6月7日会见陈嘉庚、9月25日座谈会、10月24日接见傅作义三条会议事实。
- `holdout_intersection_positive` → “刘伯承和邓小平有哪些共同指挥的战役？”；改为邯长（1939）、上党（1945）、陇海（1946）、定陶（1946）四个战役。

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
| Precision@K | **18 道可答题，K≤5 稳定** | 193 条判断：95 条 Agent + 78 条 LLM + 20 条人工处理（18 通过、2 改判）；K=10/20 受池大小/池外候选限制 |
| MRR@K | 18 道可答题，K≤5 | 同上 |
| 固定池 nDCG@K | 18 道可答题，K≤5 | 18 个固定池；不是全语料理想排序 |
| Fact/Cit | 旧 13 题中剩余的 8 道可答题 + 2024 拒答（Agent 评审） | 其余题没有可评真实答案 |
| 正式 R | **5 道已批准开发题** | 保留题 0 批准 |
| 正式 P/MRR/nDCG/Fact/Cit | **0 题** | 无人工候选标签/人工答案复核 |

18 道可答题都有固定池。其中 8 题的候选标签是 `agent_review`，10 题共 98 条模型标签：20 条已由用户人工处理（18 条通过、2 条改判为 rel=1；basis=`human_review`），78 条仍是 `llm_judge`。人工抽检不改变题目定义的 pending 状态。

## 本次本地运行

详见 [Golden 20 题本地基线](observations/20261029_golden20_local/README.md)（完整 capture/report 留在本地忽略目录 `data/reports/golden20_human20b_20261029/`）：

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 63.1%（18 题宏平均；微平均 46/93 组） |
| Precision@5 | 57.8%（18 题） |
| MRR@5 | 0.833（18 题） |
| 固定池 nDCG@5 | 0.666（18 题） |
| 正式 Recall@20 | 37.4%（5 题） |
| 生成模型调用 / Token | 0 / N/A |

注意：63.1% 的暂定 Recall 包含 98 条 LLM/人工抽检 `supported_groups` 匹配，不能与无这些标签时的 49.4% 直接比较为“检索提升”；正式 Recall 仍只按 5 道已批准题的冻结锚点计算。部分新题的池内没有 gold 锚点页，LLM 标签只覆盖返回候选，池外召回缺失不会被补回。

## 距离正式 Golden 还差什么

1. 15 道 `pending` 题的题目定义人工批准（当前 5/20）。
2. 剩余 78 条 `llm_judge` 候选标签的人工抽检/校准。
3. K=10/20 的完整候选标注（当前 18 题、池 6–19 个成员，K≤5 稳定）。
4. 至少一次 20 题真实答案的逐事实/引用/来源/时间/拒答复核。
5. 保留集补约束题和拒答题；当前保留集没有这两类。
6. Qdrant 服务 artifact manifest 绑定，才能对 embedding/切分/rerank 做可归因实验。
