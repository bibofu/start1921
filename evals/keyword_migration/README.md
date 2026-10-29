# 关键词存储迁移评测

当前协议是 `protocol_v2.json`，绑定 20 题 `evals/golden/golden_dataset.json` 和 8 题固定池 `evals/golden/ranking_pools.json`。它只验证关键词存储后端（SQLite → PostgreSQL）的检索兼容性，不改变 Agent，也不把合成标签当 Golden。

旧 `protocol_v1.json` 和 `results_v1.json` 保留为历史记录；其引用的 v3–v6 标注/协议已在 2026-10-29 清理，不能直接复现。旧本地大文件 `data/reports/keyword-migration-v1/` 已按评测清理计划删除。

## 当前可用的报告工具

`python -m history_agent.evaluation.keyword_migration` 提供 `compare`、`compare-e2e`、`score-e2e`，读取已有 JSON 结果，不打开旧索引或加载旧实现。示例：

```powershell
python -m history_agent.evaluation.keyword_migration compare-e2e `
  data/reports/keyword-e2e-a.json `
  data/reports/keyword-e2e-b.json `
  --output data/reports/keyword-e2e-review.json
```

输入路径以本地实际保留的 capture 为准。原 `capture`、`capture-e2e`、`capture-synthetic` 双后端执行命令已退休。

## 历史结果

2026-10-20 的迁移验证保留在 `results_v1.json`：完成部分的 278/278 组结果顺序与公开得分相同，20 题/21 次无 LLM 端到端执行 21/21 相同；剩余 183 组未完成，不声明整个计划通过。真实 Precision/MRR/nDCG 当时可评题数为 0，因为候选标签全部是 `agent_review`。该结果是历史快照，不能与当前 20 题成绩混用。

## 测试

PostgreSQL 合成语料测试使用 `HISTORY_AGENT_TEST_POSTGRES_URL`；未配置时明确跳过。JSON 比较和指标单元测试不需要数据库。
