# Golden 20 题本地组件基线（2026-10-29）

按用户 2026-10-29 裁定删除 9 题、改写 2 题并清理历史资产后，对当前 `golden_dataset.json` 的本地采集：20 题、18 可答/2 拒答、0 次生成模型调用。候选池和 98 条模型预标已完成，其中 20 条已人工抽检处理（18 条通过、2 条改判为 rel=1）、78 条仍待抽检；18 道可答题都有候选标签和固定池。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_dataset.json` |
| 数据集指纹 | `5b17338123f05acac8633dffbe8e2e76ae188241003222f8cf94f32a13f6460f` |
| 采集指纹 | `f080414cd8fdc75384c59fc1da7821b63709ed97d123a8131991a2cc4c6fdf1d` |
| 源码指纹 | `b85671ca3caf6c9e51e284d84bd7c52d5444fd53cb3d6c2f52e83eead7ff0f8e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false` |

## 结果

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 63.1%（18 题宏平均；微平均 46/93 组） |
| Precision@5 | 57.8%（18 题） |
| MRR@5 | 0.833（18 题） |
| 固定池 nDCG@5 | 0.666（18 题） |
| 正式 Recall@20 | 37.4%（5 道已批准题） |
| 正式 P/MRR/nDCG | 0 题（相关题目定义未批准；人工候选标签仅 10 条） |
| 生成模型调用 / Token | 0 / N/A |

限制：

- 18 道可答题都有固定池；8 题候选标签是 `agent_review`，78 条是 `llm_judge`，20 条已人工抽检，合计 193 条。
- **63.1% 的暂定 Recall 包含 98 条 LLM/人工抽检 `supported_groups` 匹配**；此前 49.4% 是无这些标签时的锚点/旧标签口径。两者不能直接当作“检索提升”。
- 部分新题的池内没有 gold 锚点页（例如 `holdout_semantic_observation`、`holdout_intersection_positive`）；LLM 只能标注返回的候选，池外召回缺失不会被标签补回。
- 20 条候选标签已人工处理（18 条通过、2 条改判为 rel=1），78 条仍待抽检；相关题目定义仍 pending，正式 P/MRR/nDCG 仍为 0 题。
- 答案未复核，Fact/Cit/来源/时间/路由/拒答均不可评。
- `index_attribution.attribution_safe=false`，原因仍是 Qdrant 服务集合没有独立可验证的 artifact manifest。
- 旧的 29 题版本及其清单已在 2026-10-29 清理；当前唯一工作集是 `golden_dataset.json`（20 题）。
