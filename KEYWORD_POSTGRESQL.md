# PostgreSQL 关键词索引

> 2026-10-31 更新：生产关键词 tokenizer 已从 CJK 二元字 bigram 切换为 jieba search mode，
> 索引版本改为 `postgresql-bm25-jieba-v1`。本文以下内容记录 2026-10-20 从 SQLite FTS5
> 迁移到 PostgreSQL 时的历史契约，不再代表当前切词口径；当前实现见
> [RAG 实现说明 §5](RAG-IMPL.md#5-关键词索引postgresql--bm25) 和
> [关键词分词 A/B](evals/KEYWORD_TOKENIZER_AB_20261031.md)。

关键词索引现在只支持 PostgreSQL，可以与主库共用，也可以使用独立数据库。
原 SQLite 兼容实现和一次性迁移命令已移除，旧数据与迁移备份已于 2026-10-21 清理
（见 [PostgreSQL 清理记录](POSTGRESQL.md#2026-10-21-sqlite-资产清理)）。
此变更只迁移关键词索引存储，不改变文献切分、embedding 模型、Qdrant、
混合检索融合、重排、上下文选择或回答提示词。

## 保持的检索契约

- 继续使用原中文二元切词、英文/数字词项、年份扩展和查询停用词。
- 保留原 `unicode61` 对预分词结果中连字符、下划线、小数点的拆词效果；
  多词查询项仍按连续词位匹配短语。PostgreSQL 构建和检索不调用 SQLite 词法器。
- 显式实现原 SQLite FTS5 的 BM25：`k1=1.2`、`b=0.75`，
  非正 IDF 使用 `1e-6`。语料数量、平均长度和词项/短语文档频率均来自完整索引，
  不随人物、时间、文献等过滤条件重新计算。
- 保留时间线年谱和观点选集的 `4.0` 加权，以及作者匹配的 `2.0` 加权。
  按原始分数排序，同分按原 FTS 行号；对外分数继续保留六位小数。
- 文献、人物、年份及范围、章节、资料范围过滤保持原语义。
  章节检索按字面子串处理 `%`、`_`、反斜杠，并仅折叠 ASCII 大小写。
- 不使用 PostgreSQL `ts_rank` 替代 BM25。定义依据为
  [SQLite FTS5 BM25 文档](https://www.sqlite.org/fts5.html#the_bm25_function)。

完整元数据和预分词文本使用 UTF-8 字节保存，避免 PostgreSQL TEXT 对空字符的限制。
倒排表保存词项、原 FTS 行号和词位数组；原元数据行号也保留用于完整性核验。

## 配置与构建

关键词默认使用 `HISTORY_AGENT_DATABASE_URL` 指定的 PostgreSQL 数据库。
需要单独配置时，在被 Git 忽略的 `.env` 中设置：

```dotenv
HISTORY_AGENT_KEYWORD_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

公开配置、运行记录与索引报告只显示后端及 `postgresql:keyword`，不记录 URL。
密码中的特殊字符应进行 URL 编码。关键词 URL 和主库 URL 均缺失时会报错，
不会读取旧的本地索引。修改服务连接后需重启应用。

后续重新构建使用：

```powershell
uv run start1921 index build-keyword
```

该命令直接从已有 chunk JSONL 创建新的 PostgreSQL 索引版本，不需要旧 SQLite
索引或词法器。构建成功后在事务中切换活动版本；旧 PostgreSQL 版本保留，
尚未实现自动清理策略。数据库备份应覆盖关键词表，可使用 `pg_dump`。

## 已完成的迁移与历史存档

旧迁移曾创建一致快照并导入全部元数据、预分词原文、原始行号、文档长度及词位。
全部字段、词位摘要和行数验证通过后才发布 PostgreSQL 活动版本。
原数据库文件和迁移备份已于 2026-10-21 删除，下面的数量与摘要记录对应当时已完成的迁移。

一次性迁移、旧库校验命令及 SQLite 回退已经从当前代码删除。
原迁移工具可在 Git 提交 `24509b7` 中查阅；当前版本不能执行旧迁移命令，
清空 PostgreSQL 配置也不会启用旧索引。历史报告可直接作为 JSON 阅读和比较。

历史文件 SHA-256、包含文件名的索引摘要和跨数据库逻辑摘要是不同身份，不能混用。
一致备份可能改变旧数据库文件头，因此文件哈希不同不一定代表逻辑内容变化。
这些说明只用于解释既有迁移报告，当前构建和检索不再打开历史数据库。

## 评测边界

迁移评测协议在实现前冻结于
[protocol_v1.json](evals/keyword_migration/protocol_v1.json)。
原实现、索引、标注、过滤组合和多个 K 值固定，基线来自原代码快照，
不通过新实现生成参考结果。

完整结果顺序、分数、字段以及混合检索阶段的一致性用于判断存储兼容性。
有人工批准的证据组用于计算关键证据 Recall；没有充分候选标签的真实题目，
Precision、MRR、nDCG 保留不可评及原因。独立受控语料的完整标签指标单独报告，
不与真实历史题合并，也不称为正式 Golden 成绩。10 道保留题不用于此次调试。

本地确定性端到端检查覆盖查询路由、检索轨迹、证据选择、摘录回答、引用与拒答。
禁用模型的运行不代表真实模型答案质量或实际生成提示词上下文评测，
新模型答案不能沿用旧人工评审结果。

开发测试通过显式 `HISTORY_AGENT_TEST_POSTGRES_URL` 使用独立 PostgreSQL 数据库
及随机 schema；未配置时数据库用例明确跳过。当前测试没有 SQLite 后端，
旧索引捕获执行器已移除，JSON 结果比较与 PostgreSQL 合成语料测试继续保留。
`scripts/check.ps1` 和 mypy 配置均禁用 SQLite 缓存，使用 JSON 文件缓存。
向量部分见 [Qdrant 独立服务](QDRANT_SERVICE.md)。

## 本地迁移与完整性记录（2026-10-20）

以下是首次关键词迁移的验收记录，本次依赖清理没有重新执行大批量检索评测。
当时 PostgreSQL 活动索引版本为 `generation_id=1`，迁移保留：

| 内容 | 数量 |
| --- | ---: |
| 文献 | 17 |
| 切片 | 22,338 |
| 词项 | 455,590 |
| 词项与切片对应记录 | 7,927,005 |
| 词位 | 10,438,350 |

全部元数据、预分词文本、原行号、文档长度及词位的逻辑 SHA-256 为
`6e3f2521eae810cc6cfd9b38c07996ccc46b45f66fb54dd5f737ea77d01be25e`，
与 SQLite 源索引一致。从现有 17 份 chunk JSONL 使用 PostgreSQL 构建路径重新计算，
也得到相同的完整逻辑摘要，验证后续重建不需要调用 SQLite。

迁移当时原数据库、切片、别名、既有人工标注和 Qdrant 等 27 个保留文件的 SHA-256
均未改变；这些指纹记录在 `data/reports/postgres-keyword-preservation.json`。
迁移备份原位于 `data/backups/keyword-to-postgres-20261020T062453Z-90b0ab4e/`，
独立对照基线及切换前配置备份原位于
`data/backups/keyword-to-postgres-20261020T061514Z/`（曾含凭据）；
两个目录均已于 2026-10-21 删除。

本地完整性报告：

- `data/reports/postgres-keyword-migration.json`：事务发布和全部内容摘要。
- `data/reports/postgres-keyword-rebuild-verification.json`：原切片重建的一致性。
- `data/reports/postgres-keyword-preservation.json`：27 个原文件指纹。

设置独立 PostgreSQL 测试库后，`scripts/check.ps1` 的 Ruff、mypy、975 项 Python 测试、
JavaScript 语法检查和 3 项前端流式测试全部通过。新增评测后处理随后单独通过静态检查及
7 项评测测试。

此次结果一致性不代表耗时不变。最终实现的四题交错查询中，SQLite 中位耗时约
50–128 ms，PostgreSQL 约 150–425 ms，24 次响应全部相同。该记录与正式采集并发，
受负载及缓存影响，仅作为本机观察值；仍需单独优化与验证 PostgreSQL 查询性能。
报告为 `data/reports/keyword-performance-paired-after-analyze.json`。

本机 `.env` 已切换关键词目标，服务已在 `http://127.0.0.1:8000/` 重启。
首页返回 200，健康接口确认主库、会话库及关键词索引均为 PostgreSQL；
就绪接口的主库、关键词与向量组件均正常。此项最小服务检查保存于
`data/reports/postgres-keyword-http.json`。

用户要求减少验证后，停止尚未完成的大批量检索采集，保留已完成结果，
未继续进行真实模型问答或重复全量核验。具体覆盖数量和评测边界见
[迁移评测记录](evals/keyword_migration/README.md)。
