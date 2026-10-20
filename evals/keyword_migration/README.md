# 关键词存储迁移评测

本次比较冻结于 `protocol_v1.json`，基线为提交 `55c9e02` 的原始实现及只读 SQLite 备份。
未修改 Agent 以适应评测，也未修改 Golden 标注。文件身份口径见 `oracle_identity_v1.json`：
原文件与 SQLite backup 文件的字节 SHA 不同，但 metadata、FTS 内容、10,438,350 条词位及 docsize 的全量排序摘要相同。
旧 manifest 使用“文件名 + NUL + 文件内容”的摘要算法，其摘要与原始文件 SHA 不同并不表示失效。

结果见 [results_v1.json](results_v1.json)。

- 用户要求停止进一步充分验证后，立即结束剩余候选采集并保留 checkpoint。
- 原始检索基线完成计划中的 **461 组**；候选完成 **278 组、2,224 次检索**。完成部分的完整结果顺序、公开得分、所有 hit 字段摘要、解析信息和各 K 结果 **278/278 相同**。剩余 **183 组未完成，不声明整个计划通过**。
- 无 LLM 的端到端比较完成 **20 题、21 次执行，21/21 相同**：路由、关键词与向量候选、融合、重排、上下文候选、生产调用轨迹、最终抽取式回答、引用和拒答行为。实际模型 prompt context、模型答案语义质量均不可评。
- 真实历史评测仅 **8 题**拥有已批准的题目与证据定义。证据组分母依次为 `3、4、2、6、4、7、4、3`，宏平均分母为 **8**。生产最终候选的关键证据 Recall@10 前后均为 **0.6086309524**；各阶段指标完整相同。196 条候选标签仍属于 `agent_review`，真实 Precision、MRR、nDCG 的可评题数为 **0**，结果保留 `null`。
- 独立人工构造语料含 **7 条记录、10 个查询、5 个 K**，完整相关性标签与历史 Golden 分开。实际 **50/50** 对比相同；区间查询@3 的 Recall=`1/1`、Precision=`1/3`、MRR=`1/2`。MRR 的倒数分母由 `first_relevant_rank` 给出，字段 `denominator=1` 表示单题统计口径。
- 4 题配对延迟观测中 PostgreSQL 中位耗时约为 SQLite 的 **3 倍**。采集存在并发负载与缓存影响，不能作为严谨性能基准，也不宣称提速。

10 个 holdout 未执行或用于调参，当前不宣称已完成 30 个高质量 Golden。既有拒答标注中的部分项目文档摘要已随项目更新变化，不据此计算新答案或拒答正确性。

完整本地产物保留在 `data/reports/keyword-migration-v1/`：
`baseline-keyword.json`、`final-candidate-keyword.checkpoint.jsonl`、
`partial-keyword-comparison.json`、`final-e2e-comparison.json`、
两个 `stage-metrics.json` 和 `final-synthetic/`。这些大文件不进入版本库。

独立执行器为 `python -m history_agent.evaluation.keyword_migration`，提供 `capture`、
`capture-e2e`、`compare`、`compare-e2e`、`score-e2e` 和 `capture-synthetic`。
所有新运行必须使用新输出路径；候选连接来自 `HISTORY_AGENT_KEYWORD_DATABASE_URL`，
合成比较仅使用显式的 `HISTORY_AGENT_TEST_POSTGRES_URL` 并创建、清理随机隔离 schema。
本次已经按用户要求停止，不继续运行剩余评测。

已完成验证：7 项评测测试通过（含真实 PostgreSQL 差分），新增阶段后处理的 21 份结果完全相等，
并通过独立只读指标复核。项目检查先前通过 975 项 Python 测试、3 项前端测试及 Ruff/mypy；
评测后处理新增后仅补跑相关检查，没有再扩大测试范围。
