# Golden v1.2 冻结记录（2026-11-01）

本版本接替 [v1.1](RELEASE_v1.1.md)。v1.1 的 20 题全部保留，新增 12 题，形成 **32 题**。

## 变更

**1. 新增 12 题**

- 精确事实：毛泽东思想写入党章；开国大典地点时间
- 语义：1956 年双百方针原因；鞍钢宪法“两参一改三结合”
- 多证据：长征期间召开的会议；两弹一星主要节点
- 交集/负例：朱德—彭德怀八路军正副总指挥；毛泽东—朱德井冈山会师
- 约束：1950 年 10 月抗美援朝决策；只依据《中国共产党历史》第一卷说明南昌起义背景
- 拒答：1950 年《婚姻法》是否允许纳妾；中国是否在 1972 年尼克松访华后才恢复联合国席位

**2. 新增 10 个固定池**

`dev_multi_long_march_meetings` 因 15 条长清单，池单独扩到三路各取前 20（37 个候选）；其余 9 题仍按三路各取前 5。全部池 `basis=human_review`，SHA 已重签。

**3. 新增 119 条候选标签**

全部人工复核通过，`basis=human_review`；没有 `agent_review` 或 `llm_judge` 残留。

**4. 新增答案/过程复核**

新增 10 道可答题使用 LLM 正式回答采集（`with_llm=true`），完成逐事实、引用、来源约束、时间约束、路由和拒答复核；过程复核 10 pass / 2 fail（A05、A07）。

## 身份

| 项目 | 值 |
|---|---|
| 版本 | `golden-v1.2-selected-32-20261101` |
| 数据集语义指纹 | `5df0d4a42b41bdc4ac55d461443ce6eea24971a82c519656f707b4cb94cbec22` |
| 数据集文件 SHA-256 | `14498c961972c01646789268b145ccac65ec511b78759dd659e6ac53fd557bf5` |
| 固定池文件 SHA-256 | `2a50e98e879ad2313e9eaf502b8ca0307ce4de29097d4e7da51e4a2f4a13a431` |
| 新增 12 题答案采集指纹 | `6606e314c8f156d2279fb32d834cf249ae981847a27b0cbdc9b02789633ce897` |
| 统一 32 题采集指纹 | `2c0d48f3bb9e968a57a6ec06177a34b0ca045529019213d304b491bbf6168f3d` |
| 源码指纹 | `ec05ca59dc895feaa9a977bf3c07c934ca8e1fd4e4173640b5e754ea989b5bf6` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 代码基线 | `87c105f`（统一 32 题采集时，`dirty=true`）；新增 12 题答案采集时为 `386fc42` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=true` |

## 规模

| 项目 | 数值 |
|---|---:|
| 题目 | 32（22 开发 + 10 保留；28 可答 + 4 拒答） |
| 必要事实 / 证据组 | 143 / 143 |
| 题目定义批准 | 32 / 32 |
| 候选标签 | 301 / 301 人工复核 |
| 固定池批准 | 28 / 28 |

## 指标

### v1.2 统一 32 题基线（2026-11-01，LLM 生产管线）

| 指标 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 0.3116 | 0.5122 | 0.5980 | 0.6825 | 0.7600 |
| Precision | 0.8148 | 0.7121 | 0.6471 | 0.4000 | 0.5000 |
| MRR | 0.8148 | 0.8889 | 0.9231 | 0.9231 | 0.9231 |
| 固定池 nDCG | 0.6667 | 0.6432 | 0.7037 | 0.3007 | 0.5168 |

- 28 个可答题参与排序指标；4 个拒答题 N/A。
- 线上对齐 Recall@12：0.6849（28 题）。
- P@5/nDCG@5 可评 17 题，MRR@10 可评 26 题；生产 final 命中里的池外候选按 unknown，不按 0 分。
- K=10/20 的 P/nDCG 只有长征题 1 题可评。
- 运行：90 次 HTTP 调用全部成功，0 degraded，285,890 Token；27 题 LLM 回答，5 题 `not_applicable`。
- 详见 [observations/20261101_v1.2_unified_run/README.md](observations/20261101_v1.2_unified_run/README.md)。

### v1.2 统一 32 题答案/过程复核（LLM judge provisional）

| 指标 | 结果 |
|---|---:|
| Required fact recall | **0.4085**（58/143 covered；报告分母 142） |
| Citation support | **0.7667**（23/30 适用题） |
| Source constraint | **1.0000** |
| Time constraint | **0.9583**（23/24 适用题） |
| Routing | **1.0000** |
| Safe refusal | **1.0000** |
| Scope explanation | **0.7500**（3/4 拒答题） |
| Answer pass | **0.3438**（11/32） |
| Process review | **28 pass / 4 fail** |

详见 [observations/20261101_v1.2_unified_run/REVIEWED.md](observations/20261101_v1.2_unified_run/REVIEWED.md)。本轮使用 `fact-coverage-v1` + `citation-entailment-v1` LLM judge 预标，写入 `basis=agent_review`；`approved_answer_aggregate` 为空。需先按 [CALIBRATION_QUEUE.md](observations/20261101_v1.2_unified_run/CALIBRATION_QUEUE.md) 人工校准 C01–C12。

## 使用规则

1. 22 道开发题用于调参；10 道保留题只在最终验收时跑，新增保留题不得用于调参。
2. 实验一次只改一个变量；引用本版本号和上述指纹。
3. 未标注候选保持 unknown；不可评指标保持 N/A。
4. `dev_multi_long_march_meetings` 的池内覆盖 10/15；5 个缺失证据组只能通过召回指标反映，不能用 nDCG 代替。
5. `index_attribution.attribution_safe=false` 时不能把差异归因到 embedding 或切分。

## 已知缺口

- 7 题 `citation_support` fail：2 题无引用，5 题存在未获引用支持的主张；建议优先抽检。
- 4 题过程 fail：`holdout_intersection_negative`、`holdout_intersection_positive`、`dev_intersection_zhu_peng_command` 为 planner 回退；`dev_multi_long_march_meetings` 为时间窗过宽。
- `dev_refusal_einstein` 的 `scope_explanation` 错误地说 1925 年超出 1921—1978 范围；应按缺乏可核实任职证据拒答。
- `dev_multi_long_march_meetings` 的 5 个证据组不在 capture 命中里：扎西、芦花、沙窝、阿西、俄界。
- P@5/nDCG@5 只有 17 题可评；生产 final 命中含池外未标注页。
- K=10/20 的 P/nDCG 受池大小限制；除长征题外，池只有 7–10 个候选。
- `dev_semantic_contradiction` 在统一采集中走了 26,827 字符的抽取式回答，建议单独排查。
- Qdrant 服务没有独立 artifact manifest。
