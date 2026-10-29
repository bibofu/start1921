# 当前评测集索引（selected20，2026-10-29）

按用户 2026-10-29 裁定，从 29 题中删除 9 题、改写 2 题后，当前工作集为 **20 题**。`development_annotations_v6.json`、`holdout_annotations_v1.json`、`DATASET_V1.md` 和 `CASE_INVENTORY_V1.md` 保留为历史版本。

## 总量

| 分层 | 题数 | 可答 / 拒答 | 必要事实 | 证据组 | 人工批准 |
|---|---:|---:|---:|---:|---:|
| 开发集 | 15 | 13 / 2 | 72 | 77 | 5 |
| 保留集 | 5 | 5 / 0 | 16 | 16 | 0 |
| **合计** | **20** | **18 / 2** | **88** | **93** | **5 / 20** |

- 当前数据集：[golden_v2_selected20.json](golden_v2_selected20.json)
- 逐题原文与状态：[CASE_INVENTORY_V2.md](CASE_INVENTORY_V2.md)
- 历史 29 题索引：[DATASET_V1.md](DATASET_V1.md)
- 历史 29 题逐题清单：[CASE_INVENTORY_V1.md](CASE_INVENTORY_V1.md)

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
| Precision@K | **8 道开发题，K≤5** | 95 条候选判断，全是 Agent 标签；K=10/20 多数 N/A |
| MRR@K | 8 道开发题，K=5 | 同上 |
| 固定池 nDCG@K | 8 道开发题，K=5 | 8 个固定池；不是全语料理想排序 |
| Fact/Cit | 旧 13 题中剩余的 8 道可答题 + 2024 拒答（Agent 评审） | 其余题没有可评真实答案 |
| 正式 R | **5 道已批准开发题** | 保留题 0 批准 |
| 正式 P/MRR/nDCG/Fact/Cit | **0 题** | 无人工候选标签/人工答案复核 |

无候选标签的 10 道可答题：

- 开发：`dev_exact_zunyi_election`、`dev_multi_meetings`、`dev_multi_mao_hunan`、`dev_intersection_mao_zhou_1949`、`dev_constraint_history_isolation`
- 保留：`holdout_exact_date`、`holdout_semantic_observation`、`holdout_multi_period`、`holdout_intersection_positive`、`holdout_intersection_negative`

## 本次本地运行

详见 [selected20 本地基线](observations/20261029_selected20_local/README.md)（完整 capture/report 留在本地忽略目录 `data/reports/selected20_local_20261029/`）：

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 49.4%（18 题宏平均；微平均 28/93 组） |
| Precision@5 | 65.0%（8 题） |
| MRR@5 | 0.875（8 题） |
| 固定池 nDCG@5 | 0.718（8 题） |
| 正式 Recall@20 | 37.4%（5 题） |
| 模型调用 / Token | 0 / N/A |

## 距离正式 Golden 还差什么

1. 15 道 `pending` 题的题目定义人工批准（当前 5/20）。
2. 10 道无候选标签的可答题补固定池和相关性标注。
3. K=10/20 的完整候选标注（当前只有 8 题、K≤5）。
4. 至少一次 20 题真实答案的逐事实/引用/来源/时间/拒答复核。
5. 保留集补约束题和拒答题；当前保留集没有这两类。
6. Qdrant 服务 artifact manifest 绑定，才能对 embedding/切分/rerank 做可归因实验。
