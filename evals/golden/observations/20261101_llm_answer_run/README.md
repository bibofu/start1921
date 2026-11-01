# 2026-11-01 LLM 答案采集（Golden v1.2 草案）

## 范围

- 数据集：[DRAFT_v1.2_cases.json](../../DRAFT_v1.2_cases.json)，12 题（10 可答 + 2 拒答）
- Run：`golden12_llm_20261101`
- Capture：`data/reports/golden12_llm_20261101/capture.json`（本地生成，不入库）
- 复核包：`data/reports/golden12_llm_20261101/reviews/index.html`

## 运行结果

| 项目 | 结果 |
|---|---:|
| 采集题数 | 12 |
| `llm_status=used` | 12 / 12 |
| degraded cases | 0 |
| HTTP 调用 | 34 |
| HTTP 失败 | 0 |
| 总 Token | 106,310 |
| Prompt Token | 98,510 |
| Completion Token | 7,800 |
| Cache Hit / Miss | 29,184 / 69,326 |
| 检索平均耗时 | 214 ms |
| 回答平均耗时 | 13,061 ms |
| 回答最长耗时 | 42,955 ms |

调用记录中的 `request_model` 为 `deepseek-v4-flash`，`response_model` 为 `deepseek-flash`。这是本次生产回答管线的实际调用模型，不是候选标签 judge 的模型。

## 过程状态

- Query planner：11 题 `used`，1 题 `fallback`（`dev_intersection_zhu_peng_command`，`invalid_plan`，回退到本地计划）
- Retrieval reflection：9 题 `skipped`，3 题 `retried`（`dev_semantic_double_hundred`、`dev_multi_long_march_meetings`、`holdout_multi_two_bombs_satellite`）
- 全部 12 题 `evidence_status=partial`
- 全部 12 题 `uncited_claims=0`
- 所有回答都带 citations；拒答题也给出了纠正性回答，不是空白拒答

## 复核完成（2026-11-01）

- `answer_reviews.json` / `process_reviews.json` 已按 A01–A12 复核并导入
- `approved_answer_aggregate` 已生成：
  - required_fact_recall 0.5333（24/45）
  - citation_support 1.0；routing 1.0；safe_refusal 1.0；scope_explanation 1.0
  - time_constraint 0.9091；answer_pass 0.4167（5/12）
- 过程复核：10 pass / 2 fail（A05、A07）
- 详见 [REVIEWED.md](REVIEWED.md)

## 下一步

1. 合并 Golden v1.2：更新 `golden_dataset.json` 和 `ranking_pools.json`
2. 同步更新 `DATASET.md`、`README.md` 和 `test_golden_dataset.py` 的 20 题硬编码
3. 重新跑全量指标并冻结 v1.2
