# start1921 后续路线图（2026Q4）

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v1.0 |
| 编写日期 | 2026-10-24 |
| 定位 | 未来 3—4 个月的能力建设规划，不是验收报告 |
| 前提假设 | 单人开发；单机 Docker 部署（app 1 CPU / 1 GiB）；不做账号体系；现有 17 份启用文献、22,338 个 chunk |
| 关联文档 | [企业级差距评估](ENTERPRISE-GAP.md)、[RAG 实现说明](../RAG-IMPL.md)、[Golden 评测](../evals/golden/README.md)、[问答问题记录](../badCase.md) |

> 本文与 [ENTERPRISE-GAP.md](ENTERPRISE-GAP.md) 的分工：后者回答“离企业级还差什么”，本文回答“接下来按什么顺序做、每步做到什么程度算完成”。两者冲突时以本文的排期为准，企业级门槛不降低。

> **2026-11-01 进度更新**：本文是 2026-10-24 的规划快照。此后已完成：Golden v1.2 冻结（32 题、32/32 题目批准、28 个固定池、301 条候选标签人工复核）；统一 32 题真实 LLM 基线（检索/排序指标已出，答案指标为 LLM judge provisional，待 C01–C12 人工校准）；CI 门禁已落地（`.github/workflows/eval-gate.yml`，PR 执行 pytest、打包检查、ruff、mypy 与前端测试）；生产引用存在性检查已恢复。仍未完成：连接池、指标/追踪/告警、备份演练、mini-golden 发布门禁阈值、Golden 答案的正式人工批准。下文“现状”与第 1—2 章的缺口数字按 2026-10-24 口径阅读。

---

## 0. 结论先行

你的四段式判断（评测 → 观测 → 记忆 → RAG）方向是对的：没有可复现的度量，记忆和检索调优都会退化成“凭感觉改 prompt”。但按当前仓库状态，建议做四处修正：

1. **评测的瓶颈不是“体系”，是“供给与门禁”。**
   六层指标、`metric_status`、可归因比较器、离线复核工作台都已存在；缺的是 30 题冻结、候选相关性标注、重构后的真实基线、CI 门禁和评审吞吐。继续加指标代码的边际收益很低。第一阶段应叫“评测运营”，不是“评测体系”。

2. **观测不要等评测全部收尾。**
   第 1 周先把 `trace_id` 打通（HTTP → workflow → 日志 → 会话元数据），Langfuse 在真实基线出来后接。否则基线跑出来的坏例仍然只能靠猜。

3. **记忆先做“可控记忆”，不要先做自动长期记忆。**
   历史研究场景里，错误记忆比没有记忆更糟。先做可见、可编辑、可删除的“研究状态卡 + 显式笔记”；自动长期记忆等有多轮评测和真实使用数据后再议。

4. **RAG 调优前先修已知正确性缺陷。**
   `badCase.md` 中 BC-025/026/027/029/035/036/037 仍未修复；且 13 题观察显示“融合 Recall@20 76.7% → 最终 71.8%”存在约 5pp 的选择损耗，向量分支（57.4%）明显弱于关键词（75.4%）。在这些没查清前加 reranker，很可能只是给一个漏召回的上游做精排。

推荐主线与周期：

```text
第1周        第2-4周          第5-7周           第8-11周        第12-16周
解锁+基线  →  评测运营+门禁  →  观测+可信交付  →  记忆管理      →  RAG 调优
   G0            G1                G2                G3              G4
```

单人、每周 3—4 个有效工作日约 14—18 周；全职约 10—12 周。每个阶段都有明确的“出门条件”，不满足不进入下一阶段。

---

## 1. 现状快照（2026-10-24）

### 1.1 评测

**已经有的：**

- `evaluation/pilot_*` 六层评测：查询理解/路由、组件召回、排序、候选上下文、生成与拒答、引用；
- 逐题、逐阶段、逐 K 的指标，以及 `metric_status{value, evaluable, reason}`；
- `pilot collect → prepare-reviews → import-reviews → score → compare` 的冻结采集与离线复核流程；
- 可归因比较器：核对数据集、索引、embedding、切分身份，区分“可比较”与“可归因”；
- 离线答案复核工作台（`index.html`），支持逐事实、逐引用、逐约束复核。

**关键缺口：**

| 缺口 | 现状 | 影响 |
| --- | --- | --- |
| 用例数量 | 30 题目标：20 道开发题完成，其中 8 题人工批准、12 题待审；10 道验收题尚未成稿 | 正式 Golden 成绩仍为 `N/A` |
| 候选相关性 | Precision@5/nDCG@5 有 10/13 可评；最终候选的 Precision@10/nDCG@10 只有 3/13（不同阶段 3—6/13），K=20 全部 `N/A`；标注只覆盖短前缀 | 排序结论只在 K≤5 稳定可用，无法支撑 Top-20 选择与 rerank 评估 |
| 真实基线 | 最近一次真实模型运行是 2026-10-05 的 13 题；2026-10-23 编排重构后未重跑 | 当前回答质量未知，整题通过率 3/13 只是旧快照 |
| 采集门禁 | 两道拒答题绑定旧版 `REQUIREMENTS.md` 整文件哈希，`validate_anchors` 会拒绝新采集 | 改一行需求文档就无法采集，评测实际上停摆 |
| CI 门禁 | 无 `.github/workflows`；唯一门禁是本地 `scripts/check.ps1`；DB 测试未设 URL 时静默跳过 | 回归无法在合并前被挡住 |
| 评审吞吐 | 逐题人工复核，工作台是离线 HTML | 12 题待审 + 10 题验收会长期拖欠 |

> 结论：工具层相对数据供给已经超前。**不要再写新的指标框架**，先把“能跑、有人审、能挡回归”补齐。

### 1.2 观测

**已经有的：**

- `log.py` 的 JSON 日志和 `log_event(..., **context)`；
- `HistoryResearchWorkflow.run_id`，以及 `AnswerResponse.execution_summary`（计划、任务状态、`usage_by_stage`、增补次数、停止原因）；
- `RetrievalStageTrace`：逐阶段 hit、耗时、输入数、drop 原因，但由 `capture_retrieval_trace` 控制，默认不采集；
- LlamaIndex `CallbackManager` 已接入自定义 LLM 适配器，LLM 调用有事件钩子。

**关键缺口：**

- 没有 HTTP 请求级 ID；`run_id` 只在 workflow 内，日志无法从一次 HTTP 请求串起来；
- 没有指标（QPS、错误率、分阶段延迟、token 成本、检索分支可用性、预算耗尽率）；
- 没有 trace 导出（Langfuse / OTel / Jaeger 均未接入）；
- 没有错误聚合、告警、SLO/SLI 看板；
- `/api/health`、`/api/ready` 只给布尔，无法回答“慢在哪一步、错在哪一步”。

### 1.3 记忆

**已经有的：**

- PostgreSQL 会话与消息持久化、多会话、软删除、访客隔离；
- 每 6 条完成消息触发一次确定性抽取式滚动摘要（保留最近 2 条）；
- 按消息数、字符数、token 预算注入历史；旧 `[E#]` 替换为“历史引用”，历史回答不能充当本轮证据；
- 仅在 `requires_conversation_context` 命中时使用历史。

**关键缺口：**

- 没有结构化的“会话研究状态”：人物、年份、约束、开放问题、已确认结论都只存在于自然语言摘要里；
- 没有跨会话记忆、用户偏好、研究笔记；
- 没有记忆的查看、编辑、删除、导出；
- `visitors.settings_json` 字段存在但未使用；
- 没有多轮评测集，无法证明“记忆变好”还是“记忆污染”。

### 1.4 检索与 RAG

**已经有的：**

- `bge-small-zh-v1.5`（512 维）+ FastEmbed + Qdrant 精确检索；
- 页内 650 字分片、BM25（PostgreSQL）+ 向量双路、RRF(k=60)、按页去重、来源奖励、时间覆盖；
- 人物/年份硬过滤、历史时期映射、结构化时间线/交集工具、篇目全文读取；
- 唯一问答编排（Plan-and-Execute DAG），有界增补与预算。

**关键缺口：**

- 无 cross-encoder / 学习式重排；
- 已写入 `previous_chunk_id` / `next_chunk_id`，但召回时从不扩展邻居；
- 页内分片 + 按页去重会丢掉同页第二个相关片段；
- 人物识别是字面别名匹配，无 NER、无消歧；
- 年份是“提及”，不是“事件时间”。

**13 题观察数据（2026-10-05 运行，2026-10-11 复核；小分母，只作方向参考）：**

| 指标 | 数值 |
| --- | ---: |
| 整题通过 | 3/13 |
| 必要事实完整覆盖 | 20/43（46.5%） |
| 必要证据 Recall@20（最终候选） | 71.8% |
| Precision@5 | 70.0% |
| nDCG@5 | 0.7315 |
| 组件召回 Recall@20 | 关键词 75.4% / 向量 57.4% / 融合 76.7% |
| 完整问答墙钟 | 中位 15.1s，最大 31.6s |
| 单题 token | 约 8,900 |

两点值得注意：**向量分支明显弱于关键词**，**融合到最终候选掉了约 5pp**。这决定了 RAG 阶段的第一批实验不是 rerank。

### 1.5 交付与工程底座

**已经有的：**

- 生产交付前 `citation_check` S1：移除非法 `[E#]`、丢弃原文找不到的引文、修正/移除冲突页码；
- 匿名 workspace、CSRF、三级配额、SSE、容器硬化、1000+ 测试、mypy/Ruff。

**关键缺口：**

- 不做事实蕴含校验、不做日期/未引用事实校验（BC-043 主动移除）；
- `evidence_status` 只有三态，无 `conflicting_sources` 与独立冲突数组；
- 单 worker、无连接池、无备份自动化、无 Alembic、无 CI；
- 评测结果不参与发布决策。

---

## 2. 四个方向分别要解决什么

### 2.1 评测体系：从“能算”到“能决策”

评测最终只需要回答四个问题：

| 问题 | 需要的能力 | 现状 |
| --- | --- | --- |
| Q1 现在多少分？ | 冻结数据集 + 真实模型基线 + 正式/暂定分离 | 缺真实基线与正式成绩 |
| Q2 变化来自哪一层？ | 分层指标 + 逐题诊断 | 已有，保持 |
| Q3 能不能发？ | 门禁、阈值、发布绑定 | 缺 |
| Q4 哪道题坏了？ | trace + badCase 回流 | 缺观测 |

执行原则：

- **不新增指标，除非某个决策没有指标可用。** 记忆阶段会新增一组多轮指标；RAG 阶段沿用现有指标。
- 每个指标必须有分母、可评题 ID、N/A 原因；未标注不按 0 分。
- 30 题是当前目标，不要扩到 100。统计功效不足时用配对 bootstrap 置信区间和分类型结论，不要宣称 1—2pp 的提升。
- 调参集与验收集分离：20 道开发题用于日常调参，10 道保留题只在 G1、G4 跑。
- **Langfuse 不作为 Golden 真源。** Golden 的冻结、复核、评分仍在 `evals/golden/` 与 `pilot` 里；Langfuse 只做 trace 与运行态观测。

### 2.2 观测体系：从“有日志”到“能定位”

目标：任意一条线上问题，1 分钟内回答：

- 哪一步慢？
- 哪一步错/降级？
- 花了多少 token、多少钱？
- 用的哪个代码版本、哪个索引 generation、哪个 prompt/model？

三层建设：

| 层 | 内容 | 优先级 |
| --- | --- | --- |
| 结构化日志 | 补 `trace_id`、`stage`、`error_code`、`index_generation`，保持 JSON | P0（第 1 周） |
| 指标 | 请求量、错误率、分阶段延迟、token/成本、检索分支可用性、预算耗尽、引用校验改动、空证据率 | P1（第 5—6 周） |
| Trace | HTTP → workflow → plan → task → retrieval → LLM → citation_check → delivery | P1（第 5—7 周） |

Langfuse 的定位与边界：

- **用途**：trace 浏览、会话回放、人工打分、成本聚合、bad case 定位；
- **不用途**：Golden 数据集真源、自动评分替代人工复核、提示词唯一管理后台；
- **部署**：Langfuse v3 自托管需要 Postgres + ClickHouse + Redis + S3 兼容存储，**不要塞进现有 1C1G 的 app compose**。单独一台 4C8G 主机，或先用 OTel Collector + Jaeger/Tempo 过渡；
- **数据**：默认只发送 ID、长度、哈希、分数、模型名、错误码；原文与引文默认 mask；调试采样显式开启并设保留期；
- **埋点顺序**：先 LLM 与 retrieval（已有 `CallbackManager`、`RetrievalStageTrace`），再 workflow 阶段，最后 HTTP。

### 2.3 记忆管理：三层，先可控

| 层 | 名称 | 内容 | 是否新建 |
| --- | --- | --- | --- |
| M0 | 会话工作记忆 | 最近消息 + 滚动摘要 | 已有，补结构化 |
| M1 | 会话研究状态卡 | 实体、年份、约束、开放问题、已确认结论 + 证据 ID | **新增，优先** |
| M2 | 显式长期研究笔记 | 用户主动保存的结论/来源/偏好，带证据指针与标签 | **新增，其次** |
| M3 | 语料结构化知识 | 人物/事件/关系，有复核状态 | 已有，不叫“记忆” |

硬性原则：

1. **记忆不是证据。** 注入时标注“记忆（非证据）”；任何事实结论必须在本轮重新取证，历史引用编号全部失效。
2. **默认不自动写长期记忆。** 只自动更新 M1，且用户可见、可编辑；M2 必须由用户显式保存。
3. **证据指针失效则记忆失效。** chunk 删除、文献停用、索引重建后，记忆标记 `stale`，不再注入。
4. **按 visitor 隔离。** 可导出、可删除；清 Cookie 即丢失（UI 需明确说明）。
5. **预算上限**：M1 ≤ 600 tokens，M2 ≤ 3 条/400 tokens；召回开销 < 100ms。

灰度开关：`memory_mode=off|session|session+notes`，默认 `session`（仅 M1），M2 灰度。

### 2.4 RAG：先正确性，再召回，再排序

执行原则：

- 一次只改一个变量；
- 固定 v6 开发集与标注口径；
- 记录代码 SHA、索引 generation、embedding/模型/参数版本；
- 报告多 K、逐题结果、延迟与 token；
- 保留题只在里程碑跑。

数据指向的调优顺序（详见第 4.5 节）：

```text
修正确性 bad case
  → 查“融合 76.7% → 最终 71.8%”的选择损耗
  → 邻居扩展
  → 上下文组装（页内多段、章节顺序、引文长度）
  → cross-encoder 重排
  → 切分策略
  → embedding 升级
  → 查询规划/路由
  → 生成与引用校验
```

**为什么 rerank 不排第一**：rerank 只能重排已召回的集合。当前向量分支 Recall@20 只有 57.4%，且有 5pp 在最终选择阶段丢失；先修召回与选择，再谈精排。否则 rerank 的收益会被上游漏召回吃掉。

---

## 3. 路线图总表

| 阶段 | 周期 | 主题 | 关键交付 | 出门条件（Gate） |
| --- | --- | --- | --- | --- |
| P0 | 第 1 周 | 解锁与基线 | 锚点改造；20 题真实基线；`trace_id`；CI 骨架 | **G0**：有非 `N/A` 的当前基线 |
| P1 | 第 2—4 周 | 评测运营与门禁 | 30/30 批准；候选相关性；mini-golden CI；发布门禁 | **G1**：CI 能挡住回归，正式成绩可引用 |
| P2 | 第 5—7 周 | 观测与可信交付 | OTel/Langfuse；指标看板；SLO/告警；软校验 | **G2**：任一问题 1 分钟内定位 |
| P3 | 第 8—11 周 | 记忆管理 | M1 状态卡；M2 笔记；多轮评测；记忆 UI | **G3**：记忆 A/B 净收益为正 |
| P4 | 第 12—16 周 | RAG 调优 | 选择损耗修复；邻居扩展；重排；上下文组装 | **G4**：每项改动有报告且保留题不回归 |

**并行小项**（不单独占阶段，穿插做）：

- PostgreSQL 连接池；
- 备份自动化 + 一次恢复演练；
- Alembic 迁移（可放到 P4 之后）；
- 把 `scripts/check.ps1` 的内容搬进 CI。

---

## 4. 分阶段任务

### 4.1 阶段 0（第 1 周）：解锁与基线

| ID | 任务 | 交付物 | 验收标准 | 估时 |
| --- | --- | --- | --- | ---: |
| 0.1 | 拒答锚点改造 | `evals/golden/refusal_basis_v1.json`：只冻结拒答依据的条款文本、来源文件、版本、哈希；`pilot_protocols` 改为校验“依据版本 + 条款哈希” | 不改旧 v5 JSON 即可跑新采集；旧 capture 仍可离线评分 | 1—1.5 天 |
| 0.2 | 真实模型基线 | 20 题 `--with-llm` 采集 + 复核包 + 评分报告，放在 `data/reports/eval_baseline_2026102x/` | 整题通过率、事实覆盖、Recall@5/10/20、P@5、nDCG@5、延迟、token 均有非 `N/A` 数值 | 2—3 天 |
| 0.3 | `trace_id` 贯穿 | HTTP 中间件生成/透传 `X-Request-ID`；workflow `run_id` 复用它；日志、`metadata_json`、响应头、执行摘要都带 | 用一条答案的 `trace_id` 能串起 plan/task/retrieval/LLM 日志 | 0.5—1 天 |
| 0.4 | CI 骨架 | `.github/workflows/ci.yml`：ruff + mypy + pytest；Postgres/Qdrant service；DB 测试失败而非 skip | PR 必过；故意破坏 DB 测试会红 | 1 天 |
| 0.5 | 文档同步 | README 文档入口加入本路线图；更新 Golden README 的锚点阻塞说明 | 新成员能按文档复现基线 | 0.5 天 |

**0.1 的关键设计**：不要继续绑整份 `REQUIREMENTS.md`。拒答依据只是其中少数条款，应该冻结“条款原文 + 版本 + 哈希”，需求文档其他部分可以正常演进。这样既保留审计性，又不让文档编辑阻断评测。

**0.2 的预算控制**：先在 `.env` 设一个明确的 token/费用上限，采集脚本记录实际用量；不要为了“跑满 20 题”无限重试。基线报告必须写明“暂定/正式”、分母、未评维度。

**G0 判定**：如果第 1 周结束仍没有当前代码的真实基线，**暂停所有记忆与 RAG 改动**，先补齐。否则后续所有“变好了”都无法证明。

---

### 4.2 阶段 1（第 2—4 周）：评测运营与门禁

| ID | 任务 | 交付物 | 验收标准 | 估时 |
| --- | --- | --- | --- | ---: |
| 1.1 | 15 题待审批准 | 逐字段裁定记录写入 `human_review` | 20/20 题批准 | 2—3 天 |
| 1.2 | 保留集补题 | 约束题、拒答题；题目、证据、必要事实、边界 | 保留集覆盖六类题型 | 3—4 天 |
| 1.3 | 候选相关性 + 固定排序池 | 每题 relevance 0/1/2、`relevance_complete`、ranking pool | 18 道可答题在 K=5/10/20 都有可评分母（当前 8 题） | 3—5 天 |
| 1.4 | 评审吞吐 | LLM 预填（引用原文、候选事实、疑似遗漏）+ 人工确认；记录每题复核时长 | 单题复核 ≤ 10 分钟；自动标签不得直接当 Golden | 1—2 天 |
| 1.5 | 评测 CI | mini-golden：3—5 篇固定文献、≤2k chunks 的小索引、10 题 retrieval smoke | PR 上 Recall@10/MRR 回归 >1pp 阻止合并 | 1—2 天 |
| 1.6 | 发布门禁 | `eval compare` + 阈值写入 CI/发布脚本；绑定 git SHA、镜像 digest、索引 generation、模型版本 | 每次发布有评测记录，可回滚定位 | 1 天 |
| 1.7 | 反馈闭环 | 👍/👎 + 原因 + `trace_id` 落库；每周转 badCase/新用例 | 反馈可查询、可转标注 | 1—2 天 |

**1.3 的做法**：不要对 30 个候选逐个手标。先按“必要证据 + 同章节/同页邻近 + 向量近邻”生成候选池，用模型给出 0/1/2 的**建议**和理由，再由人工确认/修正；`relevance_complete=false` 的题继续让 Precision/nDCG 为 `N/A`，不要用未标候选冒充不相关。

**1.5 的取舍**：全量 22,338 chunk 的索引不适合每次 PR 构建。CI 用固定小索引跑“检索回归冒烟”，全量 20 题放 nightly 或本机；两者口径分开写清楚，不能把 mini-golden 的分数当正式 Golden。

**G1 判定**：

- 30/30 人工批准，版本冻结为 v6；
- 正式成绩非 `N/A`，且至少有一次“改一个变量 → 同口径对比 → 结论”的完整演练；
- CI 能在合并前挡住一次故意的检索回归。

---

### 4.3 阶段 2（第 5—7 周）：观测与可信交付

#### 4.3.1 内部 trace 模型（先定义，后接后端）

| Span | 关键属性 |
| --- | --- |
| `http.request` | route、status、visitor_hash、latency、request_id |
| `workflow.run` | run_id、question_hash、top_k、model、prompt_version、index_generation、stopped_reason |
| `plan` | intent、years、people、constraints、task_count、planner_status、tokens |
| `task` | task_id、tool、status、evidence_count、missing_aspects、elapsed_ms |
| `retrieval.keyword` / `retrieval.vector` | k、hit_count、elapsed_ms、degraded、filters |
| `retrieval.fusion` / `selection` | input/output counts、drop reasons、coverage |
| `llm.*` | stage、model、tokens、finish_reason、error_code、latency |
| `citation_check` | removed_ids、dropped_quotes、page_fixes |
| `delivery` | citation_count、evidence_status、answer_chars、limitations |

要求：

- 默认不记录正文；只记 `question_hash`、`quote_hash`、长度；
- `index_generation` 与 embedding/切分版本必须进 trace，否则无法解释“同一问题昨天对今天错”；
- span 失败不阻断主流程（观测是旁路）。

#### 4.3.2 接入 OTel + Langfuse（或 Jaeger 过渡）

- 先加 `opentelemetry-sdk` + OTLP exporter，默认 no-op；
- LlamaIndex 侧用 `CallbackManager` 事件映射 LLM/retrieval span；
- workflow 的 `plan/task/synthesis` 用显式 span 包裹；
- Langfuse 作为 OTLP 后端之一，用环境变量切换，代码不绑死供应商；
- 如果暂时没有第二台主机：先上 OTel + Jaeger/Tempo，Langfuse 等主机到位再切；不要为了“上 Langfuse”把 app 主机压垮。

#### 4.3.3 指标与看板

最小指标集：

- `qa_requests_total{status, route}`
- `qa_latency_seconds{stage}`（histogram）
- `llm_tokens_total{stage, model, kind}`
- `llm_errors_total{code, stage}`
- `retrieval_branch_failures_total{branch}`
- `retrieval_zero_hits_total{intent}`
- `budget_exhausted_total`
- `citation_check_modifications_total{kind}`
- `evidence_status_total{status}`
- `index_build_age_seconds`

SLO（先定三个，不要贪多）：

| SLI | 目标 |
| --- | --- |
| 问答可用性（月度） | ≥ 99% |
| 问答 P95 延迟 | ≤ 20s（过渡），目标 15s |
| 检索就绪 | ≥ 99.5% |

告警（先接三条）：

- 5 分钟内 5xx 比例 > 5%；
- P95 延迟连续 10 分钟 > 25s；
- LLM 错误率连续 10 分钟 > 10% 或预算耗尽率 > 10%。

#### 4.3.4 可信交付软校验

BC-043 的问题不是“不该校验”，而是“校验失败就降级摘录”。正确做法是**先观测、定阈值、再拦截**：

| 检查 | 阶段 | 处置 |
| --- | --- | --- |
| 非法 `[E#]` | 第 5 周起 | 只记录、只计入 score；2 周后硬拦截 |
| 引文在 chunk 中找不到 | 第 5 周起 | 只记录；2 周后硬拦截并移除该引用 |
| 页码与证据区间冲突 | 第 6 周起 | 只记录；阈值确定后警告或改写 |
| 日期与引用冲突 | 第 6 周起 | 只记录；不阻断 |
| 未引用事实比例（启发式） | 第 6 周起 | 只记录 |
| 来源冲突候选 | 第 7 周起 | 只记录，为五态/冲突字段做准备 |

落地方式：

- 复用 `answering/validation.py` 的离线检查逻辑，但只输出结构化事件；
- 事件写入本地表（如 `answer_quality_events`）并同步为 Langfuse score；
- `limitations` 中说明“已检测但未阻断”的项目；
- 用 2 周数据算误伤率，再决定哪些检查硬拦截。目标：硬拦截误伤率 < 2%。

#### 4.3.5 反馈入口

- 每条回答下方 👍/👎 + 可选原因；
- 落库字段：`trace_id`、`session_id`、`message_id`、`reason`、`comment`、`created_at`；
- 每周把负反馈转成 `badCase.md` 条目或评测候选；
- 不在前端暴露内部证据全文。

**G2 判定**：随机抽 10 条线上问题，都能在 1 分钟内定位到最慢/失败步骤；trace 覆盖率 ≥ 95%；SLO 看板可用；原文默认不出机。

---

### 4.4 阶段 3（第 8—11 周）：记忆管理

#### 4.4.1 记忆契约

先写清楚“什么算记忆、什么不算”，再写代码：

| 类型 | 是否记忆 | 说明 |
| --- | --- | --- |
| 本轮证据 | 否 | 证据，不是记忆；每轮重新检索 |
| 历史回答中的结论 | 是（M1） | 只作为研究线索，不作为事实 |
| 用户在问题中给出的约束 | 是（M1） | 年份、来源、人物、否定条件 |
| 用户主动保存的笔记 | 是（M2） | 带证据指针，可删除 |
| 模型对用户的推断（偏好/立场） | 暂不 | 高风险，先不做 |
| 人物/事件/关系结构化数据 | 否 | 语料知识，有复核状态 |

#### 4.4.2 M1：会话研究状态卡

建议 schema（存 `conversation_sessions` 新列或独立表）：

```json
{
  "schema_version": 1,
  "updated_at": "2026-10-24T08:00:00Z",
  "entities": [
    {"type": "person", "id": "zhou_enlai", "name": "周恩来", "source": "user|planner"}
  ],
  "time": {"start": 1956, "end": 1956, "mode": "year"},
  "constraints": [
    {"kind": "source", "text": "只看年谱", "turn": 2},
    {"kind": "style", "text": "需要原文引用", "turn": 1}
  ],
  "open_questions": ["1956 年外事活动还有哪些未覆盖？"],
  "findings": [
    {"claim": "……", "evidence_ids": ["E3"], "status": "supported", "turn": 2}
  ],
  "stale_after_index": "history_chunks_20261020"
}
```

更新规则：

- 确定性优先：人物别名、年份、显式约束用现有规则抽取；
- 模型只负责 `findings` 的候选，必须通过 schema 校验，且 `evidence_ids` 必须在本轮 `EvidenceRegistry` 中存在；
- **合并而不是覆盖**：用户手动编辑过的字段加 `pinned=true`，后续自动更新不得覆盖；
- 每轮更新有版本号，失败不阻断回答；
- 注入时压缩成 ≤ 600 tokens，放系统提示词的“研究上下文（非证据）”段。

#### 4.4.3 M2：显式研究笔记

- 入口：回答下方“保存为研究笔记”，或输入 `/note`；
- 字段：`note_id`、`visitor_id`、`title`、`body`、`evidence`（document_id/page/quote_hash）、`tags`、`session_id`、`created_at`、`expires_at`；
- 召回：先关键词/标签 + 时间衰减，量大了再加向量；每次最多 3 条；
- 冲突：笔记与当前证据冲突时，显式提示“你的笔记与当前材料不一致”，以当前证据为准；
- 生命周期：默认 180 天 TTL；可手动删除/导出；visitor 删除级联。

#### 4.4.4 多轮评测集（独立套件）

不要塞进现有 30 题单轮 Golden，单独建 `evals/memory/`：

- 15 组序列 × 3—4 轮，覆盖：指代消解、约束继承、话题切换、纠正、跨会话召回、无历史对照；
- 每轮标注：应解析的实体、应保留的约束、应引用的证据、允许的记忆使用；
- A/B 三臂：`off` / `session`（M1） / `session+notes`（M1+M2）；
- 指标：

| 指标 | 定义 | 分母 |
| --- | --- | --- |
| Follow-up Resolution Accuracy | 正确解析指代/省略的轮数 / 适用轮数 | 多轮 turn |
| Constraint Retention Rate | 继承并遵守前轮约束的轮数 / 有约束的轮数 | 多轮 turn |
| Memory Precision | 注入且相关的记忆条数 / 注入条数 | 注入项 |
| Memory-induced Unsupported Claim Rate | 因记忆产生且无当前证据支持的论断数 / 论断数 | claim |
| Cross-session Leakage | 其他 visitor/session 的记忆被召回次数 | 必须为 0 |
| Memory Recall | 相关笔记被召回的次数 / 应召回次数 | 笔记 |
| Overhead | 额外 token 与延迟 | 每题 |

验收目标（暂定，跑完基线再校准）：

- Follow-up Resolution Accuracy 相对 `off` 提升 ≥ 10pp；
- Constraint Retention Rate ≥ 90%；
- Cross-session Leakage = 0；
- Unsupported Claim Rate 不高于 `off`（允许 ±1pp 噪声）；
- 额外 token ≤ 800/题，额外延迟 ≤ 300ms。

#### 4.4.5 UI 与灰度

- 侧栏“研究上下文”：显示 M1 的实体/年份/约束/开放问题，可编辑、可清空；
- “研究笔记”列表：查看、搜索、删除、导出；
- 回答中标注“参考了你的研究笔记（非证据）”；
- 首次使用提示：清 Cookie/换设备会丢失会话与笔记；
- `memory_mode` 灰度：先内部 1 周，再默认开启 M1，M2 保持手动。

**G3 判定**：三臂 A/B 有报告；M1 净收益为正；无跨会话泄漏；用户可查看/删除记忆；额外开销在预算内。否则只保留 M1，M2 回滚。

---

### 4.5 阶段 4（第 12—16 周）：RAG 调优

#### 4.5.1 实验矩阵

| 顺序 | 变量 | 假设 | 主指标 | 护栏 |
| ---: | --- | --- | --- | --- |
| 0 | 修 BC-025/026/027/029/035/036/037 | 这些是正确性缺陷，不是调参 | 对应 bad case 回归 | 不改变其他题 |
| 1 | 选择损耗诊断 | 按页去重/时间覆盖/证据门槛丢掉了已召回的相关页 | 融合 vs 最终的 Recall@20 差 | 上下文噪声不升 |
| 2 | 邻居扩展（±1 chunk） | 跨 chunk 的事件与指代需要上下文 | Required Evidence Recall、Fact Recall | token +≤50%，P95 不升 |
| 3 | 上下文组装 | 章节顺序、页内多段、引文长度自适应能提升事实覆盖 | Fact Recall、Context Precision | 冗余率不升 |
| 4 | cross-encoder rerank | 在已召回集合内提升排序 | nDCG@10、P@5、Fact Recall | P95 ≤ 20s |
| 5 | 切分策略 | 跨页/结构感知切分减少断章 | Recall、引用页码正确率 | 页级标注可映射 |
| 6 | embedding 升级 | 向量分支是短板 | 向量 Recall@20、融合 Recall | 全量重建成本 |
| 7 | 查询规划/路由 | 细约束丢失、结构化阈值不当 | Routing Accuracy、Constraint Retention | 不增加澄清率 |
| 8 | 生成与引用 | claim 级软校验、冲突分列 | Unsupported Claim Rate、拒答准确率 | 不降低答案覆盖 |

#### 4.5.2 重点实验说明

**实验 1：5pp 选择损耗。**
现有 `RetrievalStageTrace.dropped` 已记录丢弃原因。先统计“融合 Top-20 里有、最终 Top-12 里没有”的 required evidence 是被哪条规则丢的：按页去重、时间覆盖、证据门槛、Top-K 截断。若是按页去重，尝试“每页保留前 2 个不同文本片段”，观察 Precision 与噪声；若是时间覆盖，检查 `per_year` 的配额是否挤掉了高相关页。

**实验 2：邻居扩展。**
只对最终 Top-N（如 8）扩展前后各 1 个 chunk，且要求同章节、同年份；扩展后重新按页去重。指标看 Required Evidence Recall 与 Fact Recall，不看总命中数。风险是上下文变长后模型分心，需同时看 Context Precision 和答案事实覆盖。

**实验 3：上下文组装。**
当前每条证据引文最多 420 字符；对 `analyze` 任务和复杂比较题，420 字可能不够。建议按任务类型自适应：普通问答 420，分析任务 800，全文任务不限。同时按文档/页码排序，保留 `section_path`，让模型看到章节语境。

**实验 4：rerank。**
候选 50 → 12，优先 CPU 可跑的 cross-encoder（ONNX/量化），或小参数重排模型。先离线测 nDCG@10/P@5，再测端到端 Fact Recall；若 P95 增加 > 2s，缩小候选池或只对复杂题启用。**不要在召回没修好时把 rerank 当银弹。**

**实验 5：切分。**
页内分片保证页码精确，但跨页事件会断。可尝试“同一章节内跨页合并、保留 `pdf_page_start/end`”的结构感知切分；代价是页级 gold 映射需要支持跨页区间（现有闭区间逻辑已兼容）。重建索引后必须重跑 citation page validity。

**实验 6：embedding。**
候选 `bge-m3`、`bge-large-zh-v1.5`、`Qwen3-Embedding` 级别；全量重建 22k chunk 需要时间与磁盘。先在小切片上对比向量 Recall，再决定是否全量。记录 FastEmbed/模型版本与维度，Qdrant collection 用新 alias 原子切换。

#### 4.5.3 每次实验的报告模板

```text
实验名 / 日期 / 负责人
假设：
唯一变量：
固定项：dataset SHA、代码 SHA、索引 generation、embedding、切分、RRF、Top-K、模型、prompt
结果：
  Recall@5/10/20（分母）
  P@5/10（可评题数）
  nDCG@5/10（可评题数）
  Required Fact Recall
  Answer Correctness / Forbidden Claims
  P50/P95 延迟、token
逐题 delta（变好/变差 case ID）
结论：采纳 / 回滚 / 继续观察
```

#### 4.5.4 延迟预算

当前中位 15.1s、最大 31.6s，已经压线。RAG 改动叠加前先设预算：

- 检索总耗时 ≤ 3s；
- rerank ≤ 0.5s（CPU）或 ≤ 0.2s（GPU）；
- 邻居扩展带来的 prompt 增量 ≤ 30%；
- 端到端 P95 ≤ 20s（过渡），15s 为目标。

超过预算的优化，即使指标更好，也先不进生产。

**G4 判定**：每项改动都有同口径报告；开发集至少一项 +3pp；保留题不回归；P95 不破 20s；可一键回滚到旧索引/旧配置。

---

## 5. 评测口径补充

### 5.1 新增维度的放置

- 记忆指标放独立套件 `evals/memory/`，不改变现有 30 题分母；
- RAG 实验沿用 `pilot` 的 retrieval/ranking/context/generation 维度；
- 新增“可信交付”维度时，先在报告中单列，不混入 Answer Correctness。

### 5.2 统计与结论

- 30 题样本小，报告必须带分母与可评题 ID；
- 用配对 bootstrap 给 95% 置信区间；
- 差异 < 3pp 不宣称“提升”，只说“未观察到退化”；
- 分类型看：timeline / intersection / viewpoint / event / refusal，避免某一类被平均掩盖；
- 保留题跑完即冻结，不反复用来调参。

### 5.3 防止“指标好看、回答更差”

每次实验同时看四组：

1. 检索：Recall / MRR / nDCG；
2. 上下文：相关比例、冗余率；
3. 生成：Fact Recall、Answer Correctness、Forbidden Claims；
4. 成本：延迟、token。

任何一组明显变差，都不能用另一组的提升来抵消，除非有明确的产品取舍记录。

---

## 6. 工作量估算

| 阶段 | 人日 | 日历周（每周 3—4 个有效工作日） |
| --- | ---: | ---: |
| P0 解锁与基线 | 5—7 | 1 |
| P1 评测运营与门禁 | 12—16 | 3 |
| P2 观测与可信交付 | 10—12 | 3 |
| P3 记忆管理 | 12—15 | 4 |
| P4 RAG 调优 | 16—20 | 5 |
| **合计** | **55—70** | **14—18** |

说明：

- 不含 OCR/索引重建的机器时间；
- 不含 Langfuse 主机采购/运维；
- 若全职投入，约 10—12 周；
- 若中途插入产品功能（冲突展示、引用跳转等），顺延。

---

## 7. 风险与决策门

### 7.1 主要风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 标注继续拖延 | 评测永远 `N/A`，后面全是盲改 | 设硬截止：P1 结束必须 30/30；先出 20 题正式成绩，再补 10 题 |
| Langfuse 运维过重 | 拖慢主线 | 单独主机或先用 Jaeger；埋点与后端解耦；不阻塞 P2 |
| 记忆污染 | 错误结论跨会话传播 | 默认不自动写长期；证据指针校验；A/B；可删除 |
| 30 题过拟合 | 调参收益无法泛化 | 保留题隔离；一次一个变量；报告置信区间 |
| 延迟恶化 | 用户体验下降 | 每项实验设延迟预算；P95 门禁 |
| 隐私外发 | 史料/问题泄露 | 默认 mask；自托管；保留期；调试采样显式开启 |
| 单 worker/连接池 | 并发瓶颈 | P2 并行修连接池；观测先暴露问题 |
| 双评测框架漂移 | 口径混乱 | 明确 `pilot` 为唯一新入口；`golden.py` 只维护旧 v1，不再加功能 |

### 7.2 决策门

| Gate | 时点 | 判定条件 | 不通过怎么办 |
| --- | --- | --- | --- |
| G0 | 第 1 周末 | 有当前代码的真实基线，非 `N/A` | 暂停记忆/RAG，继续补基线 |
| G1 | 第 4 周末 | 30/30 批准；CI 能挡回归；正式成绩可引用 | 不合并记忆/RAG 改动 |
| G2 | 第 7 周末 | trace 覆盖 ≥95%；10 条问题可 1 分钟定位；SLO 看板 | 先修观测，记忆延后 |
| G3 | 第 11 周末 | 记忆 A/B 净收益为正；无泄漏；可删除 | 只保留 M1，M2 回滚 |
| G4 | 第 16 周末 | 每项 RAG 改动有报告；保留题不回归；P95 ≤20s | 回滚最近一项，重做实验 |

---

## 8. 接下来 10 个工作日

| 工作日 | 任务 | 产出 |
| --- | --- | --- |
| D1 | 0.1 锚点改造 + v6 骨架 | `refusal_basis_v1.json`、校验改造、单测 |
| D2—D3 | 0.2 20 题真实采集 | `capture.json`、`.partial.json`、成本记录 |
| D4—D5 | 生成复核包 + 完成事实/引用复核 + 评分 | 基线报告（暂定） |
| D6 | 0.3 `trace_id` 贯穿 | 中间件、日志、元数据、响应头 |
| D7—D8 | 0.4 CI 骨架 | `ci.yml`、DB service、失败而非跳过 |
| D9 | 1.1 12 题批准（第一批） | 裁定记录 |
| D10 | 1.3 候选相关性试点（5 题） | 标注规范 + 5 题 relevance |

命令示例（以实际 CLI 帮助为准）：

```powershell
# 基线采集（当前 20 题工作集）
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset evals/golden/golden_dataset.json `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --with-llm `
  --run-name baseline_20261029 `
  --output data/reports/eval_baseline_20261029/capture.json
```

> 2026-10-29：当前工作集是 `golden_dataset.json`（20 题，15 开发 + 5 保留），旧 v3–v6 标注/协议已清理；采集不再需要 `--protocols`。当前本地基线见 [observations/20261029_golden20_local](../evals/golden/observations/20261029_golden20_local/README.md)。

---

## 9. 现在不要做

| 项 | 原因 |
| --- | --- |
| 继续扩指标/再写一套评测框架 | 工具已超前，瓶颈在数据与门禁 |
| 把 Golden 迁进 Langfuse datasets | 会破坏冻结、复核、可归因比较；Langfuse 只做观测 |
| 先做自动长期记忆/用户画像 | 污染风险高，且当前没有多轮评测证明收益 |
| 先换 embedding 或先加 rerank | 召回上限与选择损耗未查清，精排收益会被吃掉 |
| 上 Kubernetes / 微服务 / 多租户 | 22k chunk、单域、单租户，分布式只放大运维成本 |
| 把 30 题扩到 100 题 | 数量不等于代表性；先保证 30 题可复核 |
| 在没有基线时改 prompt | 无法区分“变好”与“换了个说法” |

---

## 附录 A：Langfuse 方案取舍

| 方案 | 优点 | 代价 | 适用 |
| --- | --- | --- | --- |
| A. Langfuse 自托管 v3 | 数据不出内网；LLM 专属 UI、评分、成本 | 需 Postgres + ClickHouse + Redis + S3；至少 4C8G；运维成本 | 有第二台主机，长期方案 |
| B. Langfuse Cloud | 接入最快 | 问题、证据、模型调用外发；隐私与合规风险 | 仅脱敏调试，不作为默认 |
| C. OTel + Jaeger/Tempo | 轻量；通用 trace；易替换后端 | 无 LLM 专属评分/成本视图 | 过渡方案，先跑通埋点 |

建议路径：**先 C 后 A**。埋点用 OTel 标准，后端可切换；等 P2 中段、确认 trace 价值后再上 Langfuse 自托管。不要为了工具而工具。

## 附录 B：与 ENTERPRISE-GAP 的对应

| ENTERPRISE-GAP 建议 | 本文位置 | 说明 |
| --- | --- | --- |
| 0.1 生产侧软校验 | 4.3.4 | 先观测、后拦截 |
| 0.2 CI | 0.4、1.5 | 先骨架，再评测门禁 |
| 0.3 覆盖率/契约 | 1.5—1.6 | 与评测门禁一起 |
| 0.4 Golden retrieval smoke | 1.5 | mini-golden，避免全量索引 |
| 0.5 反馈入口 | 4.3.5 | 与 trace 绑定 |
| 1.1 30 题冻结 | 1.1—1.3 | 本文最重要的交付 |
| 1.3 检索优化 | 4.5 | 按数据指向排序 |
| 1.5 可观测性 | 4.3 | 本文展开为 trace/指标/SLO |
| 1.6 连接池 | 并行小项 | 观测阶段暴露后修 |
| 2.x 工程化 | P4 之后 | 不阻塞当前主线 |

---

*本文是规划文档，未修改 Agent 逻辑、索引或评测标注。若与代码实际行为冲突，以代码与服务的 `/openapi.json`、`/api/health`、`/api/ready` 为准。*
