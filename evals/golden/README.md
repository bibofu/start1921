# Golden Dataset（selected32，2026-11-01，v1.2）

当前评测集是 **32 题**：22 道开发题 + 10 道保留题，28 可答 + 4 拒答，143 个必要事实、143 个证据组、301 条候选标签。它在 v1.1 的 20 题基础上新增 12 题，未删除或改写旧题。

## 入口

| 文件 | 内容 |
|---|---|
| [golden_dataset.json](golden_dataset.json) | 32 题数据集（PilotCase schema） |
| [RELEASE_v1.2.md](RELEASE_v1.2.md) | Golden v1.2 冻结记录（当前版本） |
| [RELEASE_v1.1.md](RELEASE_v1.1.md) | Golden v1.1 历史记录 |
| [DATASET.md](DATASET.md) | 总量、题型覆盖、指标可计算性、缺口 |
| [CASE_INVENTORY_v1.2.md](CASE_INVENTORY_v1.2.md) | 新增 12 题的逐题清单 |
| [CASE_INVENTORY.md](CASE_INVENTORY.md) | v1.1 旧 20 题的逐题清单 |
| [ranking_pools.json](ranking_pools.json) | 28 道可答题的固定池 |
| [POOL_REVIEW.md](POOL_REVIEW.md) | 18 个旧池 + 10 个新增池的口径确认单 |
| [REPEATABLE_WORKFLOW.md](REPEATABLE_WORKFLOW.md) | 采集、复核、评分、比较命令 |
| [label_reviews/20261101_llm119_reviewed.md](label_reviews/20261101_llm119_reviewed.md) | 119 条新增候选标签人工复核记录 |
| [observations/20261101_llm_answer_run/README.md](observations/20261101_llm_answer_run/README.md) | 新增 12 题 LLM 正式回答采集 |
| [observations/20261101_llm_answer_run/REVIEWED.md](observations/20261101_llm_answer_run/REVIEWED.md) | 新增 12 题答案/过程复核结果 |
| [observations/20261101_v1.2_unified_run/README.md](observations/20261101_v1.2_unified_run/README.md) | v1.2 统一 32 题基线 |
| [observations/20261101_v1.2_unified_run/REVIEWED.md](observations/20261101_v1.2_unified_run/REVIEWED.md) | v1.2 统一 32 题答案/过程复核（LLM judge provisional） |
| [observations/20261101_v1.2_unified_run/CALIBRATION_QUEUE.md](observations/20261101_v1.2_unified_run/CALIBRATION_QUEUE.md) | LLM judge 人工校准队列 C01–C12 |
| [observations/20261030_current_run/README.md](observations/20261030_current_run/README.md) | v1.1 的 20 题当前重跑 |

## 当前状态

| 项目 | 数值 |
|---|---:|
| 开发题 / 保留题 | 22 / 10 |
| 可答 / 拒答 | 28 / 4 |
| 必要事实 / 证据组 | 143 / 143 |
| 候选标签 | 301 / 301 人工复核 |
| 固定池 | 28 / 28 人工批准 |
| 题目定义已批准 / 待审 | 32 / 0 |

- 新增 12 题：6 开发 + 6 保留，其中 10 可答 + 2 拒答。
- 新增 119 条候选标签全部 `human_review`；新增 10 个池全部 `basis=human_review`。
- 统一 32 题已完成答案/过程复核：27 题为 LLM 回答，5 题为抽取式或无证据；新增 10 题与原有 18 题都有答案分母。

## 指标摘要

### v1.2 统一 32 题基线（2026-11-01，LLM 生产管线）

| 指标 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 0.3116 | 0.5122 | 0.5980 | 0.6825 | 0.7600 |
| Precision | 0.8148 | 0.7121 | 0.6471 | 0.4000 | 0.5000 |
| MRR | 0.8148 | 0.8889 | 0.9231 | 0.9231 | 0.9231 |
| 固定池 nDCG | 0.6667 | 0.6432 | 0.7037 | 0.3007 | 0.5168 |

- 28 道可答题参与 Recall/Precision/MRR/nDCG；4 道拒答题 N/A。
- 线上对齐 Recall@12：0.6849（28 题）。
- P@5/nDCG@5 可评 17 题，MRR@10 可评 26 题；池外命中按 unknown，不按 0 分。
- K=10/20 的 P/nDCG 只有长征题 1 题可评。
- 详见 [observations/20261101_v1.2_unified_run/README.md](observations/20261101_v1.2_unified_run/README.md)。

### v1.2 统一 32 题答案/过程复核（LLM judge provisional）

| 指标 | 结果 |
|---|---:|
| Required fact recall | **0.4085**（58/143 covered） |
| Citation support | **0.7667**（23/30） |
| Source constraint | **1.0000** |
| Time constraint | **0.9583**（23/24） |
| Routing | **1.0000** |
| Safe refusal | **1.0000** |
| Scope explanation | **0.7500**（3/4） |
| Answer pass | **0.3438**（11/32） |
| Process review | **28 pass / 4 fail** |

高风险：7 题 citation fail、4 题 process fail、`dev_refusal_einstein` scope 说明错误。  
`approved_answer_aggregate` 为空；需按 [CALIBRATION_QUEUE.md](observations/20261101_v1.2_unified_run/CALIBRATION_QUEUE.md) 人工校准 C01–C12 后再升级。详见 [REVIEWED.md](observations/20261101_v1.2_unified_run/REVIEWED.md)。

## 重要边界

- `approved` 只批准题目定义、来源、必要事实和回答边界，不批准候选标签、排序池和历史答案。
- 未标注候选是 unknown，不是 0 分；不可评指标保持 N/A。
- 固定池 nDCG 只在该池内成立，不是全语料理想排序。
- `dev_multi_long_march_meetings` 的池覆盖 10/15 个证据组；扎西、芦花、沙窝、阿西、俄界 5 组不在 capture 命中里，不能补回池外召回。
- 当前 `golden_dataset.json` 是单轮 PilotCase schema，不含多臂执行协议。
- Qdrant 服务没有独立可验证的 artifact manifest，`attribution_safe=false`；embedding/切分/rerank 的单变量归因仍需补 manifest。

## 历史

- v1.0/v1.1：20 题（16 开发 + 4 保留）；v1.1 只改了查询改写和观察题归属。
- v1.2（2026-11-01）：在 20 题上新增 12 题，形成 32 题；新增题覆盖精确事实、语义、多证据、交集/负例、约束和拒答，并补齐保留集的约束题与拒答题。
