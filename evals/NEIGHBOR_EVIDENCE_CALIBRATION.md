# 邻居证据扩展校准记录（2026-10-24）

本文件记录"把相邻 chunk 作为额外证据"的实验：先测它能否提升证据覆盖，再看端到端问答的影响。结论是**证据层收益成立，但端到端事实覆盖未被证明，默认关闭**（`HISTORY_AGENT_NEIGHBOR_EVIDENCE=false`）。第 8 节复核了分组摘要这个混淆变量并已消除。本文不是 Golden 成绩，也没有经过人工验收。

## 1. 动机

模型每条证据只能看到 420 字引文，而事件日期、地点常落在相邻 chunk 里。此前的日期校准发现：19 个日期中有 2 个"月份对、日不在所引 chunk"，旧规则 3 处误判也属于"引文覆盖不足"。因此先问：把相邻 chunk 补进证据包，能补回多少？

## 2. 实现方式

- 证据层扩展，不改检索排序：`SearchHit` 顺序、RRF、按页去重、Top-K 全部不变；
- 对每个已入选 hit，读取 `data/processed/chunks/{document_id}.jsonl` 中的 `previous_chunk_id` / `next_chunk_id`，按文档懒加载 + 3 篇 LRU 缓存（单篇约 15 MB RSS）；
- 相邻 chunk 作为**独立证据**注册（保留自己的页码、章节、年份），评分按 0.5 衰减，追加在原始 hit 之后；
- 上限 `HISTORY_AGENT_NEIGHBOR_EVIDENCE_LIMIT`（默认 4）；`HISTORY_AGENT_NEIGHBOR_EVIDENCE` 默认 `false`。

之所以不做成"合并文本"：合并会破坏页码归属，而引用必须能回到具体 PDF 页；也不做成检索候选：并列参与排序会改变 Top-K 语义，无法单变量归因。

## 3. 证据层收益（确定性测量）

语料：`evals/golden/development_v2.json` 的 13 道题、43 个必要证据组；检索结果取 2026-10-05 冻结采集的组件检索（top_k=20）。

| 指标 | 现状 | 加邻居 | 变化 |
| --- | ---: | ---: | ---: |
| 必要证据组可达数 | 23 / 43（53.5%） | 27 / 43（62.8%） | **+4（+9.3pp）** |

新增可达的组：

| 题目 | 新增页码 | 文獻 |
| --- | ---: | --- |
| `pilot_semantic_deng_1962_agriculture` | 385 | 邓小平年谱（下卷） |
| `pilot_negative_cppcc_1949` | 13 | 毛泽东年谱 第4卷 |
| `dev_constraint_month_place` | 477 | 毛泽东年谱 第3卷 |
| `dev_semantic_investigation` | 82 | 毛泽东选集 |

日期维度：13 道题的答案中有 12 个日期不在所引 chunk 内，其中 **3 个** 能在该 chunk 的相邻 chunk 中找到（遵义题 p484→p483、p123→p122）。其余 9 个属于 OCR 缺字、资料范围说明句或确实不在邻近片段。

## 4. 端到端对照（13 题，同模型，单次运行）

| 题目 | 证据数（关→开） | 引用数 | 字数 | 日期判定 |
| --- | --- | --- | --- | --- |
| `pilot_multievidence_zunyi_leadership` | 18 → 27 | 6 → 9 | 1093 → **1548** | 2 supported + 1 partial → **4 supported** |
| `dev_semantic_first_congress` | 12 → 16 | 3 → 4 | 1484 → **912** | 1 supported → 1 supported |
| `dev_semantic_investigation` | 12 → 16 | 10 → 12 | 1586 → **1174** | 1 supported → 2 supported |
| `pilot_exact_deng_1952_appointment` | 12 → 13 | 2 → 3 | 197 → 284 | 2 supported → 2 supported |
| 其余可答題 | 12 → 13~16 | 基本持平 | 有增有减 | 无新增矛盾 |

两点观察：

1. **目标题改善明显**：遵义题原本 1 个日期 `partial`，加邻居后 4 个日期全部 supported，答案也更长。这与第 3 节的确定性测量一致。
2. **单检索任务的答案普遍变短**：`first_congress` 1484→912、`investigation` 1586→1174（约 -30%）。这两题的证据数都从 12 变成 16，越过了合成器的 12 条分组阈值（`LLM_EVIDENCE_BATCH_SIZE`），因此触发了分组摘要。**推测**是分组摘要压缩了细节，但本次没有做事实级复核，不能据此断言事实覆盖下降。

另有一题（`pilot_constraint_deng_1973_march`）从 LLM 答案变成摘录兜底，核对发现是查询规划改走了 `read_source` 分支（`retrieval_calls` 0→1、tools 变化），与本功能无关，属于规划随机性。

## 5. 结论与决定

| 问题 | 结论 |
| --- | --- |
| 能提升证据覆盖吗？ | 能，页级必要证据组 +4/43（+9.3pp），日期补回 3/12 |
| 端到端变好吗？ | **未证明**。目标题明显变好，但两题答案变短；第 8 节复核表明变短来自分组摘要，不是邻居本身 |
| 有副作用吗？ | 原副作用（越过分组阈值）已在实现中消除：邻居证据单独计数，见第 8 节 |
| 默认开启吗？ | **否**。默认 `false`，代码与测试保留，可一键开启 |

不默认开启的理由：在无法证明事实覆盖不下降之前，只凭"覆盖更多"就改变线上答案构成，违背本项目"先测量后上线"的约定。这与 BC-043 的教训一致。

## 6. 下一步（按优先级）

1. **做一次固定计划的事实覆盖对照**：用同一组检索结果和同一计划，只切换邻居开关，跑 2×13 题，按 `development_v2` 的 43 条必要事实逐条复核。若事实覆盖不降，再考虑默认开启。
2. 分组混淆已在第 8 节排除；若事实覆盖对照通过，可直接把 `HISTORY_AGENT_NEIGHBOR_EVIDENCE` 默认值改为 `true`。

## 7. 复现

```powershell
# 证据层收益（离线，不调用模型）
.\.venv\Scripts\python.exe scripts\measure_neighbor_gain.py `
  --capture data\reports\eval_observation_20261005\live_capture.json `
  --annotations evals\golden\development_v2.json `
  --answers data\reports\citation_date_calibration\live_answers.json `
  --output data\reports\neighbor_gain

# 端到端对照（13 次真实问答；需要服务与密钥）
$env:HISTORY_AGENT_NEIGHBOR_EVIDENCE="true"
.\.venv\Scripts\python.exe scripts\capture_live_answers.py `
  --questions-from data\reports\eval_observation_20261005\live_capture.json `
  --output data\reports\neighbor_gain\live_answers_neighbors.json
```

## 8. 分组混淆变量的复核（选项 A）

上一节把"答案变短"归因于分组摘要，但未验证。做法：让邻居证据不参与分组阈值计数（只有主证据超过 12 条才分组），再跑同一批 13 题。三次运行对照：

| 指标 | 基线（无邻居） | 邻居 + 分组 | 邻居 + 不分组 |
| --- | ---: | ---: | ---: |
| 日期 supported | 17 | 22 | **34** |
| 日期 partial | 2 | 1 | 4 |
| 日期 unverifiable | 0 | 1 | 0 |
| 日期 contradicted | 0 | 0 | 0 |
| 一大题字数 | 1484 | 912 | **1534** |
| 周1954字数 | 1315 | 500 | **1016** |
| 周1954—1956字数 | 2171 | 1944 | **4554** |
| 邓1962字数 | 744 | 633 | **1323** |

结论：

1. **确认**：分组摘要确实是压缩来源——不分组后，一大的 912 字恢复到 1534 字，周 1954 从 500 字恢复到 1016 字。
2. 不分组时多年度题的答案显著变长（2171→4554 字），相关日期支持从 0 增加到 15，说明邻居确实补进了跨年份材料。
3. 三次运行都没有出现日期矛盾（`contradicted_*` = 0），也没有新增的核对提示。
4. 仍有 4 个 `partial`（月份对、日不在所引 chunk），以及部分题目比基线短（调查研究 1586→1234），因此**不能据此宣称事实覆盖提升**。

决定不变：默认仍为 `false`。A 只证明了"分组是混淆变量"，要改成默认开启仍需 §6 的事实覆盖对照。

## 9. 局限

- 单次运行，13 题；查询规划本身有随机性（已出现一题改走 `read_source`）。
- 没有做事实级人工复核，"答案变短"只是长度观察，不等于质量下降。
- 页级收益基于 2026-10-05 的组件检索结果，生产链路有覆盖策略与查询改写，实际收益可能不同。
- 相邻 chunk 读取依赖 `data/processed/chunks/*.jsonl` 的文件名等于 `document_id`；重建切片后需保持该约定。
