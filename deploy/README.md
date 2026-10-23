# Linux 独立部署

这套配置在已有服务的 Linux 主机上运行独立的 start1921 Compose 项目。应用只映射
`127.0.0.1:18021`，由宿主 nginx 按域名反向代理；PostgreSQL 和 Qdrant 只有内部网络，
不映射宿主端口。应用另接出网网络，以调用 DeepSeek。Compose 不接管现有的
80、443 或 8080 端口，也不使用已有应用的数据卷。

## 镜像与目录

| 组件 | 固定版本 | 数据位置 |
| --- | --- | --- |
| 应用 | Python `3.12.15-slim-bookworm`，uv `0.13.3`；依赖取 `uv.lock` | `/opt/start1921/runtime/data` |
| PostgreSQL | `postgres:18.6-bookworm` | Compose 卷 `start1921_postgres` |
| Qdrant | `qdrant/qdrant:v1.19.2` | Compose 卷 `start1921_qdrant`、`start1921_qdrant_snapshots` |
| 证据 PDF | 与数据库对应的原始文件 | `/opt/start1921/runtime/docs`，容器只读 |
| 运行配置及密钥 | `/etc/start1921/start1921.env`，权限 `600` | 镜像外 |

代码目录示例为 `/opt/start1921`。Dockerfile 使用
`uv sync --frozen --extra app --extra vector --no-dev`，不安装 OCR。
依赖安装为 editable，并显式设置 `HISTORY_AGENT_PROJECT_ROOT=/app`，保持配置、
证据和模型路径一致。构建上下文采用白名单，不包含 `.env`、PDF、数据、缓存或 Git。
固定 tag 仍可能更新；上线时另外记录镜像 digest、代码 commit 和数据备份标识。

应用仅一个 Uvicorn worker，LLM 并发设为 2，内存上限为 1 GiB；PostgreSQL 为
256 MiB，Qdrant 为 512 MiB。总上限约 1.75 GiB，宿主还需为原有服务、操作系统、
文件缓存和构建预留空间。CPU 配额不是线程数；现有 embedding 实现仍按宿主可见
CPU 数选择最多 8 个线程。本部署不改检索或 Agent 逻辑。需要 OCR 或全量重新建索引时，
应在资源充足的离线环境完成，再迁移产物。

## 初次启动

以下命令在 Linux 服务器上执行，需要 Docker Engine、Compose v2 和足够磁盘空间。
代码及配置准备好以后先启动数据库，导入已有数据，再启动应用。

```bash
cd /opt/start1921
sudo install -d -m 700 /etc/start1921
sudo install -m 600 deploy/environment.example /etc/start1921/start1921.env
sudo install -d -o 10001 -g 10001 /opt/start1921/runtime/data
sudo install -d -m 755 /opt/start1921/runtime/docs
sudoedit /etc/start1921/start1921.env
```

填入三个不同的随机十六进制密钥（PostgreSQL、Qdrant、visitor token pepper，可分别运行
`openssl rand -hex 32`），及已有 DeepSeek API key。不要原样复制本地 `.env` 中指向
Windows 路径或 localhost 的数据库地址。Compose 强制使用本项目的数据库、Qdrant 和容器路径。若本地原来将主库、
会话库、关键词库分开，需先规划合并或调整 Compose 中三个连接地址，再分别迁移。
配置路径如有变化，需要同时修改 `--env-file` 参数和文件内的 `START1921_ENV_FILE`。

后续命令统一使用这个 shell 函数：

```bash
dc() {
  sudo docker compose --env-file /etc/start1921/start1921.env \
    -f /opt/start1921/deploy/compose.yaml "$@"
}
dc config --quiet
dc build app
dc up -d postgres qdrant
dc ps
```

`docker compose config` 不加 `--quiet` 会展开密钥，不要将其输出保存到日志或提交。
这里的 `postgres` 是 start1921 自己的服务名，不是宿主上其他 Compose 项目的数据库。

## 从已有工作区迁移

1. 迁移期间暂停源端写入，记录源代码版本、主库表数/记录数、Qdrant collection、
   alias 和 point 数，以及文件校验和。先保留完整可恢复备份。
2. 使用 PostgreSQL 18 的 `pg_dump -Fc --no-owner --no-acl` 生成逻辑备份。主库、
   会话和关键词位于同一库时导出一次即可；不要把 Windows PostgreSQL 数据目录直接
   挂到 Linux 容器。
3. 在目标新库恢复备份（以下路径替换为实际文件；命令只针对本 Compose 项目）：

   ```bash
   dc exec -T postgres pg_restore -U start1921 -d start1921 \
     --no-owner --no-acl --exit-on-error < /path/to/start1921.dump
   ```

4. Qdrant 使用其 snapshot API 创建并下载每个物理 collection 的快照；在目标同版本
   Qdrant 通过 `/collections/{collection}/snapshots/upload` 上传恢复。源端 alias
   需单独记录，再用 `/collections/aliases` 重建；collection snapshot 不代替 alias
   迁移。服务只有容器内部网络，可从应用容器执行 HTTP 请求或临时加入
   `start1921_backend` 网络的管理容器操作。密钥从受保护的环境读取，不放到 URL。
   若采用分批 scroll/upsert，保留原 collection 配置、point ID、向量、payload、
   payload index 和 alias，并校验点数及内容；不要对现有集合直接重建索引。
5. 同步 `data/processed/` 和 `data/models/` 到目标 `runtime/data/`，同步 `docs/` 中
   对应 PDF 到 `runtime/docs/`。其他确实需要的运行产物单独同步，避免复制旧数据库、
   Windows 二进制、历史临时文件及 `data/qdrant-service` 活跃存储。
   embedding 缓存在 `data/models/fastembed/`；Windows 缓存链接中的反斜杠不能直接
   用于 Linux。迁移包应解引用为普通文件，或转换成可解析的 POSIX 相对链接；
   `files_metadata.json` 中的路径键也需在部署副本中转换为 `/`。不改写源缓存。
   缓存完整后可设置 `HF_HUB_OFFLINE=1` 并验证一次向量检索；缺失模型且未开启
   离线模式时，首个向量查询会尝试下载模型。
6. 确认目标数据归 UID/GID `10001:10001` 且可写、PDF 可读；只对本部署数据目录调整
   权限。比较数据库表数/记录数、向量 point 数、alias 及关键产物校验和，然后启动应用。

```bash
dc up -d app
dc ps
curl --fail http://127.0.0.1:18021/api/health
curl --fail http://127.0.0.1:18021/api/ready
```

`/api/health` 的 `database_ready`、`indexes.keyword`、`indexes.vector` 应全部为
`true`。容器健康检查核对这三项，HTTP 200 本身不表示检索可用。`/api/ready`
会实际执行向量检索；上线时还需确认其 `components.vector=true`，并做人物查询、
带引用的问答、SSE 流式回答及会话读写检查。该接口允许关键词或向量其一就绪，
所以不能只看它的 HTTP 状态。模型第一次加载需要额外时间与内存。

## 域名、访问与 TLS

将 `start1921.chat` 的 A 记录指向部署主机。仅在配置了可用 IPv6 时发布 AAAA 记录。
首次签发证书前，先创建仅监听 80 的独立 vhost，将 `/.well-known/acme-challenge/`
映射到 `/var/www/start1921-acme`，其他路径暂返 503。用 Certbot webroot 模式签发
证书并配置续期 reload；该流程不需要停止现有 nginx。

证书准备好后，采用
[nginx.conf.example](nginx.conf.example) 中的 HTTPS 及重定向配置；
先 `nginx -t` 再 reload，保留现有服务的 vhost 和默认站点。示例依赖已经存在的
证书，不会自动创建证书。SSE 必须关闭代理缓冲。

网站页面和 API 公开访问，无需用户名和密码；nginx 显式设置 `auth_basic off`。
应用端口保持 `127.0.0.1:18021`，由 nginx 提供 HTTPS 入口。

### 匿名 workspace 与配额

不做账号登录。应用首次访问时签发 `__Host-start1921_vid` HttpOnly Cookie，
会话、消息和配额按 `visitor_id` 隔离；跨访客访问统一返回 404。生产环境必须设置：

- `START1921_VISITOR_TOKEN_PEPPER`：随机十六进制密钥，用于 HMAC token 和 IP hash；
- `HISTORY_AGENT_VISITOR_COOKIE_NAME=__Host-start1921_vid`；
- `HISTORY_AGENT_VISITOR_COOKIE_SECURE=true`；
- `HISTORY_AGENT_CSRF_ENABLED=true`；
- `HISTORY_AGENT_QUOTA_ENABLED=true` 及每日问题/token 限额。

Cookie 丢失、换浏览器或清站点数据会得到新的空 workspace，旧会话仍在库中但应用内
不可见；页面提供“导出全部会话”。不存在账号找回或跨设备同步。nginx 示例已加
HSTS/CSP；生产建议在 `http{}` 定义 `limit_req_zone`/`limit_conn_zone`，对
`/api/visitor` 和 `/api/questions` 单独限流。应用不会信任任意代理头，Dockerfile
只信任私有网段转发的 `X-Forwarded-For`。

## 运维与升级

```bash
dc ps
dc logs --tail 100 app
sudo docker stats --no-stream
```

容器日志自动轮换。外部监控应关注 unhealthy、OOM/restart、磁盘容量、TLS 到期、
模型调用失败及宿主原有服务状态。Docker 健康检查只标记 unhealthy，不会自动重启；
`restart: unless-stopped` 在进程退出或宿主重启时生效。

每次升级先备份主库、Qdrant 快照及 alias、`runtime/data` 中需保留的产物、
PDF 和受保护的环境配置。把应用镜像标为代码 commit，记录实际镜像 digest。
依赖或数据 schema 变化需要单独验证恢复路径。普通应用升级：

```bash
dc build app
dc up -d --no-deps app
curl --fail http://127.0.0.1:18021/api/health
curl --fail http://127.0.0.1:18021/api/ready
```

失败时将 `START1921_APP_IMAGE` 改回已保留的旧镜像 tag，再运行
`dc up -d --no-deps --no-build app`。数据格式已改变时，先恢复兼容的数据备份。
不要运行 `docker compose down -v`；它会删除本项目数据库与向量卷。

## 2026-10-20 部署记录

服务已部署到 `118.193.34.72`，入口为 <https://start1921.chat>。Compose 项目、
目录、端口与上文一致，应用镜像为 `start1921:20261020`。发布验证记录保存在服务器
`/opt/start1921/transfer/deployment-verification.json`，记录代码 commit、镜像 ID
和数据 manifest 校验和；迁移包及逐项验证结果也位于该受限目录。

本次迁移 17 份 PDF、OCR/页面/切片结果、离线嵌入模型和 PostgreSQL 的 30 张表。
关键词与向量记录均为 22,338 条，向量检索别名为 `history_chunks`。
数据库恢复后的逐表计数与导出 manifest 一致；本地会话内容未迁移。

上线验证已通过实际关键词及向量检索、1949 年毛泽东时间线、DeepSeek 普通问答、
带引用的 SSE 回答、会话保存/读取/删除。两次问答分别返回 2 和 3 条引用，
测试会话已删除。这些是部署连通性检查，不代替 Golden 集质量验收或负载测试。
验证期间三个容器均无 OOM 或重启。

根据访问需求，同日取消网站和 API 的 Basic Auth，无需用户名和密码。
HTTP 跳转 HTTPS，页面、静态文件和 API 均已通过无认证访问验证。
证书由 Certbot 自动续期，成功后 reload nginx。
此次访问方式变更的验证记录保存在 `/opt/start1921/transfer/public-access-verification.json`；
首次部署记录中的认证检查保留为历史结果。
原有 `limitupagent.xyz`、`limituplab.tech` 的 nginx 配置哈希保持不变，部署后仍返回 200。

参考：[uv Docker 指南](https://docs.astral.sh/uv/guides/integration/docker/)、
[PostgreSQL 官方镜像的 PGDATA 说明](https://hub.docker.com/_/postgres)、
[Qdrant 快照文档](https://qdrant.tech/documentation/database-tutorials/create-snapshot/)。
