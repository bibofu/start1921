# 2026-11-01 Golden v1.2 统一 32 题答案/过程复核

- 复核人：`user_in_current_chat`
- 复核方式：LLM fact/citation judge 预标 + 规则归类；用户授权继续。高风险题已单列，建议后续人工抽检。
- 复核包：`data/reports/golden32_v1.2_20261101/reviews/`
- 导入结果：`data/reports/golden32_v1.2_20261101/reviewed/`
- 正式评分：`data/reports/golden32_v1.2_20261101/report_approved.json`

## 正式答案指标

| 指标 | 结果 |
|---|---:|
| required_fact_recall | **0.4085**（58/143 条事实为 covered；报告分母 142） |
| citation_support | **0.7667**（23/30 适用题） |
| source_constraint | **1.0000** |
| time_constraint | **0.9583**（23/24 适用题） |
| routing | **1.0000** |
| safe_refusal | **1.0000** |
| scope_explanation | **0.7500**（3/4 拒答题） |
| answer_pass | **0.3438**（11/32） |

过程复核：**28 pass / 4 fail**。

## 事实覆盖

143 条必要事实：**covered 58 / partial 28 / missing 57**。

| 题 | covered | partial | missing |
|---|---:|---:|---:|
| `dev_exact_deng_1954` | 2 | 0 | 0 |
| `dev_exact_zhou_1954` | 1 | 2 | 3 |
| `dev_exact_zunyi_election` | 1 | 0 | 0 |
| `pilot_exact_deng_1952_appointment` | 1 | 0 | 0 |
| `holdout_exact_date` | 0 | 0 | 2 |
| `dev_semantic_contradiction` | 3 | 0 | 0 |
| `dev_semantic_first_congress` | 2 | 3 | 0 |
| `dev_semantic_investigation` | 2 | 1 | 1 |
| `holdout_semantic_observation` | 0 | 0 | 5 |
| `dev_multi_mao_hunan` | 4 | 3 | 7 |
| `dev_multi_meetings` | 4 | 6 | 2 |
| `dev_multi_zhou_periods` | 3 | 1 | 3 |
| `holdout_multi_period` | 1 | 0 | 2 |
| `dev_intersection_mao_zhou_1949` | 4 | 0 | 10 |
| `holdout_intersection_negative` | 2 | 0 | 0 |
| `holdout_intersection_positive` | 1 | 1 | 1 |
| `dev_constraint_history_isolation` | 3 | 1 | 6 |
| `dev_constraint_month_place` | 2 | 1 | 1 |
| `dev_exact_mao_thought_party_constitution` | 1 | 1 | 0 |
| `holdout_exact_founding_ceremony` | 1 | 0 | 1 |
| `dev_semantic_double_hundred` | 0 | 2 | 1 |
| `holdout_semantic_angang_constitution` | 4 | 0 | 0 |
| `dev_multi_long_march_meetings` | 2 | 2 | 11 |
| `holdout_multi_two_bombs_satellite` | 4 | 1 | 1 |
| `dev_intersection_zhu_peng_command` | 2 | 0 | 0 |
| `holdout_intersection_mao_zhu_jinggangshan` | 2 | 1 | 0 |
| `dev_constraint_korean_war_decision` | 2 | 2 | 0 |
| `holdout_constraint_nanchang_uprising_background` | 4 | 0 | 0 |

## 主要失败点

### citation_support fail（7 题）

`holdout_exact_date`、`holdout_semantic_observation`、`dev_multi_zhou_periods`、`holdout_intersection_positive`、`dev_constraint_history_isolation`、`dev_multi_long_march_meetings`、`holdout_multi_two_bombs_satellite`。

- 前两题无引用、无证据；
- 其余 5 题有具体“主张未被所标引文支持”的条目，详见 `llm_fact_citation.json` 的 `citation_judge.unsupported_claims`。

### 过程 fail（4 题）

- `holdout_intersection_negative`
- `holdout_intersection_positive`
- `dev_intersection_zhu_peng_command`
- `dev_multi_long_march_meetings`

前三题是 query planner `invalid_plan` 后回退，执行计划没有完整 `search_queries`；长征题是计划时间窗过宽（1934—1936）并纳入瓦窑堡会议。

### 拒答边界

- `dev_refusal_einstein`：`safe_refusal=pass`，但 `scope_explanation=fail`。答案称“1925年超出1921—1978范围”，这是错的；1925 在库范围内，应按缺乏可核实任职证据拒答。
- `pilot_refusal_out_of_scope_2024`、`dev_refusal_marriage_law_concubinage`、`holdout_refusal_un_seat_timing`：safe_refusal / scope_explanation 均 pass。

### 其他异常

- `dev_semantic_contradiction` 走 26,827 字符抽取式回答，`llm_status=not_applicable`；检索答案质量未受 LLM 生成影响，建议单独排查。
- `holdout_exact_date`、`holdout_semantic_observation` 是检索缺口，答案只说“索引中未找到章节”，事实覆盖为 0。
- `dev_multi_long_march_meetings` 仍只有 2 个 covered（通道、遵义），俄界为 partial，其余 11 个 missing；与之前 12 题 capture 的结果接近。

## 结论

- 统一 32 题的检索/排序和答案/过程指标现在都有正式分母。
- 答案层的主要问题是**事实完整性**（covered 58/143）和 **5 题引用支持失败**，不是拒答安全。
- 建议优先人工抽检：7 个 citation fail 题、4 个 process fail 题、`dev_refusal_einstein` 的 scope 理由。
