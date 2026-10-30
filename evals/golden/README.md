# Golden Dataset（selected20，2026-10-29）

当前评测集是 **20 题**：15 道开发题 + 5 道保留题，18 可答 + 2 拒答，98 个必要事实、104 个证据组。它是按用户 2026-10-29 裁定从原 29 题中删除 9 题并两次改写交集题后的唯一工作集；旧的 v3–v6 标注、协议、29 题集、旧复核队列和旧观测已清理。

## 入口

| 文件 | 内容 |
|---|---|
| [golden_dataset.json](golden_dataset.json) | 20 题数据集（PilotCase schema） |
| [DATASET.md](DATASET.md) | 总量、题型覆盖、指标可计算性、缺口 |
| [CASE_INVENTORY.md](CASE_INVENTORY.md) | 逐题原文、锚点、事实、拒答依据、状态 |
| [REPEATABLE_WORKFLOW.md](REPEATABLE_WORKFLOW.md) | 采集、复核、评分、比较命令 |
| [ANSWER_REVIEW_CALIBRATION.md](ANSWER_REVIEW_CALIBRATION.md) | 答案逐事实/维度复核口径 |
| [ranking_pools.json](ranking_pools.json) | 18 道可答题的固定池 |
| [label_reviews/20261030_llm63_reviewed.md](label_reviews/20261030_llm63_reviewed.md) | 63 条 LLM 标签复核记录（全部通过） |
| [observations/20261029_golden20_local/](observations/20261029_golden20_local/README.md) | 当前本地组件基线 |
| [observations/20261029_v6_live/](observations/20261029_v6_live/README.md) | 保留的历史真实模型观察（v6 数据已清理） |

## 当前状态

| 项目 | 数值 |
|---|---:|
| 开发题 / 保留题 | 15 / 5 |
| 可答 / 拒答 | 18 / 2 |
| 必要事实 / 证据组 | 98 / 104 |
| 有候选标签的题 | 18（95 条 Agent + 97 条人工，合计 192） |
| 有固定池的题 | 18 |
| 题目定义已批准 / 待审 | 20 / 0 |

- 正式 Recall@K 覆盖 18 道可答题；正式 Precision@5 与 MRR@5 各覆盖 10 题（0.54 / 0.85），nDCG/Fact/Cit 仍为 0 题。
- 暂定 Recall 覆盖 18 道可答题；暂定 Precision/MRR/nDCG 也覆盖 18 道，K≤5 稳定。
- `llm_judge` 已清零；97 条已人工复核，95 条 `agent_review` 仍待人工复核。
- 20 题定义全部已批准；保留集目前没有约束题和拒答题。
- 逐题状态和每一条原文见 [CASE_INVENTORY.md](CASE_INVENTORY.md)。

## 重要边界

- `approved` 只批准题目定义、来源、必要事实和回答边界，不批准候选标签、排序池或历史答案。
- 未标注候选是 unknown，不是 0 分；不可评指标保持 N/A。
- 固定池 nDCG 只在该池内成立，不是全语料理想排序。
- 当前 `golden_dataset.json` 是单轮 PilotCase schema，不含 v6 的多臂执行协议；`dev_constraint_history_isolation` 在本数据集中只作为单轮问题存在。
- Qdrant 服务没有独立可验证的 artifact manifest，`attribution_safe=false`；embedding/切分/rerank 的单变量归因仍需补 manifest。

## 历史

2026-10-29 清理后只保留：

- 当前 20 题数据集及其索引、逐题清单、固定池、当前本地基线；
- 一次历史真实模型观察 [20261029_v6_live](observations/20261029_v6_live/README.md)，用于对照；其原始 v6 标注/协议文件已不在仓库。
