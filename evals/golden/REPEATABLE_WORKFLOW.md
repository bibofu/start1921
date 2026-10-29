# Golden 20 题评测流程

当前数据集：[golden_dataset.json](golden_dataset.json)。它是单轮 PilotCase schema，15 开发 + 5 保留，18 可答 + 2 拒答。没有多臂执行协议；`dev_constraint_history_isolation` 在本数据集中只作为单轮问题。

## 1. 采集

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset evals/golden/golden_dataset.json `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --run-name golden20_local_20261029 `
  --output data/reports/golden20_local_20261029/capture.json
```

- 组件检索用原问题，不经过 LLM 规划。
- 需要真实模型时显式加 `--with-llm`，会外发题干和证据片段并产生费用。
- 输出目录不能已存在；失败保留 `.partial.json`。
- 采集记录数据集、源码、语料、索引身份和调用用量。

## 1.1 候选池与 LLM 预标

当前 `ranking_pools.json` 有 18 个池，覆盖全部可答题；候选标签为 95 条 `agent_review` + 68 条 `llm_judge` + 30 条人工处理。未抽检的 LLM 标签只是暂定，不能当人工批准。

复现/扩展命令：

```powershell
.\.venv\Scripts\python.exe -B scripts/build_candidate_pools.py --write
```

人工抽检清单见 [LLM_LABEL_REVIEW.md](LLM_LABEL_REVIEW.md)。抽检通过后，应把对应判断改为 `human_review` 并记录 reviewer/time；未抽检的 `llm_judge` 继续只作诊断。

## 2. 生成复核包

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot prepare-reviews `
  --dataset evals/golden/golden_dataset.json `
  --capture data/reports/golden20_local_20261029/capture.json `
  --output-dir data/reports/golden20_local_20261029/reviews
```

生成 `index.html`、答案/过程复核模板、校准包和导出包。所有判断初始为 `unknown`，不会自动打分或批准。

## 3. 导入复核

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot import-reviews `
  --dataset evals/golden/golden_dataset.json `
  --capture data/reports/golden20_local_20261029/capture.json `
  --bundle data/reports/golden20_local_20261029/review-bundle.json `
  --output-dir data/reports/golden20_local_20261029/reviewed
```

## 4. 评分

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/golden_dataset.json `
  --capture data/reports/golden20_local_20261029/capture.json `
  --ranking-pools evals/golden/ranking_pools.json `
  --reviews-dir data/reports/golden20_local_20261029/reviewed `
  --k-values 1 3 5 10 20 `
  --output data/reports/golden20_local_20261029/report.json
```

- 暂定分数允许 Agent 标签；正式分数只接受人工批准题目和人工标签/答案。
- 未标注候选是 unknown，不是 0 分；不可评指标保持 N/A。
- 当前只有 8 道题有候选标签/固定池，Precision/MRR/nDCG 只在 K≤5 稳定。

## 5. 比较

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot compare `
  data/reports/run_a/report.json data/reports/run_b/report.json `
  --output data/reports/run_b/comparison.json
```

比较器核对数据集、源码、语料、K 集合和索引身份。只有固定切分、embedding、候选池和索引时才可归因；当前 Qdrant 服务没有 artifact manifest，排序不能做单变量归因。

## 6. 规则

- 调参只用开发题；保留题不用于调参。
- 不修改题目/事实/证据后复用旧 capture；必须重新采集。
- 不把未标注候选当不相关。
- 不把“已批准题目定义”解释为“候选/答案已批准”。
- 逐题原文、事实和拒答边界见 [CASE_INVENTORY.md](CASE_INVENTORY.md)；答案复核口径见 [ANSWER_REVIEW_CALIBRATION.md](ANSWER_REVIEW_CALIBRATION.md)。
