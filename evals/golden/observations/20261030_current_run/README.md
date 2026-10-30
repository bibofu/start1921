# 当前评测重跑（2026-10-30）

对当前代码和 `golden_dataset.json`（dataset v2.7，release v1.1）重新采集并评分：20 题、18 可答 / 2 拒答、16 开发 / 4 保留，0 次生成模型调用。

## 文件

- [CASES.md](CASES.md)：逐题报告，含指标、命中/缺失证据组、最终 Top 8、拒答依据
- [report.md](report.md)：评分器生成的多 K 组件报告
- [manifest.json](manifest.json)：身份、配置、汇总指标
- 本地原始文件：`data/reports/golden20_20261030_current/{capture,report}.json`

## 结果

| 指标 | 正式口径 |
|---|---:|
| Recall@10（主指标） | 59.2%（宏平均；微平均 48/104 组） |
| Recall@12（线上对齐） | 59.6%（宏平均；微平均 49/104 组） |
| Recall@20（诊断） | 61.5%（宏平均；微平均 50/104 组） |
| Precision@5 | 58.9% |
| MRR@10 | 0.917 |
| 固定池 nDCG@5 | 0.678 |

分类 Recall@10 均值：

| 类别 | 均值 |
|---|---:|
| 精确事实/职务 | 0.900 |
| 约束/路由 | 0.792 |
| 人物交集 | 0.464 |
| 语义检索 | 0.454 |
| 多证据/跨期 | 0.342 |

## 主要观察

1. 精确事实题稳定：5 题里 4 题 R@10 为 1.0，`dev_exact_zhou_1954` 为 0.5。
2. 多证据题是最大短板：`dev_multi_mao_hunan` 3/14 组、`dev_multi_meetings` 2/15 组、`dev_multi_zhou_periods` 1/7 组。
3. `dev_semantic_first_congress` 虽然池内 5/5 有锚点，但最终 R@10 为 0，说明召回/排序阶段把 gold 页挤掉了，不是标注问题。
4. `holdout_semantic_observation` 已从保留集移入开发集；R@10 0.4，PDF 143/146 仍未召回。
5. 3 个池内零锚点：`dev_semantic_investigation`、`holdout_semantic_observation`、`holdout_intersection_negative`；池覆盖和最终 Top10 召回要分开看。
6. 2 道拒答题只做了定义和拒绝依据，答案行为尚未人工复核；Fact/Cit/拒答正式指标仍为 0 题。

## 身份

| 项目 | 值 |
|---|---|
| 数据集指纹 | `c8d0cc4adfa4988426c94970f9f3bf267c113503e49564f1c66d20fd3a5da807` |
| 采集指纹 | `039a0b093ea93c651bfd6114fa2b54d1af06e78b3f43473258d9ccddf7b1434f` |
| 源码指纹 | `b525fa19e3c9cc08b17e09237a626a691d39c0095551be7d8b4b755c9bdd0841` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
