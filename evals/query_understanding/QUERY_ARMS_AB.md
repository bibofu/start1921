# 查询臂 A/B（开发题）

只使用开发集可答题；保留题未运行。基线与重写使用同一采集配置、同一检索计划；重写只增加 canonical/per-entity 查询臂。

| 指标 | baseline | rewrite | 变化 |
|---|---:|---:|---:|
| recall@20 | 0.582 | 0.582 | +0.000 |
| precision@5 | 0.631 | 0.655 | +0.024 |
| mrr@5 | 0.929 | 0.893 | -0.036 |
| ndcg@5 | 0.667 | 0.623 | -0.044 |

## 逐题

| 题 | 查询臂 | baseline R/P/MRR/nDCG | rewrite R/P/MRR/nDCG |
|---|---|---|---|
| `dev_exact_deng_1954` | 4 | 1.00 / N/A / 1.00 / N/A | 1.00 / N/A / 1.00 / N/A |
| `dev_exact_zhou_1954` | 1 | 0.50 / 1.00 / 1.00 / 0.92 | 0.50 / 1.00 / 1.00 / 0.92 |
| `dev_exact_zunyi_election` | 3 | 1.00 / 0.40 / 1.00 / 0.35 | 1.00 / 0.60 / 1.00 / 0.46 |
| `pilot_exact_deng_1952_appointment` | 1 | 1.00 / 0.60 / 1.00 / 0.63 | 1.00 / 0.60 / 1.00 / 0.65 |
| `dev_semantic_contradiction` | 1 | 0.67 / 0.80 / 1.00 / 0.92 | 0.67 / 0.80 / 1.00 / 0.92 |
| `dev_semantic_first_congress` | 0 | 0.00 / 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 / 0.00 |
| `dev_semantic_investigation` | 1 | 0.75 / 1.00 / 1.00 / 0.86 | 0.75 / 1.00 / 1.00 / 0.86 |
| `holdout_semantic_observation` | 4 | 0.40 / 0.20 / 1.00 / 0.61 | 0.40 / 0.20 / 0.50 / 0.39 |
| `dev_multi_mao_hunan` | 2 | 0.21 / 0.60 / 1.00 / 0.47 | 0.21 / 0.60 / 1.00 / 0.47 |
| `dev_multi_meetings` | 2 | 0.53 / 1.00 / 1.00 / 0.67 | 0.53 / 1.00 / 1.00 / 0.67 |
| `dev_multi_zhou_periods` | 2 | 0.29 / 0.80 / 1.00 / 0.75 | 0.29 / 0.80 / 1.00 / 0.90 |
| `dev_intersection_mao_zhou_1949` | 3 | 0.21 / 0.60 / 1.00 / 0.56 | 0.21 / 0.60 / 1.00 / 0.61 |
| `dev_constraint_history_isolation` | 2 | 0.83 / 1.00 / 1.00 / 0.94 | 0.83 / N/A / 1.00 / N/A |
| `dev_constraint_month_place` | 3 | 0.75 / 0.20 / 1.00 / 1.00 | 0.75 / N/A / 1.00 / N/A |
