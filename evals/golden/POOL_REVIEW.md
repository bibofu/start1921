# 固定池口径确认单（18 个池）

本单只确认 **nDCG 的评分池**：18 道可答题各有一个固定候选池，池内成员和构造规则一经批准，就成为正式 nDCG 的分母。它不批准检索质量、不批准候选标签、也不批准答案。

## 构造规则

1. 用**原始问题**（不经过 LLM 规划）调用关键词检索、向量检索和最终排序；
2. 三路各取**前 5 条**返回片段；
3. 按证据单元身份去重（文献 + 页码 + 归一化文本 SHA），得到并集；
4. 池内每条候选都已有一个人工相关性判断（0/1/2）；
5. nDCG 只在池内计算，gain = 2^rel−1，discount = log2(rank+1)，重复片段只计第一次。

## 18 个池

| 题 | 分片 | 候选 | 已标 | 缺标 | 证据组 | 池内锚点组 | rel 2/1/0 | 池 SHA |
|---|---|---:|---:|---:|---:|---:|---|---|
| `dev_exact_deng_1954` | development | 9 | 9 | 0 | 2 | 2 | 3/2/4 | `b3b17d0947bc` |
| `dev_exact_zhou_1954` | development | 9 | 9 | 0 | 6 | 3 | 2/5/2 | `2b6577b07020` |
| `dev_exact_zunyi_election` | development | 11 | 11 | 0 | 1 | 1 | 2/3/6 | `37498b50ac04` |
| `pilot_exact_deng_1952_appointment` | development | 9 | 9 | 0 | 1 | 1 | 2/4/3 | `d8928f5a5e65` |
| `holdout_exact_date` | holdout | 6 | 6 | 0 | 2 | 2 | 1/1/4 | `2858fb06eba6` |
| `dev_semantic_contradiction` | development | 12 | 12 | 0 | 3 | 2 | 1/4/7 | `f4f58744bcf3` |
| `dev_semantic_first_congress` | development | 13 | 13 | 0 | 5 | 5 | 3/0/10 | `89fa8fde7a43` |
| `dev_semantic_investigation` | development | 14 | 14 | 0 | 4 | 0 | 12/2/0 | `d6fd5d892d45` |
| `holdout_semantic_observation` | holdout | 11 | 11 | 0 | 5 | 0 | 0/2/9 | `4c74615118eb` |
| `dev_multi_mao_hunan` | development | 11 | 11 | 0 | 14 | 3 | 3/3/5 | `a07d394dab92` |
| `dev_multi_meetings` | development | 11 | 11 | 0 | 15 | 2 | 6/5/0 | `afe51b8371fb` |
| `dev_multi_zhou_periods` | development | 10 | 10 | 0 | 7 | 1 | 1/5/4 | `e50f3e8c9b8d` |
| `holdout_multi_period` | holdout | 9 | 9 | 0 | 3 | 1 | 1/0/8 | `a57914ba31c1` |
| `dev_intersection_mao_zhou_1949` | development | 9 | 9 | 0 | 14 | 1 | 3/1/5 | `4d96fa6cb139` |
| `holdout_intersection_negative` | holdout | 11 | 11 | 0 | 2 | 0 | 2/8/1 | `e0438bd8fd47` |
| `holdout_intersection_positive` | holdout | 10 | 10 | 0 | 4 | 1 | 2/4/4 | `10f5396990d8` |
| `dev_constraint_history_isolation` | development | 8 | 8 | 0 | 12 | 5 | 4/2/2 | `dffd111332e2` |
| `dev_constraint_month_place` | development | 9 | 9 | 0 | 4 | 1 | 1/0/8 | `8fd50b0b57a2` |

合计：18 个池、182 个候选单元、182 条人工标签，缺标 0。

## 已知边界

- 池只覆盖三路前 5 的并集，规模 6–14 条，因此 **K=10/20 的 Precision/nDCG 不稳定**；当前只用 K≤5 的排序指标。
- 3 个池内没有任何锚点组（`dev_semantic_investigation`、`holdout_semantic_observation`、`holdout_intersection_negative`）。这是检索召回缺口，不是池构造错误；批准池不会把这些缺口补上。
- 池是在 r2 采集上建立的；r3 与 r2 的候选指纹逐题一致，所以池对当前 r3 仍然有效。
- 批准后正式 nDCG 的分母是 18 道可答题；拒答题不参与排序指标。

## 确认

- [ ] 批准全部 18 个池，正式 nDCG 按上述规则计算
- [ ] 只批准部分池（请写题 ID）
- [ ] 不批准，池构造规则需要改（请写改法）
