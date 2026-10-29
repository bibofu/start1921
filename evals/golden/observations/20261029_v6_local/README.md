# v6 开发集本地基线（2026-10-29）

这是 v6 标注/协议发布后的第一次完整采集：20 道开发题、21 个输入（含淮海无历史控制臂），**只运行本地关键词/向量/融合/选择与摘录回答，没有调用任何外部模型**。它证明 v6 已恢复可采集，并为后续真实模型和 harness 实验提供同口径的组件基线。

## 身份

| 项目 | 值 |
|---|---|
| 题集 | `evals/golden/development_annotations_v6.json` |
| 题集指纹 | `513b684429d8ba5bf069f9c0d4b3c94415224f2529e160992c2dacea05dfebee` |
| 协议 | `evals/golden/development_protocols_v6.json` |
| 协议文件 SHA-256 | `8aa9b7e9d09a985fb18799da78db57a79030460fb06405250bc26c4ee2f31e9a` |
| 采集指纹 | `1a31f74cc8ff6929c94c63b56c14961fbe0f134caf10680deb759761e4dfdb8f` |
| 源码指纹 | `33efedce2bd57c76c764ccaf8e241259bce6ca37b3a20f129a7bbefc485e86f4` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 采集时 git | `d040925`，`dirty=true`（评测数据/文档在同一提交前修改） |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、组件查询为原始问题、`with_llm=false` |

采集和完整评分报告不进入 Git；本地路径与哈希见 [manifest.json](manifest.json)。下表数值均来自 [report.md](report.md)。

## 组件检索（最终候选）

| 口径 | K | 必要证据 Recall | Precision | MRR | 固定池 nDCG |
|---|---:|---:|---:|---:|---:|
| 暂定（Agent 标签） | 5 | 0.486（17/20） | 0.700（12/20） | 0.917（12/20） | 0.731（12/20） |
| 暂定 | 10 | 0.597（17/20） | 0.367（3/20） | 0.917（12/20） | 0.589（3/20） |
| 暂定 | 20 | 0.609（17/20） | N/A（0/20） | 1.000（11/20） | N/A（0/20） |
| **正式（人工批准）** | 5 | **0.455（8/20）** | N/A（0/20） | N/A（0/20） | N/A（0/20） |
| **正式** | 10 | **0.567（8/20）** | N/A（0/20） | N/A（0/20） | N/A（0/20） |
| **正式** | 20 | **0.567（8/20）** | N/A（0/20） | N/A（0/20） | N/A（0/20） |

各阶段 K=20 的暂定宏平均：关键词候选 **64.9%**、向量候选 **44.1%**、融合 **66.3%**、最终候选 **60.9%**（17 道可答题）。向量分支继续明显弱于关键词，融合到最终选择仍有约 5.4pp 损耗。

“正式”列只覆盖 8 道题目定义已人工批准的题，且只计算冻结锚点 Recall；它不使用 Agent 候选标签，所以没有任何 Precision/MRR/nDCG 可评。暂定列使用 12 道题的 196 条 Agent 候选判断，只能作诊断。

## 逐题观察

正式 Recall@20（仅 8 道已批准题）：

| 题 | 命中/分母 |
|---|---:|
| `pilot_semantic_deng_1962_agriculture` | 2/3 |
| `pilot_multievidence_zunyi_leadership` | 4/4 |
| `pilot_constraint_deng_1973_march` | 2/2 |
| `dev_exact_zhou_1954` | 3/6 |
| `dev_constraint_month_place` | 3/4 |
| `dev_multi_zhou_periods` | 2/7 |
| `dev_semantic_investigation` | 0/4 |
| `dev_semantic_contradiction` | 1/3 |

暂定 Recall@20（5 道尚无候选标签的新可答题，只作召回诊断）：

| 题 | 命中/分母 |
|---|---:|
| `dev_exact_zunyi_election` | 1/1 |
| `dev_multi_meetings` | 1/15 |
| `dev_constraint_history_isolation` | 3/12 |
| `dev_multi_mao_hunan` | 3/14 |
| `dev_intersection_mao_zhou_1949` | 1/5 |

这几道复杂题的召回明显偏低；在给它们补候选相关性之前，不能计算 Precision/MRR/nDCG，也不能据此判断 reranker 的收益。

## 限制

- **没有真实模型运行**：HTTP 调用 0，Token N/A；答案、引用、来源/时间约束、拒答和范围说明全部待复核。
- **排序归因不安全**：`index_attribution.attribution_safe=false`，原因是 Qdrant 服务集合没有独立可验证的 artifact manifest；关键词侧 manifest 已校验。组件排序与 2026-10-11 的 v3 采集逐阶段相同，但不能据此单独归因 embedding/切分变化。
- **候选标签仍是 Agent 暂定**：196 条判断全部是 `agent_review`；12 道题有标签，5 道新可答题没有，3 道拒答无检索分母。
- **12 题题目定义待审**，10 道保留题仍无事实/证据标注。

## 复现

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset evals/golden/development_annotations_v6.json `
  --protocols evals/golden/development_protocols_v6.json `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --run-name development20_v6_local_20261029 `
  --output data/reports/eval_development20_v6_20261029/capture.json

.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/development_annotations_v6.json `
  --protocols evals/golden/development_protocols_v6.json `
  --capture data/reports/eval_development20_v6_20261029/capture.json `
  --ranking-pools evals/golden/ranking_pools_v2.json `
  --k-values 1 3 5 10 20 `
  --output data/reports/eval_development20_v6_20261029/report.json
```
