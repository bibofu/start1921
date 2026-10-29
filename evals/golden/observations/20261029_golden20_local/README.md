# Golden 20 题本地组件基线（2026-10-29）

按用户 2026-10-29 裁定删除 9 题、改写 2 题并清理历史资产后，对当前 `golden_dataset.json` 的本地采集：20 题、18 可答/2 拒答、0 次模型调用。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_dataset.json` |
| 数据集指纹 | `31eebe905a0d937d5a9662bf482c2d655ac93ea3942835caa53a394601d53071` |
| 采集指纹 | `493763fbcf2112339747c8d87a35a197ea83974f9cad70a48ca80add800fb95e` |
| 源码指纹 | `7584b632df12a039057bfafd4a3e4823d9da0ea6fb45f6037cefead25c492f3e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false` |

## 结果

| 指标 | 结果 |
|---|---:|
| 最终候选 Recall@20 | 49.4%（18 题宏平均；微平均 28/93 组） |
| Precision@5 | 65.0%（8 题） |
| MRR@5 | 0.875（8 题） |
| 固定池 nDCG@5 | 0.718（8 题） |
| 正式 Recall@20 | 37.4%（5 道已批准题） |
| 正式 P/MRR/nDCG | 0 题可评（无人工候选标签） |
| 模型调用 / Token | 0 / N/A |

限制：

- 8 道题有 Agent 候选标签和固定池；10 道可答题没有候选标签。
- 答案未复核，Fact/Cit/来源/时间/路由/拒答均不可评。
- `index_attribution.attribution_safe=false`，原因仍是 Qdrant 服务集合没有独立可验证的 artifact manifest。
- 旧的 29 题版本及其清单已在 2026-10-29 清理；当前唯一工作集是 `golden_dataset.json`（20 题）。
