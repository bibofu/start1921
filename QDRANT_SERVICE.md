# Qdrant 独立服务

本机向量存储从 Python Qdrant 本地模式迁移到 Qdrant Server。
主库、会话库和关键词索引继续使用 PostgreSQL；向量使用独立服务自己的存储目录，
不再读取旧 Qdrant 的 `storage.sqlite`。

模型仍为 `BAAI/bge-small-zh-v1.5`，512 维，Cosine 距离。
迁移直接复制已有 point ID、向量和 payload，不重新生成 embedding。
查询显式使用 `exact=True`，保留原有文献、人物、年份、范围过滤和年标题优先排序；
混合检索融合及回答逻辑不变。服务与 Python 本地实现的浮点计算可能有微小差异。

## 启动与配置

本机使用官方 Qdrant `v1.19.2` Windows x64 程序，客户端版本为 `1.19.0`。
程序位于 `data/qdrant-runtime/v1.19.2/qdrant.exe`，仅监听本机。
新机器可从 [官方发行页](https://github.com/qdrant/qdrant/releases/tag/v1.19.2)
下载 `qdrant-x86_64-pc-windows-msvc.zip` 并解压至上述目录。
本次下载的 SHA-256 为
`7d86596f16c6e85d45a50312f5e16ccb51e059b62e3d7308110cb65b4c799a4d`。

```powershell
.\scripts\postgres.ps1 start
.\scripts\qdrant.ps1 start
uv run start1921 serve
```

在被 Git 忽略的 `.env` 中配置：

```dotenv
HISTORY_AGENT_QDRANT_URL=http://127.0.0.1:6333
HISTORY_AGENT_QDRANT_TIMEOUT_SECONDS=30
# 连接启用鉴权的服务时另外设置 HISTORY_AGENT_QDRANT_API_KEY
```

`config/qdrant.yaml` 配置本地监听、存储和快照目录。
运行数据位于 `data/qdrant-service/`，不要与旧的 `data/indexes/qdrant/` 混用。
管理命令为 `scripts/qdrant.ps1 start|status|stop`；停止前先结束应用及索引写入任务。
辅助脚本后台启动进程，不注册 Windows 服务；重启电脑后需重新启动数据库和应用。

## 迁移与后续构建

先停止本地索引构建任务，备份整个旧 Qdrant 目录和对应构建报告；
迁移命令要求显式传入备份目录，保留源数据：

```powershell
uv run start1921 index migrate-qdrant-service `
  --source-index data/backups/某次备份/qdrant `
  --source-report data/backups/某次备份/source_vector_report.json `
  --report data/reports/qdrant-service-migration.json
```

数据分批复制到新的物理 collection。精确计数以及少量边界样本通过后，
原子切换 `history_chunks` alias；旧 collection 和旧本地索引均保留。
若导入未完成，服务 alias 不切换，失败的新 collection 留作排查。
后续 `index build-vector` 也创建新 collection，并在成功后切换 alias。

服务索引不再有可由客户端直接读取的本地文件摘要。评测元数据不会将旧目录的摘要
冒充当前服务索引摘要；严格的索引身份复现检查会标为尚未核验。
本阶段仅做数量、样本、少量检索对照及服务可用性检查，不进行完整质量评测。

## SQLite 退役边界

配置四项服务连接后，业务数据读写和检索使用 PostgreSQL 与 Qdrant Server。
SQLite 迁移工具、本地兼容分支、部分测试和开发缓存仍保留；
部分公共模块也仍导入 `sqlite3`。这些是下一步清理范围，
本次不宣称项目代码和开发环境已经完全不依赖 SQLite。
旧数据库与本地向量索引保留为备份，不能将删除文件等同于移除代码依赖。

## 本机迁移记录（2026-10-20）

- 已复制 17 份文献对应的 22,338 个点，源数量、复制数量和服务精确计数一致。
- 首尾 6 个样本的 ID、payload 相同；归一化向量的最大分量差约 `4.62e-9`。
  未调用 embedding 重建。
- 3 条向量查询和 1 条混合查询的 Top-10 顺序及非分数字段相同；
  公开分数或嵌套 `vector_score` 的最大差约 `1e-6`，来自不同实现的浮点计算。
  对照检查允许 `1.1e-6` 的浮点误差，其他字段严格比较。
- 服务查询阶段临时禁止 `sqlite3.connect` 后，上述查询仍全部成功。
- 首页返回 200，主库、会话库、关键词为 PostgreSQL，向量后端为 `qdrant-service`，
  `/api/ready` 三个组件均正常。原本地索引的完整目录指纹未变。
- 32 项针对性测试及相关 Ruff/mypy 检查通过；未运行大型检索评测或全套测试。

一致备份与切换前配置位于 `data/backups/qdrant-to-service-20261020T065622Z/`。
配置备份含凭据，仅留本机。服务当前物理 collection 为
`history_chunks_import_004028549da44ef6af8e386ae87509c4`，
通过 `history_chunks` alias 提供查询。

本地报告：`data/reports/qdrant-service-backup.json`、
`qdrant-service-migration.json`、`qdrant-service-smoke.json` 和 `qdrant-service-http.json`。
最初对照把嵌套向量分数也要求精确相等，发现 `1e-6` 差异；定位后仅调整比较容差，
没有修改模型、数据或检索算法，初始记录保留在 `qdrant-service-smoke-initial.json`。
