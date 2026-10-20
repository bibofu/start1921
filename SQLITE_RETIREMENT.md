# SQLite 退役记录（2026-10-20）

项目运行时已仅使用 PostgreSQL 和独立 Qdrant 服务，不再读取 SQLite。
现有数据库、索引和备份保留，没有重新生成 embedding，也没有更改分词、过滤、BM25、
向量精确检索和混合排序逻辑。

## 当前依赖和配置

- 主库必须设置 `HISTORY_AGENT_DATABASE_URL`，仅接受 PostgreSQL URL。
- 会话和关键词默认共用主库，也可分别设置 `HISTORY_AGENT_CONVERSATION_DATABASE_URL`
  和 `HISTORY_AGENT_KEYWORD_DATABASE_URL`。
- 向量必须设置 `HISTORY_AGENT_QDRANT_URL`。客户端通过 `httpx` 调用 Qdrant REST API，
  不安装 `qdrant-client`；FastEmbed 保持 `0.8.0`，模型保持 `BAAI/bge-small-zh-v1.5`。
- 删除 SQLite 兼容连接、DDL 转换、本地路径回退、关键词对照后端和旧数据迁移命令。
  旧迁移代码可从 Git 提交 `24509b7` 查看；当前程序不能直接打开旧数据库恢复运行。
- 业务测试使用显式 `HISTORY_AGENT_TEST_POSTGRES_URL` 下的随机隔离 schema；
  测试收集前屏蔽本机服务配置，测试完成后仅删除本次 schema。
  mypy 使用 JSON 缓存。

使用项目的 uv 安装流程：

```powershell
uv sync --all-extras --group dev --locked
.\scripts\postgres.ps1 start
.\scripts\qdrant.ps1 start
uv run start1921 serve
```

LlamaIndex 默认声明的 `aiosqlite` 用于本项目不使用的 SQL 存储功能。
项目通过 uv 的 [exclude-dependencies](https://docs.astral.sh/uv/reference/settings/#exclude-dependencies)
将其排除，锁文件和虚拟环境中均已移除。普通 `pip install` 不读取此配置，
应使用上述 uv 流程。新增导入隔离测试阻止重新引入 SQLite 或本地 Qdrant 客户端。
Python 自带的标准库文件无需卸载，应用不依赖其 SQLite 模块。

## 数据保留

旧主库 `data/history_agent.db`、会话库 `data/conversations.db`、
关键词库 `data/indexes/keyword_fts.db`、
旧向量库 `data/indexes/qdrant/collection/history_chunks/storage.sqlite` 均未改动。
四个文件的 SHA-256 与此前保存的基线一致。

`data/backups/` 下所有现有备份保留，包括主库/会话、关键词和 Qdrant 迁移备份。
历史迁移统计与冻结评测结果也保留。它们不参与当前运行；
之后新增的数据应从 PostgreSQL 与 Qdrant 服务另行备份。

## 本次简单验证

- 在全新进程中禁止导入 `sqlite3`、`_sqlite3`、`aiosqlite`、`pysqlite3`
  和 `qdrant_client`，应用、CLI、工作流和 embedding 正常加载。
- 读取主库和已有会话；当前登记 19 份文献、25 个人物、29,122 条历史事件，
  会话库保留 1 个会话和 18 条消息。
- 活动关键词索引和 Qdrant 服务各有 22,338 条记录。
  关键词、向量和混合检索各执行一次 Top-3 查询，全部成功，混合检索无降级。
- 首页及健康接口正常；就绪检查中主库、关键词、向量均通过。
- 受影响存储测试、HTTP 请求协议测试以及 LlamaIndex/回答适配测试通过；
  Ruff 和全部 92 个应用源文件的 mypy 检查通过。
  未运行大型检索评测或重新生成 Golden 标注。

本机明细保存在 `data/reports/sqlite-retirement-smoke.json`。
