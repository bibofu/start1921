# Qdrant 独立服务

向量检索使用独立的 Qdrant 服务；主库、会话库和关键词索引使用 PostgreSQL。
向量写入 `data/qdrant-service/`，不读取客户端本地向量文件。

模型为 `BAAI/bge-small-zh-v1.5`，512 维，Cosine 距离。查询显式使用 `exact=True`，
保留文献、人物、年份、范围过滤和年标题优先排序。

## 启动与配置

本机使用官方 Qdrant `v1.19.2` Windows x64 程序。应用通过 `httpx` 调用服务 REST API，
embedding 使用 `fastembed==0.8.0`。程序位于 `data/qdrant-runtime/v1.19.2/qdrant.exe`，
仅监听本机。新机器可从
[官方发行页](https://github.com/qdrant/qdrant/releases/tag/v1.19.2) 下载
`qdrant-x86_64-pc-windows-msvc.zip` 并解压至上述目录。本次下载的 SHA-256 为
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

`config/qdrant.yaml` 配置本地监听、存储和快照目录。运行数据位于
`data/qdrant-service/`。管理命令为 `scripts/qdrant.ps1 start|status|stop`；停止前先
结束应用及索引写入任务。辅助脚本后台启动进程，不注册 Windows 服务；重启电脑后需
重新启动数据库和应用。

## 向量索引构建

```powershell
uv run start1921 index build-vector
```

该命令创建新的物理 collection，写入完成并核对精确计数后，原子切换
`history_chunks` alias。旧 collection 保留；构建失败不会切换 alias。

服务索引没有可由客户端直接读取的本地文件摘要。评测元数据不会把旧目录摘要冒充
当前服务索引摘要；严格的索引身份复现检查会标为尚未核验。

## 备份与恢复

向量数据以 `data/qdrant-service/snapshots/` 下的快照为准。恢复前停止应用和 Qdrant，
按 [Linux 部署](deploy/README.md)的流程还原快照。快照不包含 PostgreSQL 中的会话和
关键词索引，两者需分别备份。
