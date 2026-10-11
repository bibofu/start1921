# 开发集可重复评测流程

本流程使用 `history_agent.evaluation.pilot`（`reviewable-pilot-v3`），仅涉及评测工具。当前可执行入口仍为 13 题 schema v1；20 题 `development_annotations_v3.json` 的多轮协议接入属于后续工作，不得改低 schema 后直接运行。所有默认标签和已有答案评审仍为 Agent 暂定判断，正式 Golden 成绩需独立满足人工批准门槛。

## 1. 冻结输入并采集

每次实验选择新的目录，保存所用数据集、候选相关性标注、固定排序池和适用协议。固定题目、标注口径、模型及非实验参数；开发集用于调参，保留题用于独立验收。新候选没有标签时，Precision/MRR/nDCG 可能不可评，不得直接判为不相关。

```powershell
# 示例：新的本地检索采集，不调用模型。已有输出或 partial 输出会拒绝覆盖。
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset evals/golden/observations/20261005/dataset.json `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --run-name control_a --output data/reports/control_a/capture.json
```

需要真实问答时显式加 `--with-llm`，会发送问题、史料与中间答案并产生服务用量。上述命令不带该参数，答案及生成过程可能 N/A。不要把本地检索结果当成真实问答结果。

`capture.json` 记录应用源码指纹、Git 状态、PDF 文件身份、索引 manifest 与实际 artifact 校验、模型/提示词/参数、各层候选、实际 HTTP 请求及用量。保留 capture 原件；评分不重新读取当前索引，不会重新调用 Agent。采集失败时 `.partial.json` 保留已完成题目，但不是完整集报告，须使用新目录重新采集。

## 2. 为本次 capture 生成复核包

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot prepare-reviews `
  --dataset evals/golden/observations/20261005/dataset.json `
  --capture data/reports/control_a/capture.json `
  --protocols evals/golden/development_protocols_v3.json `
  --output-dir data/reports/control_a/reviews
```

生成 `review_packet.json`（题目、证据、必要事实、本次答案及轨迹入口）、`answer_reviews.json`、`process_reviews.json` 和操作说明。复核目录必须不存在，以免覆盖正在进行的审查。

- 答案复核：逐事实覆盖和引用支持、来源/时间约束、路由、拒答、范围说明。引用中有事实而正文未回答，不能算正文完整覆盖。
- 过程复核：依协议检查实际执行计划与查询变体是否保留实体、意图和约束；原始 Planner 输出和实际执行计划分别留证。`--protocols` 可省略，使用明确的通用判据；若指定，协议字节哈希和逐题定义必须匹配。
- 所有模板初始 `unknown`，不自动打分或批准。明确判断须填写依据、复核人、带时区时间和理由。可先评分未审模板，结果按实际缺口显示 N/A。
- 复核绑定整份 capture、题目定义，以及答案/引用或执行计划快照。换一次 capture 就必须生成并审阅新包，不能修改哈希来复用旧判断。

## 3. 离线生成统一报告

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/observations/20261005/dataset.json `
  --capture data/reports/control_a/capture.json `
  --ranking-pools evals/golden/ranking_pools_v2.json `
  --assessments data/reports/control_a/reviews/answer_reviews.json `
  --process-reviews data/reports/control_a/reviews/process_reviews.json `
  --protocols evals/golden/development_protocols_v3.json `
  --k-values 1 3 5 10 20 `
  --output data/reports/control_a/report.json
```

每次自动输出三份文件：

| 文件 | 用途 |
| --- | --- |
| `report.json` | 完整逐题、逐阶段、逐 K 指标及诊断，供比较器使用 |
| `report.summary.json` | 保留身份、聚合、过程、成本、逐题结论；省略大量重复候选诊断 |
| `report.md` | 便于查看的多 K 检索、答案、过程、成本与缺失原因摘要 |

暂定与人工批准结果分别保存。未提供答案/过程复核时，相应维度为 N/A。未映射的摘要上下文、缺失生产检索轨迹、缺失 usage 均不计零；成本同时报告完整总量和已知子集。HTTP 统计包含重试和失败；请求耗时之和可能有并发，不能冒充逐题 wall-clock 延时。

生产路径的多变体、多轮候选并集只计算关键证据覆盖，不能拼成 Precision/MRR/nDCG 排名。严格锚点和 span 身份会受到裁剪影响，因此阶段 Recall 下降不一定全部是语义丢失。最后一次摘要综合若不能还原原页，保持 N/A，同时报告可评子集及分母。

## 4. 用同版本评分器比较实验

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot compare `
  data/reports/control_a/report.json data/reports/control_b/report.json `
  --output data/reports/control_b/comparison.json
```

使用完整 `report.json`；摘要文件缺少完整阶段身份，不能作为归因材料。版本不同的旧报告，应先用同一评分器、同口径标签和各自绑定的复核重新离线评分，然后比较。

比较器区分三件事：

1. `compatible`：评分器版本、数据集、语料、K 集合和题目集合是否一致。
2. `metrics` / `answer_metrics`：组件检索和答案指标的有效题目、事实分母、复核依据、nDCG 固定池是否一致，可比时才给 delta。查询理解、生产并集和成本在统一报告中按各自分母查看，当前比较器没有自动生成这些维度的 delta。
3. `attribution_safe`：除了配置只改变组件 `top_k`（或重复对照），还要求源码相同、逐题活跃分支相同、有序候选相同、实际使用的索引身份完整且跨运行一致。逐项核对 embedding、切分参数及版本、chunk/index artifact、build ID 和构建 commit。双方都说“校验成功”并不能证明双方使用同一份索引。

索引身份缺失或变化时，仍可展示同口径指标差值，但归因为不安全；原因和差异见 `index_identity_comparison`。未参与的降级分支不冒充本次配置。当前支持的归因范围为 **component_retrieval**：组件 `top_k` 不控制实际生产问答的候选预算，不能据此解释答案波动。现有 `source_sha256` 也包含评测代码，评测代码变化会保守地阻止源码一致性归因。

## 已有 13 题的离线复现

本地大 capture 位于 ignored `data/reports/eval_observation_20261005/live_capture.json`；远程仓库只保存紧凑观察记录。缺少该文件时不能靠紧凑答案记录重建全部调用和上下文，不得伪造 capture。

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/observations/20261005/dataset.json `
  --capture data/reports/eval_observation_20261005/live_capture.json `
  --ranking-pools evals/golden/ranking_pools_v2.json `
  --assessments evals/golden/observations/20261005/answer_reviews.json `
  --process-reviews evals/golden/observations/20261005/process_reviews.json `
  --protocols evals/golden/development_protocols_v3.json `
  --output data/reports/eval_workflow_20261011/report.json
```

重算应保持：整题 3/13、事实 20/43、查询理解 11/13、生产召回并集 35/36（11题子集）、原文输入并集 22/43、最后上下文 14/30（9题子集；3题不可映射），44 次请求、115393 Token。此操作只重算已有观察，不代表新增一轮模型运行或人工批准。
