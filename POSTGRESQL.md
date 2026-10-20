# PostgreSQL 主库与会话库

本项目支持将文献、人物、事件、证据、关系、复核记录和聊天记录放入
PostgreSQL。主库迁移命令不重建或修改关键词和向量索引。
关键词索引另行通过 [关键词迁移流程](KEYWORD_POSTGRESQL.md) 使用 PostgreSQL；
向量检索使用 [Qdrant 独立服务](QDRANT_SERVICE.md)，保留原有 embedding 与向量数据。

## 配置与启动

安装项目依赖后，在被 Git 忽略的 `.env` 中设置：

```dotenv
HISTORY_AGENT_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

密码中的特殊字符需要 URL 编码。会话默认与主库使用同一数据库。
`HISTORY_AGENT_CONVERSATION_DATABASE_URL` 可指定独立运行地址，但当前一次性迁移命令
要求主库和会话共用一个目标数据库，以便在同一事务内导入并验证。
公开配置与健康接口只显示后端类型，不输出连接凭据。

当前工作区使用仅监听 `127.0.0.1` 的本地 PostgreSQL 实例，运行文件位于
`data/postgres-runtime/pgsql`，集群目录为 `data/postgres`。它不注册 Windows 服务：

```powershell
.\scripts\postgres.ps1 start
uv run start1921 serve
```

数据库管理：

```powershell
.\scripts\postgres.ps1 status
# 先停止问答服务，再停止数据库：
.\scripts\postgres.ps1 stop
```

新机器需自行安装 PostgreSQL，或从
[PostgreSQL 官方 Windows 下载页](https://www.postgresql.org/download/windows/)
进入 EDB 下载二进制包。上述辅助脚本要求二进制解压至指定目录，并已使用 `initdb`
初始化集群；也可以使用已有 PostgreSQL 服务，只需配置连接 URL。
数据库角色应拥有目标数据库及业务表的建表、读写和迁移权限。

## 保留现有数据的迁移

1. 停止问答服务及所有写入主库、会话库的 CLI 任务。
2. 创建空的目标 PostgreSQL 数据库，配置 `.env`，暂不启动应用。
3. 运行迁移：

```powershell
uv run start1921 database migrate-postgres `
  --backup-dir data/backups `
  --report data/reports/postgres-migration.json
```

默认源为原 `HISTORY_AGENT_DATABASE_PATH` 与 `data/conversations.db`；
可用 `--source-database`、`--source-conversations` 指定备份文件。

命令通过 SQLite backup API 创建一致快照，检查完整性及外键，再导入 PostgreSQL。
原 SQLite 文件保留。所有业务表必须为空；只要一张表已有记录，导入就会拒绝，
不会覆盖或清空。主库和会话数据在同一事务中写入，任一失败会回滚。
表结构初始化独立提交，失败时目标可能保留空表，备份也会保留。

逐表校验包括记录数和全部字段的 SHA-256 摘要；摘要不依赖两种数据库的排序规则。
人物、事件及证据 ID、页码、日期精度、JSON 字符串和浮点值均保留。
部分原始 PDF 标题、作者元数据含有 `U+0000`，PostgreSQL `TEXT` 不支持该字符；
这两个不参与检索的元数据字段使用 UTF-8 `BYTEA` 保存，应用读取时恢复原字符串，
不会删除空字符或改变原值。PostgreSQL schema 版本为 7，SQLite 兼容 schema 仍为 6。
自增序列按已用 ID 和 SQLite 序列高水位恢复，避免下一次写入发生主键冲突。
报告只记录路径、表名、数量与摘要，不包含密码或聊天正文。

可在恢复写入前重复只读验证：

```powershell
uv run start1921 database verify-postgres
```

恢复写入后，两库会自然产生差异，因此全量相等验证应以迁移完成时的状态为准。
不要重复导入到已开始使用的 PostgreSQL 数据库。

## 功能验证与回退

启动后检查 `/api/health` 的数据库后端及 `/api/ready` 的实际主库、关键词和向量检索状态。
还应比较人物时间线、人物交集、组织关系查询及原会话恢复，并验证新会话写入和清空。
迁移只改变存储实现，检索参数、模型和回答策略保持原有配置。

若尚未在 PostgreSQL 产生新数据，可停止应用、清空两个 PostgreSQL URL 配置并重启，
恢复使用保留的 SQLite 文件。若 PostgreSQL 已有新写入，必须先导出并合并这些数据，
直接切回旧文件会看不到迁移后的新记录。

集群数据位于本机，应另行用 `pg_dump` 做持续备份；迁移时的 SQLite 备份不包含后续写入。

## 开发验证

SQLite 后端保留用于既有隔离测试。真实 PostgreSQL 用例通过环境变量
`HISTORY_AGENT_TEST_POSTGRES_URL` 指向测试数据库：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_db_backend.py tests/test_postgres_migration.py
```

真实测试会创建并清理随机命名的独立 schema，角色需要相应权限；不要使用只读角色。
测试覆盖事务回滚、可延迟外键、64 位数值、参数绑定、自增序列、非空目标拒绝、
全字段校验、会话恢复和裁剪。未设置测试 URL 时，真实 PostgreSQL 用例明确跳过。

## 本地迁移验收记录（2026-10-20）

当前工作区已切换至本机 PostgreSQL 18.6，地址为 `127.0.0.1:55432/start1921`。
主库和会话库共 25 张业务表、153,479 条记录，迁移前后逐表数量和全字段摘要一致。
原有 1 个会话、18 条消息完整恢复。

- 原 `data/history_agent.db`、`data/conversations.db` 的 SHA-256 与迁移前一致。
- 关键词索引及 Qdrant 的存储文件、元数据文件 SHA-256 与迁移前一致。
- 人物时间线、日期筛选、分页、交集、组织关系、复核队列和会话等 76 项业务对照全部一致。
- 设置独立 PostgreSQL 测试库后运行 `scripts/check.ps1`：Ruff、mypy、915 项 Python 测试、
  JavaScript 语法检查及 3 项前端流式测试全部通过，无跳过用例。
- 本地首页返回 200，`/api/ready` 的主库、关键词索引、向量索引均正常。
  真实模型流式问答完成，返回 12 条引用；新会话写入、回读和清空通过。
  清理临时测试会话后再次进行只读全量校验，25 张表仍与原 SQLite 数据一致。

迁移快照保存在 `data/backups/sqlite-to-postgres-20261020T060148Z-7c40a035/`，
其中包括两份 SQLite 一致备份及切换前的配置备份。配置备份含凭据，应仅在本机保管。
原数据库文件也继续保留。验收报告位于：

- `data/reports/postgres-migration.json`：导入和全字段校验。
- `data/reports/postgres-final-verification.json`：功能测试结束后的全量复核。
- `data/reports/postgres-behavior.json`：76 项业务对照。
- `data/reports/postgres-http.json`：实际服务与问答验证。
- `data/reports/postgres-preservation.json`：原数据库和索引文件指纹复核。
