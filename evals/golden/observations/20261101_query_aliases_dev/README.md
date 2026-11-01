# 2026-11-01 Query alias 实验（未采纳）

## 假设

在 `config/query_aliases.json` 中加入 5 条**仅从开发题**推导的别名，利用现有 alias arm（raw query 始终保留，alias variant 与 raw 做 RRF），看是否能提升 Golden v1.2 的检索指标。

## 新增别名

| canonical | alias |
|---|---|
| 中共一大 | 党的头一次全国大会 |
| 中共一大 | 头一次全国大会 |
| 抗美援朝 | 出兵朝鲜 |
| 八路军总司令 | 八路军总指挥 |
| 八路军副总司令 | 八路军副总指挥 |

未加入 10 道保留题特有的别名（如“两参一改三结合”“恢复联合国合法席位”“井冈山会师”“开国大典”等），避免 test leakage。

## 实验身份

| 项目 | 基线 | alias v2 |
|---|---|---|
| `query_aliases.json` 条目 | 5 | 9 |
| 关键词索引 | 不变（`037df8ef...`） | 不变 |
| Capture | `data/reports/golden32_v1.2_20261101/capture.json` | `data/reports/golden32_alias_dev_20261101/capture.json` |
| Report | `data/reports/golden32_v1.2_20261101/report_llm_judge.json` | `data/reports/golden32_alias_dev_20261101/report.json` |

已确认 alias arm 实际生效。例如：

- `党的头一次全国大会` → `中共一大`
- `围绕出兵朝鲜` → `围绕抗美援朝`
- `八路军总指挥` → `八路军总司令`（raw 与 alias 两个查询都在 trace 里）

## 结果

| 指标 | 基线（全部） | alias v2（全部） | Δ | 开发集 Δ | 保留集 Δ |
|---|---:|---:|---:|---:|---:|
| Recall@1 | 0.3116 | 0.3116 | +0.0000 | +0.0000 | +0.0000 |
| Recall@5 | 0.5980 | 0.5980 | +0.0000 | +0.0000 | +0.0000 |
| Recall@10 | 0.6825 | 0.6825 | +0.0000 | +0.0000 | +0.0000 |
| Recall@12 | 0.6849 | 0.6849 | +0.0000 | +0.0000 | +0.0000 |
| Recall@20 | 0.7600 | 0.7600 | +0.0000 | +0.0000 | +0.0000 |
| Precision@5 | 0.6471 | 0.6250 | **-0.0221** | -0.0291 | +0.0000 |
| MRR@10 | 0.9231 | 0.9231 | +0.0000 | +0.0000 | +0.0000 |
| nDCG@5 | 0.7037 | 0.6968 | **-0.0070** | -0.0098 | +0.0000 |

逐题看，R@10 / MRR@10 / nDCG@5 没有任何题发生变化；P@5/nDCG@5 的小幅下降来自 alias arm 进入 RRF 后对部分题的候选排序稀释。

## 结论

**未采纳。**

- alias 确实被触发，但没有带来召回提升；
- RRF 等权融合 alias variant 会引入额外候选，P@5/nDCG@5 小幅下降；
- 保留集完全不变；
- 说明对当前 query，别名不是主要瓶颈；更关键的是检索覆盖/切分和候选排序。

已回退：

- `config/query_aliases.json` 恢复为 5 条；
- 关键词索引未改动，仍为基线 artifact `037df8ef...`。

## 下一步

不要再用“等权 RRF + 全量 alias variant”的方式做扩展。更值得试的是：

1. **只对高置信别名**启用 alias arm（例如 exact entity alias / congress name），不要对所有 phrased alias 等权融合；
2. **加权融合**：alias arm 权重低于 raw arm，或只在 raw arm 无有效命中时回退；
3. **补召回覆盖**：`holdout_exact_date`、`holdout_semantic_observation` 是章节/切分问题，不是 alias 问题；
4. **query expansion 单独评测**：把 expanded query 作为 rerank 的辅助信号，而不是直接并入候选池。
