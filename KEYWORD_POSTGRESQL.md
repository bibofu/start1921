# PostgreSQL 关键词索引

关键词索引可以与主库共用 PostgreSQL，也可以使用独立数据库。
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

## 迁移与配置

先停止关键词索引构建任务，备份配置，再设置目标连接。应用服务应在验证完成后重启：

```dotenv
HISTORY_AGENT_KEYWORD_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

连接保存在被 Git 忽略的 `.env` 中，公开配置、运行记录与索引报告只显示后端及
`postgresql:keyword`，不记录 URL。密码中的特殊字符应进行 URL 编码。
迁移命令要求显式配置关键词目标，不会隐式推断主库地址。

```powershell
uv run start1921 index migrate-keyword-postgres `
  --backup-dir data/backups `
  --report data/reports/postgres-keyword-migration.json

uv run start1921 index verify-keyword-postgres `
  --report data/reports/postgres-keyword-verification.json
```

默认源为 `data/indexes/keyword_fts.db`，可用 `--source-index` 指定一致备份；
`--source-report` 可指定对应的原构建报告。验证命令可使用 `--generation-id` 核对某个版本。

迁移通过 SQLite backup API 创建一致快照，源文件保留不变。导入内容包括全部元数据、
预分词原文、原始行号、文档长度和 `fts5vocab(instance)` 导出的词位。
所有字段及全部词位的摘要、行数和词项统计校验通过后，才在同一 PostgreSQL 事务中
切换活动版本。导入失败会回滚，之前活动版本继续可用。

文件 SHA-256、原报告包含文件名的索引摘要、跨数据库的逻辑内容摘要是三种不同身份，
不能混用。SQLite backup 可能改变文件头，即使逻辑内容一致，文件哈希也可能不同。
只有原报告索引摘要与源文件按相同算法验证一致，才继承其切分来源等信息。

后续重新构建仍使用原命令：

```powershell
uv run start1921 index build-keyword
```

设置关键词 PostgreSQL URL 后，该命令直接从已有 chunk JSONL 创建新的 PostgreSQL
索引版本，不需要旧 SQLite 索引。旧 PostgreSQL 版本保留；未实现自动清理策略。
集群备份应同时覆盖关键词表，可使用 `pg_dump`。

若需要临时回退且原 SQLite 索引仍对应当前 chunks，可恢复旧配置并重启应用；
不要将旧索引用于已经变化的文献切片。主库与会话库的 PostgreSQL 配置无需改变。

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

开发测试通过 `HISTORY_AGENT_TEST_POSTGRES_URL` 使用独立数据库及随机 schema，
随后运行 `scripts/check.ps1`。测试和旧索引比较仍保留 SQLite；本阶段不宣称整个项目
已经完全移除 SQLite。关键词迁移之后的 Qdrant 服务迁移和剩余依赖边界见
[Qdrant 独立服务](QDRANT_SERVICE.md)。

## 本地迁移与完整性记录（2026-10-20）

本机 PostgreSQL 活动索引版本为 `generation_id=1`，迁移保留：

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

原数据库、切片、别名、既有人工标注和 Qdrant 等 27 个保留文件的 SHA-256 均未改变。
迁移备份位于 `data/backups/keyword-to-postgres-20261020T062453Z-90b0ab4e/`；
独立对照基线及切换前配置备份位于
`data/backups/keyword-to-postgres-20261020T061514Z/`。配置备份含凭据，仅在本机保管。

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
