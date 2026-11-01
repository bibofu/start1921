# 当前评测集索引（32 题，2026-11-01，Golden v1.2）

2026-11-01 把 12 道新题并入 v1.1 的 20 题，形成 **32 题**：22 开发 + 10 保留，28 可答 + 4 拒答；143 个必要事实、143 个证据组、301 条候选标签。v1.1 的 20 题未删除、未改写；新增题的来源、证据和复核记录见 [DRAFT_v1.2_cases.json](DRAFT_v1.2_cases.json) 和 [label_reviews/20261101_llm119_reviewed.md](label_reviews/20261101_llm119_reviewed.md)。

## 总量

| 分层 | 题数 | 可答 / 拒答 | 必要事实 | 证据组 | 候选标签 | 人工批准 |
|---|---:|---:|---:|---:|---:|---:|
| 开发集 | 22 | 19 / 3 | 114 | 118 | 218 | 22 |
| 保留集 | 10 | 9 / 1 | 29 | 25 | 83 | 10 |
| **合计** | **32** | **28 / 4** | **143** | **143** | **301** | **32 / 32** |

- 当前数据集：[golden_dataset.json](golden_dataset.json)
- 冻结记录：[RELEASE_v1.2.md](RELEASE_v1.2.md)（v1.1 见 [RELEASE_v1.1.md](RELEASE_v1.1.md)）
- 新增 12 题逐题清单：[CASE_INVENTORY_v1.2.md](CASE_INVENTORY_v1.2.md)
- 候选标签复核：[20261101_llm119_reviewed.md](label_reviews/20261101_llm119_reviewed.md)
- 固定池：[ranking_pools.json](ranking_pools.json)（28 个）与 [POOL_REVIEW.md](POOL_REVIEW.md)
- 新增题 LLM 答案与过程复核：[observations/20261101_llm_answer_run/README.md](observations/20261101_llm_answer_run/README.md)

## 本次新增 12 题

| 类别 | 开发 | 保留 |
|---|---|---|
| 精确事实 | 毛泽东思想写入党章 | 开国大典地点时间 |
| 语义 | 1956 年双百方针原因 | 鞍钢宪法“两参一改三结合” |
| 多证据 | 长征期间召开的会议 | 两弹一星主要节点 |
| 交集/负例 | 朱德—彭德怀八路军正副总指挥 | 毛泽东—朱德井冈山会师 |
| 约束 | 1950 年 10 月抗美援朝决策 | 只依据《中国共产党历史》第一卷说明南昌起义背景 |
| 拒答 | 1950 年《婚姻法》是否允许纳妾 | 中国是否在 1972 年尼克松访华后才恢复联合国席位 |

## 题型覆盖

| 类别 | 开发 | 保留 | 合计 |
|---|---:|---:|---:|
| 精确事实/日期/职务 | 5 | 2 | 7 |
| 语义改写/观点 | 5 | 1 | 6 |
| 多证据/跨期/比较 | 4 | 2 | 6 |
| 人物交集/困难负例 | 2 | 3 | 5 |
| 约束/路由/多轮 | 3 | 1 | 4 |
| 拒答/错误前提/材料不足 | 3 | 1 | 4 |
| **合计** | **22** | **10** | **32** |

新增后保留集已覆盖六类；约束题和拒答题各有 1 道保留题。

## 指标可计算性

| 指标 | 当前可评范围 | 说明 |
|---|---|---|
| 必要证据组 Recall@K | **28 道可答题** | 主指标 K=10；线上对齐 K=12；K=20 仅诊断；拒答 4 题无正向分母 |
| Precision@K | **28 道可答题** | 28 个池全部人工批准；统一 32 题运行中 P@5 可评 17 题，K=10 仅 1 题；生产 final 命中含池外未知页，按 unknown 处理 |
| MRR@K | **28 道可答题** | 统一运行中 MRR@10 可评 26 题 |
| 固定池 nDCG@K | **28 道可答题** | 统一运行中 nDCG@5 可评 17 题；K=10 仅长征题池（37 个候选）可评 |
| Fact/Cit | **新增 10 道可答题** | 新增题有逐事实/引用/来源/时间/拒答复核；原有 18 道可答题仍无完整答案基准 |
| 正式 R | **28 道可答题** | 32 道批准题去掉 4 道拒答 |
| 正式 P@5 / MRR@10 / nDCG@5 | **17 / 26 / 17 题** | 受生产 final 池外未标注页影响；不可评题不按 0 分 |
| 正式 Fact / Cit | **10 题** | 仅新增 10 道可答题；原有 18 道仍 N/A |

301 条候选标签全部为 `human_review`；`agent_review` 与 `llm_judge` 均已清零。28 个固定池全部 `basis=human_review`。

## 当前运行

### v1.2 统一 32 题（2026-11-01，LLM 生产管线）

Capture：`data/reports/golden32_v1.2_20261101/capture.json`  
Report：`data/reports/golden32_v1.2_20261101/report.json`  
复核包：`data/reports/golden32_v1.2_20261101/reviews/index.html`

| 指标 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 0.3116 | 0.5122 | 0.5980 | 0.6825 | 0.7600 |
| Precision | 0.8148 | 0.7121 | 0.6471 | 0.4000 | 0.5000 |
| MRR | 0.8148 | 0.8889 | 0.9231 | 0.9231 | 0.9231 |
| 固定池 nDCG | 0.6667 | 0.6432 | 0.7037 | 0.3007 | 0.5168 |

| 可评题数 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 28 | 28 | 28 | 28 | 28 |
| Precision | 27 | 22 | 17 | 1 | 1 |
| MRR | 27 | 27 | 26 | 26 | 26 |
| 固定池 nDCG | 27 | 22 | 17 | 1 | 1 |

- 28 个可答题都有正向证据组分母；4 个拒答题不参与排序指标。
- 线上对齐 Recall@12：0.6849（28 题）。
- P@5/nDCG@5 只有 17 题可评：生产 final 命中里有多条候选不在固定池内，按 unknown 处理，不按 0 分。
- K=10/20 的 Precision/nDCG 只有长征题 1 题可评，池大小不足。
- 运行：90 次 HTTP 调用全部成功，0 degraded，285,890 Token；27 题 LLM 回答，5 题 `not_applicable`（2 拒答 + 2 无证据 + `dev_semantic_contradiction` 抽取式超长回答）。

### 新增 12 题答案复核（另一份 capture）

| 指标 | 结果 |
|---|---:|
| Required fact recall | 0.5333（24/45） |
| Citation support / routing / safe refusal / scope explanation | 1.000 / 1.000 / 1.000 / 1.000 |
| Time constraint | 0.9091（10/11 适用题） |
| Answer pass | 0.4167（5/12） |
| Process review | 10 pass / 2 fail（A05、A07） |

详细记录：[observations/20261101_llm_answer_run/REVIEWED.md](observations/20261101_llm_answer_run/REVIEWED.md)。统一 32 题 capture 的 answer/process 复核尚未完成，因此它的 `approved_answer_aggregate` 仍为空。

## 当前缺口

1. 统一 32 题 capture 的 answer/process 复核尚未完成；当前 Fact/Cit 只有新增 10 题有分母，`approved_answer_aggregate` 为空。
2. `dev_multi_long_march_meetings` 仍有 5 个证据组不在 capture 命中里（扎西、芦花、沙窝、阿西、俄界）；池内覆盖 10/15，池外召回缺失不能补回。
3. K=10/20 的 P/nDCG 受池大小限制；除长征题外，池只有 7–10 个候选。
4. Qdrant 服务仍没有独立可验证的 artifact manifest，`attribution_safe=false`；embedding/切分/rerank 的单变量归因仍需补 manifest。
5. `dev_semantic_contradiction` 在统一采集中走了 26,827 字符的抽取式回答，建议单独排查。
