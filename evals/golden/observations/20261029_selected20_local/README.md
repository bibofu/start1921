# selected20 本地组件基线（2026-10-29）

按用户 2026-10-29 裁定删除 9 题、改写 2 题后的第一次本地采集：20 题、18 可答/2 拒答、0 次模型调用。

## 身份

| 项目 | 值 |
|---|---|
| 数据集 | `evals/golden/golden_v2_selected20.json` |
| 数据集指纹 | `d727f9cc27123c07ed7fb1f0c0d7f11ef33ae7d75f10895f843323d64bfd098c` |
| 采集指纹 | `e354c8ebbbb4233b3fe2e3199a68d43b353d88a4ac7ecb39e3b387f3dd5db2e6` |
| 源码指纹 | `4b06f0e1abec5da07a686238beaa8428e244d036f4c15339a966878f016df89f` |
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
- 本清单不替代历史 29 题版本；`DATASET_V1.md` 和 `CASE_INVENTORY_V1.md` 保留为历史资产。
