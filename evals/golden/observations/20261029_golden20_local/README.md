# Golden 20 题本地组件基线（2026-10-29）

按用户 2026-10-29 裁定删除 9 题、改写 2 题并清理历史资产后，对当前 `golden_dataset.json` 的本地采集：20 题、18 可答/2 拒答、0 次生成模型调用。候选池和 98 条 LLM 相关性预标已完成；18 道可答题都有候选标签和固定池。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_dataset.json` |
| 数据集指纹 | `f249d99737bb266ddcc1e105d4168d0cb97271ccd00125d9c5fe288c798978d1` |
| 采集指纹 | `153a6ebecd94d4445beeef022bf9a00d613d675e8a1eeb637d28604cf2d5bcb8` |
| 源码指纹 | `b85671ca3caf6c9e51e284d84bd7c52d5444fd53cb3d6c2f52e83eead7ff0f8e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false` |

## 结果

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 63.1%（18 题宏平均；微平均 46/93 组） |
| Precision@5 | 57.8%（18 题） |
| MRR@5 | 0.833（18 题） |
| 固定池 nDCG@5 | 0.664（18 题） |
| 正式 Recall@20 | 37.4%（5 道已批准题） |
| 正式 P/MRR/nDCG | 0 题可评（无人工候选标签） |
| 生成模型调用 / Token | 0 / N/A |

限制：

- 18 道可答题都有固定池；8 题候选标签是 `agent_review`，98 条是 `llm_judge`，合计 193 条。
- **63.1% 的暂定 Recall 包含 98 条 LLM `supported_groups` 匹配**；此前 49.4% 是无这些标签时的锚点/旧标签口径。两者不能直接当作“检索提升”。
- 部分新题的池内没有 gold 锚点页（例如 `holdout_semantic_observation`、`holdout_intersection_positive`）；LLM 只能标注返回的候选，池外召回缺失不会被标签补回。
- LLM 标签尚未人工抽检；正式 P/MRR/nDCG 仍为 0 题。
- 答案未复核，Fact/Cit/来源/时间/路由/拒答均不可评。
- `index_attribution.attribution_safe=false`，原因仍是 Qdrant 服务集合没有独立可验证的 artifact manifest。
- 旧的 29 题版本及其清单已在 2026-10-29 清理；当前唯一工作集是 `golden_dataset.json`（20 题）。
