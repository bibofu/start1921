# start1921 · 基于本地文档的近现代史研究 Agent

面向中国近现代史学习与研究的本地知识库 Agent，以 1921—1978 年为研究边界。项目先检索本地文献，再依据材料回答，重要事实附文献名和 PDF 页码；支持人物经历、人物交集、观点检索，以及通过 CLI/API 查询组织任职候选。

## 文档入口

| 文档 | 职责 |
| --- | --- |
| [RAG 实现说明](RAG-IMPL.md) | 当前查询规划、分片、混合检索、排序、上下文、生成和引用校验 |
| [结构化研究模型](RESEARCH_SCHEMA.md) | 人物、事件、关系、证据、复核状态及查询接口 |
| [PostgreSQL](POSTGRESQL.md) / [关键词索引](KEYWORD_POSTGRESQL.md) / [Qdrant](QDRANT_SERVICE.md) | 当前服务配置、测试方法及历史迁移记录 |
| [Linux 部署](deploy/README.md) | Docker 服务隔离、数据迁移、HTTPS 入口、健康检查与升级回滚 |
| [Golden 评测入口](evals/golden/README.md) / [可重复评测流程](evals/golden/REPEATABLE_WORKFLOW.md) | 数据版本、人工复核状态、分层指标与实验比较 |
| [需求基线](REQUIREMENTS.md) | 原始需求目标与验收约束，部分内容尚未实现 |
| [问答问题记录](badCase.md) | 已定位的问答问题、原因、修复及验证 |

实现细节集中在对应专题文档，历史实验结果保留在 `evals/`。`REQUIREMENTS.md` 被评测拒答依据引用，本次保留原始字节；其中的 `TASK_PLAN.md` 是已移除的历史规划引用，旧技术选型、五类回答状态和后续版本描述不代表当前实现。当前接口以代码及服务的 `/docs`、`/openapi.json` 为准。

## 快速启动

### 1. 准备环境

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/)、Git LFS、PostgreSQL 和独立 Qdrant 服务。DeepSeek API Key 可选；未配置时返回本地证据摘录。项目命令为 `start1921`，保留 `history-agent` 兼容入口；Python 包名和环境变量前缀仍为 `history_agent`、`HISTORY_AGENT_`。

```powershell
git clone git@github.com:bibofu/start1921.git
cd start1921
git lfs install --local
git lfs pull
uv sync --extra ocr --extra vector --extra app --group dev
Copy-Item .env.example .env
```

macOS/Linux 使用 `cp .env.example .env`。PDF 通过 Git LFS 管理，源码压缩包可能只含指针；索引仍需本地构建。以 `uv sync` 为支持的安装方式，依赖排除配置见 [pyproject.toml](pyproject.toml)。

### 2. 配置服务

编辑 `.env`：

```dotenv
HISTORY_AGENT_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
HISTORY_AGENT_QDRANT_URL=http://127.0.0.1:6333
# 可选：会话、关键词默认共用主库
# HISTORY_AGENT_CONVERSATION_DATABASE_URL=postgresql://...
# HISTORY_AGENT_KEYWORD_DATABASE_URL=postgresql://...
DEEPSEEK_API_KEY=你的密钥
```

主库、会话库、关键词索引仅支持 PostgreSQL，向量索引仅支持 Qdrant 服务。原 SQLite 库与迁移备份已于 2026-10-21 清理，只保留 PostgreSQL dump 与 Qdrant snapshot 作为可恢复归档，运行路径不会回退到本地文件，详见 [清理记录](POSTGRESQL.md#2026-10-21-sqlite-资产清理)。新机器需先按服务文档准备数据库；本工作区的 Windows 本机后台进程可用以下脚本启动：

```powershell
.\scripts\postgres.ps1 start
.\scripts\qdrant.ps1 start
uv run start1921 llm status
# 配置密钥后验证真实连通性
uv run start1921 llm check
```

查询规划默认使用 `deepseek-v4-flash`，回答默认使用 `deepseek-v4-pro`，均关闭 thinking。规划输出默认上限为 2000 tokens，已有 `.env` 的显式配置优先，不会被自动覆盖。配置字段及默认值见 [.env.example](.env.example) 和 [config.py](app/history_agent/config.py)。修改 `.env` 后需重启服务。

### 3. 首次建库或更新史料

新增 PDF 放入 `docs/` 并登记到 [文献目录](config/corpus_catalog.json)。完成 LFS 下载后执行：

```powershell
uv run start1921 corpus scan
uv run start1921 extract text
uv run start1921 extract ocr
uv run start1921 extract report
uv run start1921 process chunks
uv run start1921 index build-keyword
uv run start1921 index build-vector
```

首次 OCR 和向量构建需要下载模型，耗时较长。版本一致的已完成页面结果会复用。已登记 PDF 的哈希变化需先核对，再用 `corpus scan --accept-changes` 接受。停用文献的分片应移出活跃 `data/processed/chunks/` 后再重建双索引；结构化查询也会过滤停用或缺失来源。

结构化研究功能还需初始化人物等主数据并抽取事件：

```powershell
uv run start1921 research init
uv run start1921 research extract-chronologies --document-id zhou_enlai_chronology_1949_1976
1..9 | ForEach-Object {
    uv run start1921 research extract-chronologies --document-id "mao_zedong_chronology_volume_$_"
}
uv run start1921 research merge-events --dry-run --json
uv run start1921 research merge-events
uv run start1921 research extract-relationships
```

以上为 PowerShell 示例；其他终端逐卷传入相应 `--document-id`，也可重复该选项一次处理多份。无参数抽取会包含已撤下的林彪年谱，缺少其页面文件时会中断，因此新建库需显式选择已有文献。目录中的邓小平年谱可用于全文检索，尚无对应结构化年谱抽取器。自动事件、交集和任职均为待复核候选，人名提及不等于共同参与，也不能据单次任命记载外推任期。

可选的 `research enrich-events --dry-run --limit 5` 预览模型增强对象。去掉 `--dry-run` 会向 DeepSeek 发送所选事件的短证据并记录待复核结果；每事件证据正文合计上限为 1200 字符，详见 [模型事件抽取说明](evals/MODEL_EVENT_EXTRACTION.md)。

### 4. 启动页面并检查

```powershell
uv run start1921 serve
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)，按 `Ctrl+C` 停止。可问“毛泽东在1949年有哪些经历”“毛泽东和周恩来在长征期间有哪些交集”“毛泽东关于调查研究有哪些论述”。

```powershell
uv run start1921 health --json
```

`/api/health` 提供进程与配置摘要，`/api/ready` 实际探测数据库和双索引。索引未就绪时检查建库步骤；密钥未配置时使用摘录模式；模型调用失败时保留本地检索结果并降级。关键词或向量单路故障会标记检索不完整，双路均不可用会返回错误。

## 当前行为与边界

- 所有问答共用 LlamaIndex `HistoryResearchWorkflow` 的 Plan-and-Execute 流程：简单问题通常一个取证任务；复杂研究通过有依赖关系的检索、原文读取及分析任务完成。同步 API 与 SSE 仅交付方式不同，结构化和全文读取也是同一计划中的工具。
- 保留中文分词、PostgreSQL BM25、Qdrant embedding 与检索、RRF、人物及时间过滤和历史研究规则。人物明确、完整年份或年份区间的时间线/两人交集可使用结构化工具；月份、地点、否定、指定来源等细约束使用混合检索。组织任职的结构化入口仍为 CLI/API。
- 规划不可用时在同一流程内编译保守计划。研究计划总计最多 8 个任务、最多 2 次依据证据缺口的计划增补，同时执行最多 2 个就绪任务，共享请求时限和模型调用预算；预算结束后报告已有证据及缺口。组件边界与诊断字段见 [RAG 实现说明](RAG-IMPL.md)。
- 引用核查检查证据编号、文献页码及事实句引用覆盖，不能替代逐项人工语义核验。SSE 仍传输模型增量，但前端只缓冲、不渲染草稿；收到 `done` 后才展示一次经过校验的最终回答。停止生成、删除会话及 Markdown 渲染见 [流式问答说明](evals/STREAMING_CHAT.md)。
- 不做账号登录：服务端为每个浏览器签发 HttpOnly 匿名 workspace cookie，所有会话、消息和配额按 `visitor_id` 隔离；跨访客访问统一返回 404。清 Cookie、换浏览器或换设备会丢失历史，页面提供首次使用提示。
- 会话正文存于 PostgreSQL，支持多会话列表、新建、切换、重命名、置顶、软删除/恢复；消息开始生成时先落 `pending`，完成/停止/失败分别更新状态。服务端按消息数、字符数和 token 预算构造追问上下文；每 6 条完成消息生成一次确定性滚动摘要（保留最近 2 条），摘要只用于承接、不作为史实证据。历史引用失效化，只有本轮证据可支撑本轮事实。
- 当前 `evidence_status` 为 `supported`、`partial`、`no_evidence`。限制与差异通过答案正文和 `limitations` 表达；尚未实现需求基线中的五类状态和独立 `conflicts` 字段。

## 常用维护入口

完整参数由 CLI 帮助维护，避免在多份文档中重复列举：

```powershell
uv run start1921 --help
uv run start1921 research --help
uv run start1921 eval --help

uv run start1921 search-hybrid "毛泽东关于调查研究的观点" --top-k 8
uv run start1921 research people resolve "伍豪" --json
uv run start1921 research timeline 周恩来 --year 1956 --limit 50
uv run start1921 research intersections 毛泽东 周恩来 --year 1949 --json
uv run start1921 research relationships 周恩来 --at 1956 --json
uv run start1921 research review-queue --limit 20 --json
```

HTTP 接口与命令行共用业务实现：

| 接口 | 功能 |
| --- | --- |
| `POST /api/questions` | 问答及结构化引用 |
| `POST /api/questions/stream` | SSE 流式问答 |
| `GET /api/health` / `GET /api/ready` | 存活与依赖就绪检查 |
| `GET /api/visitor` | 匿名 workspace、CSRF token 与配额 |
| `GET /api/sessions` | 当前 workspace 的会话列表 |
| `POST /api/sessions` | 新建会话 |
| `GET /api/sessions/{session_id}` | 读取会话与最近消息 |
| `PATCH /api/sessions/{session_id}` | 重命名、置顶 |
| `DELETE /api/sessions/{session_id}` | 软删除会话（30 天内可恢复） |
| `POST /api/sessions/{session_id}/restore` | 恢复软删除会话 |
| `POST /api/sessions/claim` | 认领旧版单会话 |
| `GET /api/people/{person_id}/timeline` | 人物时间线 |
| `GET /api/people/{person_id}/intersections/{other_person_id}` | 两人共同动作候选 |
| `GET /api/people/{person_id}/relationships` | 指定时间的组织任职候选 |

请求/响应字段见 [问答模型](app/history_agent/answering/models.py)、[研究模型](app/history_agent/research/models.py) 和运行服务的 [API 文档](http://127.0.0.1:8000/docs)。

## 评测与开发检查

Golden 目标为 30 个高质量用例，目前 v5 有 20 道开发题，题目定义 8 题人工批准、12 题待审；另 10 道独立验收题仍隔离。候选相关等级和真实答案未随题目定义一起获批。最新 [13 题回答复核](evals/golden/observations/20261011_calibrated/README.md) 是对同一历史采集的重审，不代表新模型运行或正式 Golden 成绩。

本轮清理前，拒答题绑定的 `REQUIREMENTS.md` 哈希已与现文件不一致，当前全量新采集会被锚点校验阻止；需单独复核并发布新标注版本。旧采集仍可按绑定版本离线评分，详见 [评测流程](evals/golden/REPEATABLE_WORKFLOW.md)。版本化标注、裁定、候选池和观测快照保留用于审计，不按重复文件删除。

历史页级评测可通过 `eval retrieval`、`eval answers`、`eval comprehensive`、`eval golden` 运行，适用维度、分母和限制见各自报告。真实模型调用需显式启用相应参数。

```powershell
& .\scripts\check.ps1
```

该脚本执行 Ruff、mypy、pytest，以及 Node.js 可用时的前端语法/流式检查。数据库测试需要 `HISTORY_AGENT_TEST_POSTGRES_URL` 指向独立测试库，否则明确跳过；配置方法见 [PostgreSQL 开发验证](POSTGRESQL.md#开发验证)。可选浏览器集成测试使用 `node scripts/test-chat-ui.mjs`，依赖安装方法见 [流式问答说明](evals/STREAMING_CHAT.md)。

## 文献与运行数据

文献登记以 [corpus_catalog.json](config/corpus_catalog.json) 为准。最近一次文献同步记录为 [2026-09-22 更新](evals/CORPUS_UPDATE_20260922.md)：17 份启用 PDF、15,130 页，包括党史两卷、毛泽东选集、周恩来年谱、邓小平年谱三册、西行漫记和毛泽东年谱九卷。已撤下的林彪年谱、邓小平文选仍保留历史登记与研究记录。

《毛泽东选集》保留本地民间整合版，引用时区分版本、卷次和来源。PDF 只读处理；OCR 和自动抽取不等于人工核验，重要引文需回到原页。目录中 `ocr_pages` 可指定强制 OCR 页，`full_required` 表示整本 OCR。

`data/` 保存逐页文本、OCR、切片、报告和本地服务运行文件；业务与会话数据存于 PostgreSQL，向量存于 Qdrant。派生索引可以重建，主库、会话及人工复核记录需要单独备份。`tmp/` 为本地草稿和临时产物，不纳入版本控制。

## 代码目录

```text
app/history_agent/
├── cli.py                # 命令行入口
├── config.py             # 配置与服务连接目标
├── db.py / db_backend.py # PostgreSQL 模型与访问
├── corpus/               # 文献登记与扫描
├── extraction/           # PDF 文本提取、OCR、报告
├── processing/           # 清洗、篇章与切片
├── retrieval/            # PostgreSQL BM25、Qdrant、融合与 LlamaIndex 适配
├── research/             # 人物、事件、交集、组织任职与复核
├── answering/            # 统一研究 Workflow、计划、工具、证据、综合与交付
├── evaluation/           # 分层评测、协议、复核与比较
└── web/                  # FastAPI 与 static/ 单页会话界面
config/                   # 文献目录、人物别名、关系词表、Qdrant 配置
docs/                     # Git LFS 原始 PDF
evals/                    # 评测集、冻结标注与历史报告
scripts/                  # 服务管理、检查与离线复核辅助脚本
tests/                    # 单元与集成测试
```
