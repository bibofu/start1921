# 2026-11-01 Golden v1.2 统一 32 题基线

## 范围

- 数据集：[golden_dataset.json](../../golden_dataset.json)，32 题（22 开发 + 10 保留；28 可答 + 4 拒答）
- Run：`golden32_v1.2_20261101`
- Capture：`data/reports/golden32_v1.2_20261101/capture.json`
- 报告：`data/reports/golden32_v1.2_20261101/report.json`
- 复核包：`data/reports/golden32_v1.2_20261101/reviews/index.html`
- 配置：`candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=true`

## 运行结果

| 项目 | 结果 |
|---|---:|
| 题数 | 32 |
| 可答 / 拒答 | 28 / 4 |
| HTTP 调用 | 90 |
| HTTP 失败 | 0 |
| degraded cases | 0 |
| 总 Token | 285,890 |
| Prompt / Completion | 268,970 / 16,920 |
| Cache Hit / Miss | 101,248 / 167,722 |
| `llm_status=used` | 27 |
| `llm_status=not_applicable` | 5 |
| `evidence_status=partial` | 27 |
| `evidence_status=supported` | 1 |
| `evidence_status=no_evidence` | 4 |
| `uncited_claims` | 0 |

`llm_status=not_applicable` 的 5 题：

- `holdout_exact_date`：无证据，抽取式回答
- `dev_semantic_contradiction`：抽取式回答（26,827 字符，异常长，建议单查）
- `holdout_semantic_observation`：无证据，抽取式回答
- `dev_refusal_einstein`：拒答题
- `pilot_refusal_out_of_scope_2024`：拒答题

## 正式检索/排序指标（final 阶段）

| 指标 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 0.3116 | 0.5122 | 0.5980 | 0.6825 | 0.7600 |
| Precision | 0.8148 | 0.7121 | 0.6471 | 0.4000 | 0.5000 |
| MRR | 0.8148 | 0.8889 | 0.9231 | 0.9231 | 0.9231 |
| 固定池 nDCG | 0.6667 | 0.6432 | 0.7037 | 0.3007 | 0.5168 |

可评题数：

| 指标 | K=1 | K=3 | K=5 | K=10 | K=20 |
|---|---:|---:|---:|---:|---:|
| Required group recall | 28 | 28 | 28 | 28 | 28 |
| Precision | 27 | 22 | 17 | 1 | 1 |
| MRR | 27 | 27 | 26 | 26 | 26 |
| 固定池 nDCG | 27 | 22 | 17 | 1 | 1 |

- 28 个可答题都有正向证据组分母；4 个拒答题不参与 Recall/Precision/MRR/nDCG。
- 线上对齐 Recall@12：0.6849（28 题）。
- P@5/nDCG@5 只有 17 题可评，因为生产 final 命中里有多条候选不在固定池内，按 unknown 处理，不按 0 分。
- K=10/20 的 Precision/nDCG 只有长征题 1 题可评，池大小不足。
- **LLM judge provisional** 答案指标：`required_fact_recall=0.4085`（58/143）、`citation_support=0.7667`、`time_constraint=0.9583`、`scope_explanation=0.7500`、`answer_pass=0.3438`；过程 28 pass / 4 fail。`approved_answer_aggregate` 为空。
- 报告：`data/reports/golden32_v1.2_20261101/report_llm_judge.json`
- 复核记录：[REVIEWED.md](REVIEWED.md)；人工校准队列：[CALIBRATION_QUEUE.md](CALIBRATION_QUEUE.md)。

## 身份与注意

- `capture_sha256`：`2c0d48f3bb9e968a57a6ec06177a34b0ca045529019213d304b491bbf6168f3d`
- `source_sha256`：`ec05ca59dc895feaa9a977bf3c07c934ca8e1fd4e4173640b5e754ea989b5bf6`
- `corpus_sha256`：`a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d`
- 报告记录的 `git.commit=87c105f`，`dirty=true`：本次采集前刚更新了 `dev_refusal_einstein` 的 REQUIREMENTS.md 基准 SHA，工作区尚未提交；语料和源码指纹未变。
- 统一运行使用生产 LLM 管线；`dev_semantic_contradiction` 走了超长抽取式回答，建议作为单独缺陷排查，不影响检索/排序分母。
