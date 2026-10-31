# v6 开发集真实模型基线（2026-10-29）

这是 v6 标注/协议发布后的第一次真实模型运行：20 道开发题、21 个输入（含淮海无历史控制臂），使用当前 PostgreSQL 关键词索引、Qdrant 服务向量索引和生产 Plan-and-Execute 流程。**本次只采集和评分，不修改 Agent，也没有完成人工答案复核。**

## 身份

| 项目 | 值 |
|---|---|
| 题集 | v6 开发集（历史观察；标注/协议文件已清理） |
| 题集指纹 | `513b684429d8ba5bf069f9c0d4b3c94415224f2529e160992c2dacea05dfebee` |
| 协议文件 SHA-256 | `8aa9b7e9d09a985fb18799da78db57a79030460fb06405250bc26c4ee2f31e9a` |
| 采集指纹 | `756b808c66bad84e621bd3da6ba2016a9bbd3049a27b6ee065430bf4d231b843` |
| 源码指纹 | `33efedce2bd57c76c764ccaf8e241259bce6ca37b3a20f129a7bbefc485e86f4` |
| 语料指纹 | `a9225af6a1996d1721f34963cea1bdfcd5409a4a2edef73f8fbfed347dee430d` |
| 采集时 git | `d040925`，`dirty=true`（评测数据/文档在同一提交前修改） |
| 模型 | 规划/反思 `deepseek-v4-flash`，生成 `deepseek-v4-pro`，提示词 `grounded-answer-v15` |
| 配置 | `candidate_k=30`、`top_k=20`、`answer_top_k=10`、`with_llm=true` |

完整 capture、评分报告和复核工作台曾保存在本地忽略目录；原始文件已随 2026-10-31 清理删除，路径与哈希保留在 [manifest.json](manifest.json)。下表来自 [report.md](report.md)。

## 调用与结果

| 指标 | 结果 |
|---|---:|
| 独立题 / 执行输入 | 20 / 21 |
| HTTP 调用（全部执行） | **55**，全部 200，失败 0，usage 完整 |
| Token（全部执行） | **178,551**（输入 164,080，输出 9,987；主路径 53 次调用、174,067） |
| 回答模式 | LLM 16、摘录 4 |
| `evidence_status` | `partial` 16、`supported` 1、`no_evidence` 3 |
| 停止原因 | `completed` 13、`insufficient_evidence` 4、`out_of_scope` 3 |
| 组件检索耗时 | 均值 309ms、中位 339ms、最大 536ms |
| 回答耗时 | 均值 19.2s、中位 12.8s、最大 **70.8s** |
| 检索降级 | 无 |

55 次调用中包含淮海控制臂；主路径 20 题的成本按 53 次调用统计。没有 HTTP 失败或 usage 缺失。

## 检索指标

真实运行使用的组件探针是原问题；组件检索指标与已清理的 v6 本地基线相同。以下数字仅作历史对照：

| 口径 | K | 必要证据 Recall | Precision | MRR | 固定池 nDCG |
|---|---:|---:|---:|---:|---:|
| 暂定（Agent 标签） | 5 | 0.486（17/20） | 0.700（12/20） | 0.917（12/20） | 0.731（12/20） |
| 暂定 | 10 | 0.597（17/20） | 0.367（3/20） | 0.917（12/20） | 0.589（3/20） |
| 暂定 | 20 | 0.609（17/20） | N/A（0/20） | 1.000（11/20） | N/A（0/20） |
| 正式（8 题批准，仅锚点） | 20 | 0.567（8/20） | N/A | N/A | N/A |

真实模型运行的生产过程证据覆盖与本地基线不同：最终候选并集为 64.7%（33/81，15/17 可评），因为生产路径经过规划、补检和时间线过滤，且部分题没有可映射的完整轨迹。该数字不能替代组件 Top-20 指标。

## 本次发现的 Agent 行为问题（未修复）

1. **《矛盾论》观点题被当作全文交付。** 题目是“毛泽东在《矛盾论》中怎样分析主要矛盾？”，规划器选择 `read_source`（`source_title=矛盾论`），工作流按单任务全文直出，最终返回整篇《矛盾论》标题和正文，**没有生成针对“怎样分析主要矛盾”的回答**。这是本次唯一一次 `full_text` 交付，也是唯一一次 `generator_mode=extractive` 的可答题。该题属于已批准定义，但本次没有人工答案复核；在复核前不把它计为已确认失败。
2. **四道复杂题以 `insufficient_evidence` 结束。** `dev_multi_zhou_periods`（9 次调用、19 条引用、70.8s）、`dev_multi_mao_hunan`（7 次、22 条、52.1s）、`dev_multi_meetings`（6 次、8 条、48.5s）、`dev_intersection_mao_zhou_1949`（5 次、18 条、43.7s）。前两道和交集题的答案仍有较多引用，不能据停止原因直接判定答案质量；比较题的答案明确说明无法系统比较，提示遵义会议侧证据不足。
3. **拒答题在规划层直接拦截。** 三道拒答题（2024 考察、爱因斯坦 1925 任职、1904—1974 年谱问 1975 全部活动）均为 `out_of_scope`，各 1 次规划调用、0 次检索，行为符合预期；范围说明是否足够仍需答案复核。
4. **长回答接近预算。** 70.8s 的题已接近 90s 请求预算，但本次没有 `budget_exhausted`。复杂题的规划/补检/分组综合成本需要和答案质量一起评估。

## 限制

- **答案未复核**：引用支持、必要事实、来源/时间约束、路由、拒答和范围说明全部为 N/A；不能把本次运行称为 20 题通过率。
- **候选标签仍是 Agent 暂定**：12 道题有标签，5 道新可答题没有，3 道拒答无检索分母；正式 Precision/MRR/nDCG 可评题数为 0。
- **排序归因不安全**：Qdrant 服务集合没有独立可验证的 artifact manifest；`index_attribution.attribution_safe=false`。
- **12 题题目定义待审**，10 道保留题仍无事实/证据标注。

## 复核工作台

本地复核工作台曾位于 `data/reports/eval_development20_v6_live_20261029/reviews/index.html`，已随 2026-10-31 清理删除。本次没有完成人工答案复核，结论保持不变。

## 复现（历史命令，v6 文件已清理）

> 以下命令是历史记录，对应 v6 标注/协议已不在仓库，不能直接复现；当前 20 题流程见 [REPEATABLE_WORKFLOW.md](../../REPEATABLE_WORKFLOW.md)。

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset <cleaned v6 annotations> `
  --protocols <cleaned v6 protocols> `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --with-llm `
  --run-name development20_v6_live_20261029 `
  --output data/reports/eval_development20_v6_live_20261029/capture.json

.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot prepare-reviews `
  --dataset <cleaned v6 annotations> `
  --protocols <cleaned v6 protocols> `
  --capture data/reports/eval_development20_v6_live_20261029/capture.json `
  --output-dir data/reports/eval_development20_v6_live_20261029/reviews

.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset <cleaned v6 annotations> `
  --protocols <cleaned v6 protocols> `
  --capture data/reports/eval_development20_v6_live_20261029/capture.json `
  --ranking-pools <v6-era ranking pools> `
  --k-values 1 3 5 10 20 `
  --output data/reports/eval_development20_v6_live_20261029/report.json
```
