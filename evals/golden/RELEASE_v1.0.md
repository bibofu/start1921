# Golden v1.0 冻结记录（2026-10-30）

本记录冻结当前 20 题评测集的身份、人工批准状态和检索基线。此后做 Top-K、embedding、rerank、切分或上下文策略实验时，必须引用本版本号；改动题目、事实、证据、标签或固定池后，版本号必须递增。

## 身份

| 项目 | 值 |
|---|---|
| 版本 | `golden-v1.0` |
| 数据集语义指纹 | `09fa20450c82430dc3d84b6c372f686dfb663c57e729b2621126a6e5c78de35f` |
| 数据集文件 SHA-256 | `a95bbc08b289a26bc8eb6850b3ff60859e4799620dba1738d34f52cc92a20d86` |
| 固定池文件 SHA-256 | `00554930e1b04e4b32cb91c80f00ca64ab67fe4c5324f75799d502c237e1bc4e` |
| 固定池清单指纹 | `c55beec3de9803f71f595fa06583000216e467a25a21105eb6837f4de582eacf` |
| 采集指纹 | `dce19cd456c3967d7501f72c79a4703e06ec1df2942c2022d355546390f90839` |
| 源码指纹 | `b85671ca3caf6c9e51e284d84bd7c52d5444fd53cb3d6c2f52e83eead7ff0f8e` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 代码基线提交 | `a8842c38681d5ea14f08f23762c2ae861569b07d` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=false`、`component_query=raw_question` |

## 规模与批准状态

| 项目 | 数值 |
|---|---:|
| 题目 | 20（15 开发 + 5 保留；18 可答 + 2 拒答） |
| 必要事实 / 证据组 | 98 / 104 |
| 题目定义批准 | 20 / 20 |
| 候选标签 | 182 / 182 人工复核（178 通过、4 改判） |
| 固定池批准 | 18 / 18 |
| Agent / LLM 标签 | 0 / 0 |

## 检索基线（正式口径）

| 指标 | 宏平均 | 微平均 | 可评题数 |
|---|---:|---:|---:|
| 必要证据组 Recall@20 | 0.592 | 48/104 = 0.462 | 18 |
| Precision@5 | 0.578 | — | 18 |
| MRR@5 | 0.861 | — | 18 |
| 固定池 nDCG@5 | 0.643 | — | 18 |

逐题结果：

| 题 | 分片 | R@20 | P@5 | MRR@5 | nDCG@5 |
|---|---|---:|---:|---:|---:|
| `dev_exact_deng_1954` | development | 1.000 | 0.600 | 1.000 | 0.563 |
| `dev_exact_zhou_1954` | development | 0.500 | 1.000 | 1.000 | 0.921 |
| `dev_exact_zunyi_election` | development | 1.000 | 0.400 | 1.000 | 0.348 |
| `pilot_exact_deng_1952_appointment` | development | 1.000 | 0.600 | 1.000 | 0.633 |
| `holdout_exact_date` | holdout | 1.000 | 0.400 | 0.500 | 0.659 |
| `dev_semantic_contradiction` | development | 0.667 | 0.800 | 1.000 | 0.922 |
| `dev_semantic_first_congress` | development | 0.000 | 0.000 | 0.000 | 0.000 |
| `dev_semantic_investigation` | development | 0.750 | 1.000 | 1.000 | 0.857 |
| `holdout_semantic_observation` | holdout | 0.000 | 0.000 | 0.000 | 0.000 |
| `dev_multi_mao_hunan` | development | 0.214 | 0.600 | 1.000 | 0.471 |
| `dev_multi_meetings` | development | 0.533 | 1.000 | 1.000 | 0.657 |
| `dev_multi_zhou_periods` | development | 0.286 | 0.800 | 1.000 | 0.750 |
| `holdout_multi_period` | holdout | 0.667 | 0.200 | 1.000 | 1.000 |
| `dev_intersection_mao_zhou_1949` | development | 0.214 | 0.600 | 1.000 | 0.556 |
| `holdout_intersection_negative` | holdout | 1.000 | 0.800 | 1.000 | 0.938 |
| `holdout_intersection_positive` | holdout | 0.250 | 0.400 | 1.000 | 0.369 |
| `dev_constraint_history_isolation` | development | 0.833 | 1.000 | 1.000 | 0.940 |
| `dev_constraint_month_place` | development | 0.750 | 0.200 | 1.000 | 1.000 |
| `dev_refusal_einstein` | development | N/A | N/A | N/A | N/A |
| `pilot_refusal_out_of_scope_2024` | development | N/A | N/A | N/A | N/A |

## 使用规则

1. 15 道开发题用于调参和诊断；5 道保留题只在最终验收时跑，不参与任何参数选择。
2. 实验一次只改一个变量；改动前后必须用同一版本、同一 K 集合和同一标注口径。
3. 每次实验至少记录：版本号、数据集/池/采集/语料指纹、代码提交、索引或 manifest、模型与参数、K 值、逐题结果、耗时与 token。
4. 未标注候选保持 unknown，不按 0 分；不可评指标保持 N/A。
5. 固定池 nDCG 只在该池内成立，不是全语料理想排序；K=10/20 因池规模 6–14 不稳定，当前只报告 K≤5。
6. `index_attribution.attribution_safe=false` 时，只能报告“改前/改后”结果，不能把差异归因到 embedding 或切分。

## 已知缺口

- 3 个固定池内没有任何锚点组：`dev_semantic_investigation`、`holdout_semantic_observation`、`holdout_intersection_negative`；`dev_multi_mao_hunan` 14 组只覆盖 3 组。
- 答案层未评测：0 次生成调用，Fact 覆盖、引用支持、来源/时间约束、路由与拒答均无分母。
- 保留集只有 5 题，且没有约束题和拒答题，独立验收能力不足。
- Qdrant 服务没有独立可验证的 artifact manifest，索引归因不安全。
- 已知约 74.7% 的 chunk 超过 512 字符 embedding 输入上限，尾部文本不影响向量，属于索引侧待验证风险。

## 变更规则

- 只改代码或索引：版本号不变，记录实验结果与代码提交。
- 改题目、事实、证据、标签或池：版本号递增（v1.1、v2.0…），旧基线不可与新版本直接比较。
- 保留题一旦用于调参，即失去保留资格，必须补充新的保留题。
