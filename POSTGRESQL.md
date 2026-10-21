# PostgreSQL 主库与会话库

主库、会话库和[关键词索引](KEYWORD_POSTGRESQL.md)现在只支持 PostgreSQL。
向量检索使用 [Qdrant 独立服务](QDRANT_SERVICE.md)。当前代码已移除 SQLite 驱动导入、
本地数据库兼容分支和旧迁移命令；原数据库与迁移备份已于 2026-10-21 清理，
详见文末[清理记录](#2026-10-21-sqlite-资产清理)。

## 配置与启动

安装项目依赖后，在被 Git 忽略的 `.env` 中设置：

```dotenv
HISTORY_AGENT_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

密码中的特殊字符需要 URL 编码。会话默认与主库使用同一数据库；
`HISTORY_AGENT_CONVERSATION_DATABASE_URL` 可指定独立的 PostgreSQL 数据库。
关键词默认也使用主库地址，可通过 `HISTORY_AGENT_KEYWORD_DATABASE_URL` 单独配置。
缺少所需连接配置时会报错，不会回退到本地数据库文件。
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

新机器需自行安装 PostgreSQL，或使用已有 PostgreSQL 服务并配置连接 URL。
上述辅助脚本要求二进制位于指定目录、集群已经初始化。
数据库角色应拥有目标数据库及业务表的建表、读写和 schema 升级权限。

## 已完成的迁移与备份

主库和会话库已经迁入 PostgreSQL。旧迁移程序曾在同一事务中导入数据，并比较逐表
记录数及全部字段摘要；人物、事件、证据 ID、日期精度、JSON 字符串和浮点值均保留。
原始 PDF 标题、作者元数据可能包含 `U+0000`，这两个字段使用 UTF-8 `BYTEA` 保存，
读取时恢复原字符串，不删除空字符。当前 PostgreSQL schema 版本为 7。

一次性迁移和旧库对照校验命令已经从当前 CLI 删除，不能在当前版本执行。
若需审计原迁移过程，可查看 Git 提交 `24509b7` 中的历史代码和下方保留的报告。
原 SQLite 文件与一致备份已于 2026-10-21 删除；清空连接配置仍不会回退到本地文件。
历史数据以 `data/deployment/20261020/postgres.dump` 归档，向量数据以
`data/qdrant-service/snapshots/` 下的同一份快照归档，可按
[Linux 部署](deploy/README.md)的恢复流程还原。不要把归档直接当作当前数据，
因为它不包含迁移后新增的会话记录。

当前数据库应持续使用 PostgreSQL 备份工具（如 `pg_dump`）备份；覆盖范围应包括
主库、会话及关键词表。功能检查可使用 `/api/health` 和 `/api/ready`，再做一次
人物或检索查询及会话读写检查。无需重新运行历史迁移对照。

## 开发验证

测试不再使用 SQLite。需要真实数据库的用例通过显式环境变量
`HISTORY_AGENT_TEST_POSTGRES_URL` 连接独立 PostgreSQL 测试数据库：

```powershell
$env:HISTORY_AGENT_TEST_POSTGRES_URL = "postgresql://测试用户:密码@127.0.0.1:55432/start1921_test"
.\.venv\Scripts\python.exe -m pytest tests/test_db_backend.py tests/test_context.py
```

公共 fixture 为每个数据库测试创建随机 schema，结束后仅清理该 schema。
测试角色需要建表和创建、删除 schema 的权限。未设置测试 URL 时，真实 PostgreSQL
用例明确跳过。普通单元测试使用不可连接的占位 URL，避免误读本机 `.env` 中的生产连接。
覆盖内容包括事务回滚、外键、64 位数值、参数绑定、元数据保存与会话恢复。

`scripts/check.ps1` 使用 mypy 的 JSON 文件缓存（`--no-sqlite-cache`），
`pyproject.toml` 同时设置 `sqlite_cache = false`。缓存目录可随时删除，检查时会按需重建。

## 本地迁移验收记录（2026-10-20）

以下记录对应主库、会话库首次迁移时的验收，不是本次依赖清理重新执行的结果。

当时工作区切换至本机 PostgreSQL 18.6，地址为 `127.0.0.1:55432/start1921`。
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

迁移快照原保存在 `data/backups/sqlite-to-postgres-20261020T060148Z-7c40a035/`，
其中包括两份 SQLite 一致备份及切换前的配置备份；该目录已于 2026-10-21 随 SQLite
清理删除，其中配置备份曾含凭据。原数据库文件同样已删除。验收报告保留在：

- `data/reports/postgres-migration.json`：导入和全字段校验。
- `data/reports/postgres-final-verification.json`：功能测试结束后的全量复核。
- `data/reports/postgres-behavior.json`：76 项业务对照。
- `data/reports/postgres-http.json`：实际服务与问答验证。
- `data/reports/postgres-preservation.json`：原数据库和索引文件指纹复核。
- `data/reports/postgres-source-hashes.json`：被清理 SQLite 文件的原始指纹。

## 2026-10-21 SQLite 资产清理

删除前置条件已核验：`data/deployment/20261020/deployment-verification.json` 记录线上
服务（镜像 `start1921:20261020`）关键词表与 Qdrant 均为 22,338 条，30 张表计数与
数据 manifest 一致；同目录保留 `postgres.dump`（约 143 MB）作为数据库恢复归档。
向量快照在同一轮第二批清理中只保留服务目录内的一份，见下文。

| 已删除 | 清理前大小 | 内容 |
| --- | ---: | --- |
| `data/history_agent.db` | 81.5 MB | 旧主库，24 张表 |
| `data/conversations.db` | 0.1 MB | 旧会话库，1 个会话、18 条消息 |
| `data/indexes/keyword_fts.db` | 208.3 MB | 旧 FTS5 关键词索引 |
| `data/indexes/qdrant/collection/history_chunks/storage.sqlite` | 175.9 MB | 旧本地向量存储 |
| `data/backups/` | 1,524.2 MB | 6 个迁移备份，含两份 SQLite 一致备份与配置备份 |
| `data/postgres-runtime/behavior-source/` | 81.6 MB | 迁移对照用旧库快照 |
| `tmp/keyword-evaluation-tests-20261020-*` | 0.9 MB | 迁移评测临时索引目录 |
| `.mypy_cache/`、`data/mypy-cache/`、`data/mypy-cache-qdrant-service/` | 206.6 MB | mypy 缓存（非业务数据） |
| `data/sqlite_retirement_smoke.py` | 4 KB | 一次性退役校验脚本，已由 `tests/test_storage_dependencies.py` 覆盖 |
| `data/reports/keyword-migration-v1/**/legacy.sqlite` | 80 KB | 两个合成语料夹具；结论 JSON 保留 |

合计回收约 2.28 GB。删除前已留痕：

- 六个数据库文件的字节数与 SHA-256 写入
  `data/archive/20261021/sqlite-deletion-manifest.json`。
- 本地 1 个会话、18 条消息导出为 `data/archive/20261021/local-conversations.json`
  （部署时按设计未迁移本地会话）。
- 文件名、大小与历史指纹仍可在 `data/reports/postgres-source-hashes.json` 和
  `data/reports/postgres-preservation.json` 中核对。

保留的迁移评测 JSON（`data/reports/keyword-migration-v1/`，约 327 MB）与验收报告
未删除；它们只读，不参与运行。上述两个 `data/archive/` 归档位于被 Git 忽略的
`data/` 下，不随仓库分发。需要重放旧数据时以 `postgres.dump` 和
`data/qdrant-service/snapshots/` 下的快照为准，不能依赖已删除的 SQLite 文件。

依赖层只剩一处 uv 专属处理：`llama-index-core` 声明了 `aiosqlite`，项目通过
`[tool.uv] exclude-dependencies` 排除，`uv sync` 后不会安装；该字段不识别，
用 pip 安装的环境需自行确认 `aiosqlite` 未被使用。

## 2026-10-21 冗余资产清理（第二批）

同日完成的只读盘点随后删除了 A+B 两档共 3,434 MB 的冗余产物，清单与哈希保存在
`data/archive/20261021-redundancy/deletion-manifest.json`。

| 类别 | 回收 | 内容 |
| --- | ---: | --- |
| A 明确冗余 | 2,866 MB | 10 个 `*.partial.json` 采集检查点（均已存在完整件）、PostgreSQL/Qdrant 安装包与分片 494 MB、`data/uv-cache` 614 MB、部署上传包 `runtime.tar.gz` 758 MB、与 service 目录逐字节相同的 `qdrant.snapshot` 493 MB、`data/test-work` 与 `tmp/pytest-*` 49 MB |
| B 无引用旧报告 | 568 MB | `eval_development20_20261011` 的非 stable 运行（capture/report/legacy13_report）、`live_report_initial`、`browser_roundtrip_report`、`offline_rescored_report` |

B 档删除只删大文件，对应的 `*.summary.json`、`*.md` 与 `stable/` 目录保留，文档引用的
`stable/capture.json`、`eval_pilot_v2/live_capture.json`、`eval_expansion_20260923/top*_capture.json`
和 `keyword-migration-v1/*.json` 均未改动。向量快照因此只在
`data/qdrant-service/snapshots/history_chunks_import_004028549da44ef6af8e386ae87509c4/`
保留一份，其 SHA-256 与删除的部署副本一致（`F84479A6A92BCD62C53F84DCDA3FFA3016BD626A02400CB442B877807CDD5119`）。
