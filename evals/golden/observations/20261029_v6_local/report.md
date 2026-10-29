# 开发集评测报告

运行：`development20_v6_local_20261029`

暂定分数允许 Agent 复核标签，用于诊断；正式分数要求适用的人工作业批准。未知、未标注、不适用与缺采集均保持 N/A，不能按零分处理。

采集指纹：`1a31f74cc8ff6929c94c63b56c14961fbe0f134caf10680deb759761e4dfdb8f`  
题集指纹：`513b684429d8ba5bf069f9c0d4b3c94415224f2529e160992c2dacea05dfebee`  
代码指纹：`33efedce2bd57c76c764ccaf8e241259bce6ca37b3a20f129a7bbefc485e86f4`  
答案复核指纹：`N/A`  
答案校准口径：`未绑定（旧入口）`  
过程复核指纹：`N/A`  
协议文件指纹：`8aa9b7e9d09a985fb18799da78db57a79030460fb06405250bc26c4ee2f31e9a`

独立题数：20；实际执行：21（含配对控制臂）。
主质量聚合每题只纳入协议首个输入，淮海无历史控制臂单列；下面主路径成本表不含控制臂。
所有执行的 HTTP 调用数：0；总 Token：N/A。
本次未启用真实模型；答案/过程仍须复核，不能据此评估真实模型质量。
组件探针使用原问题，不接收对话历史；历史隔离需看两臂实际生产计划和轨迹。

## 组件检索：多 K 指标

各格为“宏平均（有效题数/该阶段题数）”。未知候选不当作不相关；固定池 nDCG 仅在候选池及相关性标注满足条件时计算。

| 口径 | 阶段 | K | 必要证据 Recall | Precision | MRR | 固定池 nDCG |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 暂定 | 任职过滤 | 1 | 0.289 (17/20) | 0.917 (12/20) | 0.917 (12/20) | 0.750 (12/20) |
| 暂定 | 任职过滤 | 3 | 0.409 (17/20) | 0.778 (12/20) | 0.917 (12/20) | 0.720 (12/20) |
| 暂定 | 任职过滤 | 5 | 0.482 (17/20) | 0.700 (12/20) | 0.917 (12/20) | 0.731 (12/20) |
| 暂定 | 任职过滤 | 10 | 0.617 (17/20) | 0.525 (4/20) | 0.917 (12/20) | 0.669 (4/20) |
| 暂定 | 任职过滤 | 20 | 0.648 (17/20) | N/A (0/20) | 1.000 (11/20) | N/A (0/20) |
| 暂定 | 大会覆盖补充 | 1 | 0.289 (17/20) | 0.917 (12/20) | 0.917 (12/20) | 0.750 (12/20) |
| 暂定 | 大会覆盖补充 | 3 | 0.409 (17/20) | 0.778 (12/20) | 0.917 (12/20) | 0.720 (12/20) |
| 暂定 | 大会覆盖补充 | 5 | 0.486 (17/20) | 0.700 (12/20) | 0.917 (12/20) | 0.731 (12/20) |
| 暂定 | 大会覆盖补充 | 10 | 0.597 (17/20) | 0.367 (3/20) | 0.917 (12/20) | 0.589 (3/20) |
| 暂定 | 大会覆盖补充 | 20 | 0.609 (17/20) | N/A (0/20) | 1.000 (11/20) | N/A (0/20) |
| 暂定 | 最终候选 | 1 | 0.289 (17/20) | 0.917 (12/20) | 0.917 (12/20) | 0.750 (12/20) |
| 暂定 | 最终候选 | 3 | 0.409 (17/20) | 0.778 (12/20) | 0.917 (12/20) | 0.720 (12/20) |
| 暂定 | 最终候选 | 5 | 0.486 (17/20) | 0.700 (12/20) | 0.917 (12/20) | 0.731 (12/20) |
| 暂定 | 最终候选 | 10 | 0.597 (17/20) | 0.367 (3/20) | 0.917 (12/20) | 0.589 (3/20) |
| 暂定 | 最终候选 | 20 | 0.609 (17/20) | N/A (0/20) | 1.000 (11/20) | N/A (0/20) |
| 暂定 | 关键词候选 | 1 | 0.279 (17/20) | 0.667 (12/20) | 0.667 (12/20) | 0.667 (12/20) |
| 暂定 | 关键词候选 | 3 | 0.451 (17/20) | 0.639 (12/20) | 0.750 (12/20) | 0.670 (12/20) |
| 暂定 | 关键词候选 | 5 | 0.523 (17/20) | 0.617 (12/20) | 0.750 (12/20) | 0.677 (12/20) |
| 暂定 | 关键词候选 | 10 | 0.612 (17/20) | N/A (0/20) | 0.818 (11/20) | N/A (0/20) |
| 暂定 | 关键词候选 | 20 | 0.649 (17/20) | N/A (0/20) | 0.818 (11/20) | N/A (0/20) |
| 暂定 | 页级去重 | 1 | 0.289 (17/20) | 0.917 (12/20) | 0.917 (12/20) | 0.750 (12/20) |
| 暂定 | 页级去重 | 3 | 0.409 (17/20) | 0.778 (12/20) | 0.917 (12/20) | 0.720 (12/20) |
| 暂定 | 页级去重 | 5 | 0.486 (17/20) | 0.700 (12/20) | 0.917 (12/20) | 0.731 (12/20) |
| 暂定 | 页级去重 | 10 | 0.597 (17/20) | 0.367 (3/20) | 0.917 (12/20) | 0.589 (3/20) |
| 暂定 | 页级去重 | 20 | 0.609 (17/20) | N/A (0/20) | 1.000 (11/20) | N/A (0/20) |
| 暂定 | 融合 | 1 | 0.289 (17/20) | 0.833 (12/20) | 0.833 (12/20) | 0.722 (12/20) |
| 暂定 | 融合 | 3 | 0.401 (17/20) | 0.750 (12/20) | 0.875 (12/20) | 0.709 (12/20) |
| 暂定 | 融合 | 5 | 0.413 (17/20) | 0.660 (10/20) | 0.875 (12/20) | 0.720 (10/20) |
| 暂定 | 融合 | 10 | 0.594 (17/20) | 0.533 (6/20) | 0.875 (12/20) | 0.705 (6/20) |
| 暂定 | 融合 | 20 | 0.663 (17/20) | N/A (0/20) | 0.955 (11/20) | N/A (0/20) |
| 暂定 | 规则排序 | 1 | 0.289 (17/20) | 0.917 (12/20) | 0.917 (12/20) | 0.750 (12/20) |
| 暂定 | 规则排序 | 3 | 0.409 (17/20) | 0.788 (11/20) | 0.917 (12/20) | 0.734 (11/20) |
| 暂定 | 规则排序 | 5 | 0.413 (17/20) | 0.680 (10/20) | 0.917 (12/20) | 0.729 (10/20) |
| 暂定 | 规则排序 | 10 | 0.607 (17/20) | 0.525 (4/20) | 0.917 (12/20) | 0.669 (4/20) |
| 暂定 | 规则排序 | 20 | 0.658 (17/20) | N/A (0/20) | 1.000 (11/20) | N/A (0/20) |
| 暂定 | 向量候选 | 1 | 0.093 (17/20) | 0.500 (12/20) | 0.500 (12/20) | 0.333 (12/20) |
| 暂定 | 向量候选 | 3 | 0.292 (17/20) | 0.611 (12/20) | 0.653 (12/20) | 0.489 (12/20) |
| 暂定 | 向量候选 | 5 | 0.306 (17/20) | 0.567 (12/20) | 0.674 (12/20) | 0.510 (12/20) |
| 暂定 | 向量候选 | 10 | 0.402 (17/20) | N/A (0/20) | 0.735 (11/20) | N/A (0/20) |
| 暂定 | 向量候选 | 20 | 0.441 (17/20) | N/A (0/20) | 0.735 (11/20) | N/A (0/20) |
| 正式 | 任职过滤 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 任职过滤 | 3 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 任职过滤 | 5 | 0.455 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 任职过滤 | 10 | 0.609 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 任职过滤 | 20 | 0.609 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 大会覆盖补充 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 大会覆盖补充 | 3 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 大会覆盖补充 | 5 | 0.455 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 大会覆盖补充 | 10 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 大会覆盖补充 | 20 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 最终候选 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 最终候选 | 3 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 最终候选 | 5 | 0.455 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 最终候选 | 10 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 最终候选 | 20 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 关键词候选 | 1 | 0.281 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 关键词候选 | 3 | 0.354 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 关键词候选 | 5 | 0.448 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 关键词候选 | 10 | 0.570 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 关键词候选 | 20 | 0.612 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 页级去重 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 页级去重 | 3 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 页级去重 | 5 | 0.455 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 页级去重 | 10 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 页级去重 | 20 | 0.567 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 融合 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 融合 | 3 | 0.417 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 融合 | 5 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 融合 | 10 | 0.528 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 融合 | 20 | 0.609 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 规则排序 | 1 | 0.260 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 规则排序 | 3 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 规则排序 | 5 | 0.435 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 规则排序 | 10 | 0.588 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 规则排序 | 20 | 0.629 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 向量候选 | 1 | 0.042 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 向量候选 | 3 | 0.237 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 向量候选 | 5 | 0.257 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 向量候选 | 10 | 0.320 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |
| 正式 | 向量候选 | 20 | 0.382 (8/20) | N/A (0/20) | N/A (0/20) | N/A (0/20) |

同一运行的多 K 是排序前缀诊断；不等于重新执行不同生产 Top-K。有效题 ID、未知候选、未标注/失效池原因见 JSON 的阶段诊断。

## 最终答案与查询理解

| 口径 | 维度 | 分数 | 通过数/有效分母 | 有效题数/目标题数 | N/A 原因 |
| --- | --- | ---: | ---: | ---: | --- |
| 暂定 | 必要事实覆盖 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 引用支持 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 来源约束 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 时间约束 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 路由选择 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 安全拒答 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 回答范围说明 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 整题通过 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 暂定 | 查询理解 | N/A | N/A/0 | 0/20 | 本次查询理解尚未复核（20题） |
| 正式 | 必要事实覆盖 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 引用支持 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 来源约束 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 时间约束 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 路由选择 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 安全拒答 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 回答范围说明 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 整题通过 | N/A | 0/0 | 0/20 | 本次答案尚未复核（20题） |
| 正式 | 查询理解 | N/A | N/A/0 | 0/20 | 本次查询理解尚未复核（20题） |

必要事实覆盖按事实数作分母，其余维度按适用且已复核的题数作分母。整题通过要求所有适用维度通过；有部分可用内容不等于整题通过。

## 生产过程：必要证据组覆盖

以下覆盖合并同题各轮/查询变体；并集不参与 Precision、MRR 或 nDCG。固定目标均值只在全部适用题可评时显示。

| 口径 | 阶段 | 有效子集宏平均 | 命中组/有效组分母 | 有效题/目标题 | 固定目标均值 | N/A 原因 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 暂定 | 时间线过滤后候选 | 62.1% | 30/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 任职过滤 | 73.5% | 46/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 大会覆盖补充 | 69.4% | 40/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 最终候选 | 62.1% | 30/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 关键词候选 | 70.0% | 36/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 末次生成上下文 | N/A | N/A/N/A | 0/17 | N/A | 未执行生成请求（17题） |
| 暂定 | 各次生成已映射原文并集 | N/A | N/A/N/A | 0/17 | N/A | 无成功且可映射的原文上下文（17题） |
| 暂定 | 页级去重 | 69.4% | 40/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 单查询最终候选 | 67.4% | 24/50 | 11/17 | N/A | 阶段未采集或未执行（6题） |
| 暂定 | 各轮各分支召回并集 | 76.7% | 49/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 融合 | 76.7% | 49/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 规则排序 | 76.7% | 49/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 暂定 | 改写查询任职过滤 | 67.4% | 24/50 | 11/17 | N/A | 阶段未采集或未执行（6题） |
| 暂定 | 改写查询页级去重 | 67.4% | 24/50 | 11/17 | N/A | 阶段未采集或未执行（6题） |
| 暂定 | 改写查询融合 | 67.4% | 24/50 | 11/17 | N/A | 阶段未采集或未执行（6题） |
| 暂定 | 向量候选 | 57.4% | 39/78 | 16/17 | N/A | 阶段未采集或未执行（1题） |
| 正式 | 时间线过滤后候选 | 59.1% | 17/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 任职过滤 | 71.3% | 21/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 大会覆盖补充 | 67.1% | 20/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 最终候选 | 59.1% | 17/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 关键词候选 | 67.4% | 20/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 末次生成上下文 | N/A | N/A/N/A | 0/17 | N/A | 整题尚未人工批准（9题）；未执行生成请求（8题） |
| 正式 | 各次生成已映射原文并集 | N/A | N/A/N/A | 0/17 | N/A | 整题尚未人工批准（9题）；无成功且可映射的原文上下文（8题） |
| 正式 | 页级去重 | 67.1% | 20/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 单查询最终候选 | 53.4% | 12/26 | 6/17 | N/A | 整题尚未人工批准（9题）；阶段未采集或未执行（2题） |
| 正式 | 各轮各分支召回并集 | 77.5% | 24/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 融合 | 77.5% | 24/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 规则排序 | 77.5% | 24/33 | 8/17 | N/A | 整题尚未人工批准（9题） |
| 正式 | 改写查询任职过滤 | 53.4% | 12/26 | 6/17 | N/A | 整题尚未人工批准（9题）；阶段未采集或未执行（2题） |
| 正式 | 改写查询页级去重 | 53.4% | 12/26 | 6/17 | N/A | 整题尚未人工批准（9题）；阶段未采集或未执行（2题） |
| 正式 | 改写查询融合 | 53.4% | 12/26 | 6/17 | N/A | 整题尚未人工批准（9题）；阶段未采集或未执行（2题） |
| 正式 | 向量候选 | 59.1% | 18/33 | 8/17 | N/A | 整题尚未人工批准（9题） |

原文并集包含成功请求中可映射的分组生成和修复输入；末次请求若使用摘要，不能反推成原文上下文。缺轨迹保持 N/A。原文裁剪会改变证据身份，覆盖下降也可能来自新片段尚未补标。

## 请求、Token 与耗时

HTTP 请求总数：0；已记录 0 次，成功 0、失败 0、状态未知 0。重试逐次计入。

| 请求阶段 | 已记录调用数 | 完整 usage 调用 | 输入 Token | 输出 Token | 总 Token | 已知总 Token | 缺 usage 调用数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 全部 | 0 | 0 | N/A | N/A | N/A | N/A | 0 |

usage 缺失时完整总量为 N/A，已知量仅是可观测子集；未调用 LLM 不填虚构 Token。累计请求耗时可能包含并发重叠，不能当作回答墙钟耗时。

| 实测路径 | 有效题/总题 | 均值 ms | 中位数 ms | 最大值 ms | 完整累计 ms | N/A 原因 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 组件检索墙钟 | 20/20 | 322.318 | 356.505 | 598.070 | 6446.362 | — |
| 完整回答墙钟 | 20/20 | 553.430 | 531.100 | 1123.888 | 11068.597 | — |

每题仅一次实测，组件检索和完整回答是分别计时的路径。

## 逐题结果

事实状态按“覆盖 / 部分 / 缺失 / 矛盾 / 未裁定”排列；以下按暂定口径展示，正式有效分母见前表及 JSON。

| 题目 ID | 事实状态 | 事实覆盖 | 整题通过 | 查询理解 | 召回并集 | 原文输入并集 | 末次上下文 | HTTP 次数 | 总 Token | 回答 ms |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pilot_exact_deng_1952_appointment | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 455.835 |
| pilot_semantic_deng_1962_agriculture | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 66.7% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 300.641 |
| pilot_multievidence_zunyi_leadership | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 496.138 |
| pilot_negative_cppcc_1949 | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 694.944 |
| pilot_constraint_deng_1973_march | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 746.228 |
| pilot_refusal_out_of_scope_2024 | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | 0 | N/A | 88.556 |
| dev_exact_zhou_1954 | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 507.385 |
| dev_exact_deng_1954 | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 572.369 |
| dev_constraint_month_place | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 75.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 1123.888 |
| dev_multi_zhou_periods | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 28.6% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 831.024 |
| dev_semantic_investigation | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 900.488 |
| dev_semantic_contradiction | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 880.409 |
| dev_semantic_first_congress | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 40.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 286.811 |
| dev_exact_zunyi_election | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 100.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 500.920 |
| dev_multi_meetings | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 53.3% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 404.506 |
| dev_constraint_history_isolation | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | N/A（阶段未采集或未执行） | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 4.015 |
| dev_multi_mao_hunan | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 42.9% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 845.617 |
| dev_intersection_mao_zhou_1949 | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | 20.0% | N/A（无成功且可映射的原文上下文） | N/A（未执行生成请求） | 0 | N/A | 650.131 |
| dev_refusal_einstein | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | 0 | N/A | 223.877 |
| dev_refusal_source_year | N/A（未完成适用复核） | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A（本次查询理解尚未复核） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | N/A（无适用必要证据组） | 0 | N/A | 554.815 |

题目与过程复核说明：

- `pilot_exact_deng_1952_appointment`：1952年8月7日，邓小平被任命为什么职务？
- `pilot_semantic_deng_1962_agriculture`：1962年7月，邓小平怎样判断哪种农业生产组织形式更合适？
- `pilot_multievidence_zunyi_leadership`：遵义会议、会后2月5日的常委分工和3月成立新“三人团”，分别怎样调整了中央军事领导？
- `pilot_negative_cppcc_1949`：毛泽东和周恩来在1949年10月9日是否共同当选为全国政协主席？请区分二人的职务。
- `pilot_constraint_deng_1973_march`：只依据《邓小平年谱（1904—1974）》下卷，1973年3月关于恢复邓小平职务和安排工作的决定分别是什么？
- `pilot_refusal_out_of_scope_2024`：习近平在2024年考察了哪些地方？
- `dev_exact_zhou_1954`：周恩来在1954年担任哪些主要职务？
- `dev_exact_deng_1954`：1954年9月，邓小平在国务院和国防委员会分别担任什么职务？
- `dev_constraint_month_place`：1949年3月毛泽东在北平有哪些活动？
- `dev_multi_zhou_periods`：按时间和主题梳理周恩来从1954年至1956年的主要经历，并说明这三年工作重点的变化。
- `dev_semantic_investigation`：毛泽东关于调查研究有哪些观点？
- `dev_semantic_contradiction`：毛泽东在《矛盾论》中怎样分析主要矛盾？
- `dev_semantic_first_congress`：党的头一次全国大会讲了些什么、形成了哪些决定？
- `dev_exact_zunyi_election`：遵义会议选举毛泽东担任什么党内职务？
- `dev_multi_meetings`：比较遵义会议和1959年庐山会议各自讨论的核心问题、会议进程和后续影响。
- `dev_constraint_history_isolation`：详细介绍淮海战役。
- `dev_multi_mao_hunan`：逐年梳理毛泽东1921—1926年在湖南的活动。
- `dev_intersection_mao_zhou_1949`：毛泽东与周恩来在1949年有哪些有直接原文支持的交集？
- `dev_refusal_einstein`：爱因斯坦在1925年担任了什么党内职务？
- `dev_refusal_source_year`：只依据《邓小平年谱（1904—1974）》，列出邓小平1975年的全部活动。

## 专项协议复核

以下为协议声明的检查项分母，与主报告按题打分分别展示，不增加独立题数。

| 题目 / 输入 | 检查维度 | 暂定 | 分母 | 正式 |
| --- | --- | --- | ---: | --- |
| dev_exact_zunyi_election / single_turn | dimensions.query_understanding | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_exact_zunyi_election / single_turn | dimensions.routing | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_exact_zunyi_election / single_turn | dimensions.refusal | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_multi_meetings / single_turn | dimensions.query_understanding | N/A（unknown_specialist_checks） | 3 | N/A（human_case_and_specialist_review_required） |
| dev_multi_meetings / single_turn | dimensions.routing | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_multi_meetings / single_turn | dimensions.refusal | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / with_history | dimensions.query_understanding | N/A（unknown_specialist_checks） | 4 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / with_history | dimensions.routing | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / with_history | dimensions.refusal | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_multi_mao_hunan / single_turn | stage_criteria.query_understanding | N/A（unknown_specialist_checks） | 4 | N/A（human_case_and_specialist_review_required） |
| dev_multi_mao_hunan / single_turn | stage_criteria.routing | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_intersection_mao_zhou_1949 / single_turn | stages.understanding_and_routing | N/A（unknown_specialist_checks） | 6 | N/A（human_case_and_specialist_review_required） |
| dev_intersection_mao_zhou_1949 / single_turn | stages.understanding_and_routing.routing_validity | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_intersection_mao_zhou_1949 / single_turn | stages.context_selection | N/A（生成上下文未采集） | 4 | N/A（human_case_and_specialist_review_required） |
| dev_intersection_mao_zhou_1949 / single_turn | stages.final_answer.scope_explanation | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_intersection_mao_zhou_1949 / single_turn | stages.final_answer.false_refusal | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.understanding_and_routing | N/A（unknown_specialist_checks） | 6 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.understanding_and_routing.routing_validity | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.context_selection | N/A（生成上下文未采集） | 3 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.final_answer.safe_refusal | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.final_answer.scope_explanation | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_einstein / single_turn | stages.final_answer.source_constraint | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.understanding_and_routing | N/A（unknown_specialist_checks） | 6 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.understanding_and_routing.routing_validity | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.context_selection | N/A（生成上下文未采集） | 3 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.final_answer.safe_refusal | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.final_answer.scope_explanation | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_refusal_source_year / single_turn | stages.final_answer.source_constraint | N/A（unknown_specialist_checks） | 1 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / without_history_control | dimensions.query_understanding | N/A（unknown_specialist_checks） | 4 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / without_history_control | dimensions.routing | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |
| dev_constraint_history_isolation / without_history_control | dimensions.refusal | N/A（unknown_specialist_checks） | 2 | N/A（human_case_and_specialist_review_required） |

### 淮海历史隔离配对

四项隔离检查：N/A（paired_plan_or_production_trace_unavailable）；必须同时复核两臂计划与过滤条件，质量差值本身不能证明历史泄漏。

| 维度 | 带历史 | 无历史控制 | 差值（带历史−控制） |
| --- | --- | --- | --- |
| 必要事实覆盖 | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A |
| 引用支持 | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A |
| 整题通过 | N/A（本次答案尚未复核） | N/A（本次答案尚未复核） | N/A |
| 各轮各分支召回并集 | N/A（阶段未采集或未执行） | 75.0% | N/A |
| 各次生成已映射原文并集 | N/A（无成功且可映射的原文上下文） | N/A（无成功且可映射的原文上下文） | N/A |
| 末次生成上下文 | N/A（未执行生成请求） | N/A（未执行生成请求） | N/A |

### 湖南活动：固定六年分层

完整年份：N/A（incomplete_fixed_year_review）；六年事实 Recall 宏平均：N/A（incomplete_fixed_year_review）。年份分母为6，必要事实分母为14，两者独立。

| 年份 | 必要事实数 | 该年事实 Recall |
| --- | ---: | --- |
| 1921 | 2 | N/A（本次答案尚未复核） |
| 1922 | 2 | N/A（本次答案尚未复核） |
| 1923 | 2 | N/A（本次答案尚未复核） |
| 1924 | 1 | N/A（本次答案尚未复核） |
| 1925 | 5 | N/A（本次答案尚未复核） |
| 1926 | 2 | N/A（本次答案尚未复核） |

| 组件最终候选 K | 命中年份/6 | 六年证据 Recall 宏平均 |
| ---: | --- | --- |
| 1 | 0/6 | 0.0% |
| 3 | 1/6 | 16.7% |
| 5 | 1/6 | 16.7% |
| 10 | 2/6 | 25.0% |
| 20 | 2/6 | 25.0% |

逐年各阶段/生成上下文覆盖及正式门槛结果见 JSON。

完整逐题分母、有效/不可评题 ID、逐调用 usage、候选身份、N/A 原因及索引/模型/参数版本见同名 JSON；紧凑 JSON 保留汇总与逐题结果。
