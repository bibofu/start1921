# Golden 20 题本地组件基线（2026-10-30，r5，查询改写 v1）

按用户 2026-10-29 裁定删除 9 题、两次改写交集题并清理历史资产后，对当前 `golden_dataset.json` 的本地采集：20 题、18 可答/2 拒答、0 次生成模型调用。候选池已按新题面重建，19 条新增模型预标；当前共 182 条候选标签，全部人工复核。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_dataset.json` |
| 数据集指纹 | `c8d0cc4adfa4988426c94970f9f3bf267c113503e49564f1c66d20fd3a5da807` |
| 采集指纹 | `84e82397cb488a04629a0c8c3e5896bfe3090a99a9788cc6b0f2ca8771c2f98c` |
| 源码指纹 | `b85671ca3caf6c9e51e284d84bd7c52d5444fd53cb3d6c2f52e83eead7ff0f8e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false` |

## 结果

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 61.5%（18 题宏平均；微平均 50/104 组） |
| Precision@5 | 58.9%（18 题） |
| MRR@5 | 0.917（18 题） |
| 固定池 nDCG@5 | 0.678（18 题） |
| 正式 Recall@20 | 61.5%（18 道可答题；微平均 50/104 组） |
| 正式 Precision@5 / MRR@5 | 0.589 / 0.917（各 18 题） |
| 正式固定池 nDCG@5 | 0.678（18 题，池已人工批准） |
| 生成模型调用 / Token | 0 / N/A |

限制：

- 固定池在 r2 采集上建立；r3 与 r2 的候选指纹逐题一致，池仍有效。
- 18 道可答题都有固定池；182 条候选标签全部人工复核（178 通过、4 改判）；`agent_review` 与 `llm_judge` 均为 0。
- **59.3% 的暂定 Recall 包含 182 条人工 `supported_groups` 匹配**；与上一版 63.1% 不可直接比较，因为两道交集题重写、固定池重建。
- 部分题的池内没有 gold 锚点页（`holdout_semantic_observation`、`dev_intersection_mao_zhou_1949`、`holdout_intersection_negative`、`holdout_intersection_positive`）；LLM 只能标注返回的候选，池外召回缺失不会被标签补回。
- 正式 Recall/Precision/MRR/nDCG 均覆盖 18 题；Fact/Cit 仍未复核。
- 答案未复核，Fact/Cit/来源/时间/路由/拒答均不可评。
- `index_attribution.attribution_safe=false`，原因仍是 Qdrant 服务集合没有独立可验证的 artifact manifest。
- 旧的 29 题版本及其清单已在 2026-10-29 清理；当前唯一工作集是 `golden_dataset.json`（20 题）。
