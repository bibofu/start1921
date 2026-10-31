# PostgreSQL 主库、会话库与关键词索引

主库、会话库和[关键词索引](KEYWORD_POSTGRESQL.md)只使用 PostgreSQL。向量检索使用
[Qdrant 独立服务](QDRANT_SERVICE.md)。缺少连接配置时直接报错，不会回退到本地文件
或嵌入式数据库。

## 配置与启动

安装项目依赖后，在被 Git 忽略的 `.env` 中设置：

```dotenv
HISTORY_AGENT_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

密码中的特殊字符需要 URL 编码。会话默认与主库使用同一数据库；
`HISTORY_AGENT_CONVERSATION_DATABASE_URL` 可指定独立的 PostgreSQL 数据库。
关键词默认也使用主库地址，可通过 `HISTORY_AGENT_KEYWORD_DATABASE_URL` 单独配置。
公开配置与健康接口只显示后端类型，不输出连接凭据。

当前工作区使用仅监听 `127.0.0.1` 的本地 PostgreSQL 实例，运行文件位于
`data/postgres-runtime/pgsql`，集群目录为 `data/postgres`。它不注册 Windows 服务：

```powershell
.\scripts\postgres.ps1 start
.\scripts\qdrant.ps1 start
uv run start1921 serve
```

数据库管理：

```powershell
.\scripts\postgres.ps1 status
# 先停止问答服务，再停止数据库：
.\scripts\postgres.ps1 stop
```

新机器需自行安装 PostgreSQL，或使用已有服务并配置连接 URL。上述辅助脚本要求
二进制位于指定目录、集群已经初始化。数据库角色应拥有目标数据库及业务表的建表、
读写和 schema 升级权限。

## Schema 与备份

当前 PostgreSQL schema 版本为 7。原始 PDF 标题、作者元数据可能包含 `U+0000`，
这两个字段使用 UTF-8 `BYTEA` 保存，读取时恢复原字符串，不删除空字符。

当前数据库应持续使用 `pg_dump` 备份，覆盖主库、会话及关键词表；Qdrant 向量数据
另按 [快照流程](QDRANT_SERVICE.md)备份。`data/` 下的派生索引可以重建，主库、会话和
人工复核记录需要单独备份。

归档目录 `data/deployment/20261020/postgres.dump` 与 Qdrant 快照只用于恢复部署，
不包含之后新增的会话记录，不能当作当前数据。

功能检查可使用 `/api/health` 和 `/api/ready`，再做一次人物或检索查询及会话读写检查。

## 开发验证

需要真实数据库的用例通过显式环境变量 `HISTORY_AGENT_TEST_POSTGRES_URL` 连接独立的
PostgreSQL 测试数据库：

```powershell
$env:HISTORY_AGENT_TEST_POSTGRES_URL = "postgresql://测试用户:密码@127.0.0.1:55432/start1921_test"
.\.venv\Scripts\python.exe -m pytest tests/test_db_backend.py tests/test_context.py
```

公共 fixture 为每个数据库测试创建随机 schema，结束后只清理该 schema。测试角色需要
建表以及创建、删除 schema 的权限。未设置测试 URL 时，真实 PostgreSQL 用例明确跳过；
普通单元测试使用不可连接的占位 URL，避免误读本机 `.env` 中的生产连接。覆盖内容包括
事务回滚、外键、64 位数值、参数绑定、元数据保存与会话恢复。

`scripts/check.ps1` 运行 Ruff、mypy 和 pytest。mypy 缓存写入 `data/mypy-cache`，
可随时删除并在下次检查时重建；Ruff 使用 `--no-cache`。
