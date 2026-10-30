# Golden 20 题本地组件基线（2026-10-30，r3）

按用户 2026-10-29 裁定删除 9 题、两次改写交集题并清理历史资产后，对当前 `golden_dataset.json` 的本地采集：20 题、18 可答/2 拒答、0 次生成模型调用。候选池已按新题面重建，19 条新增模型预标；当前共 192 条候选标签，其中 97 条已人工复核、95 条仍为 `agent_review`。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_dataset.json` |
| 数据集指纹 | `011c64f353679e53cdae0d028b521d0f9454f3b08435df552e7a3e98ffcab77e` |
| 采集指纹 | `dce19cd456c3967d7501f72c79a4703e06ec1df2942c2022d355546390f90839` |
| 源码指纹 | `b85671ca3caf6c9e51e284d84bd7c52d5444fd53cb3d6c2f52e83eead7ff0f8e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false` |

## 结果

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 59.3%（18 题宏平均；微平均 48/104 组） |
| Precision@5 | 58.9%（18 题） |
| MRR@5 | 0.861（18 题） |
| 固定池 nDCG@5 | 0.649（18 题） |
| 正式 Recall@20 | 53.2%（18 道可答题；微平均 44/104 组） |
| 正式 Precision@5 / MRR@5 | 0.54 / 0.85（各 10 题） |
| 生成模型调用 / Token | 0 / N/A |

限制：

- 固定池在 r2 采集上建立；r3 与 r2 的候选指纹逐题一致，池仍有效。
- 18 道可答题都有固定池；192 条候选标签中 97 条已人工复核（94 通过、3 改判）、95 条仍是 `agent_review`；`llm_judge` 已清零。
- **59.3% 的暂定 Recall 包含 97 条人工 `supported_groups` 匹配**；与上一版 63.1% 不可直接比较，因为两道交集题重写、固定池重建。
- 部分题的池内没有 gold 锚点页（`holdout_semantic_observation`、`dev_intersection_mao_zhou_1949`、`holdout_intersection_negative`、`holdout_intersection_positive`）；LLM 只能标注返回的候选，池外召回缺失不会被标签补回。
- 正式 Recall 覆盖 18 题，但正式 Precision/MRR 各覆盖 10 题，nDCG 仍为 0 题；不能据此判断排序质量。
- 答案未复核，Fact/Cit/来源/时间/路由/拒答均不可评。
- `index_attribution.attribution_safe=false`，原因仍是 Qdrant 服务集合没有独立可验证的 artifact manifest。
- 旧的 29 题版本及其清单已在 2026-10-29 清理；当前唯一工作集是 `golden_dataset.json`（20 题）。
