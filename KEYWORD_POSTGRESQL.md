# PostgreSQL 关键词索引

关键词索引只使用 PostgreSQL，可以与主库共用，也可以使用独立数据库。

## 配置

默认使用 `HISTORY_AGENT_DATABASE_URL` 指定的 PostgreSQL 数据库。需要单独配置时，
在被 Git 忽略的 `.env` 中设置：

```dotenv
HISTORY_AGENT_KEYWORD_DATABASE_URL=postgresql://用户名:密码@127.0.0.1:55432/start1921
```

密码中的特殊字符应进行 URL 编码。关键词 URL 和主库 URL 均缺失时会报错，不会回退
到本地文件。公开配置、运行记录与索引报告只显示后端类型，不记录 URL。

## 切词与查询

索引版本为 `postgresql-bm25-jieba-v1`。中文使用 jieba search mode
（`lcut_for_search`）切词，同时产出词和词典内子词；英文、数字及含连字符或下划线的
标识转为小写后按词位规则拆词；四位年份额外加入 `YYYY` 和 `YYYY年`。

查询端使用同一 tokenizer，然后删除“哪些、什么、怎么、如何、主要、请问、经历、
观点、交集、期间”等停用词，删除以“的、了、在、和、与、及、是、有、为、于、把、
被、从、对”等虚词开头或结尾的中文 token，并去重。没有剩余可检索 token 时报检索
错误。查询词之间是 OR；人物、年份、文献、章节和资料范围由元数据过滤补充约束。

查询端还会删除文档频率过高的泛词（默认 `df/N > 0.12`），但保留
`config/jieba_userdict.txt` 中的实体专名。少于 500 个 chunk 的测试语料不启用该过滤。
精确实词加权由 `HISTORY_AGENT_KEYWORD_WORD_BOOST` 控制，默认 `1.0` 关闭。

需要补充领域词时，可通过 `HISTORY_AGENT_JIEBA_DICT` 或 `config/jieba_userdict.txt`
加载用户词典，每行格式为 `词语 [词频] [词性]`。项目词典由
`scripts/build_jieba_userdict.py` 从人物别名、实体目录、文献目录和会议名生成。

## 索引结构

`keyword_generations` 与 `keyword_active` 管理索引版本；`keyword_chunks` 保存完整
元数据、预分词文本、文档长度和原始行号；`keyword_postings` 保存词项、原始行号和
词位数组。构建时先在事务内写入完整数据，校验全部元数据与词位摘要后切换活动版本；
失败时保留原活动版本。

索引上界为 32 KiB 词项，词项不能包含反斜杠，因此可以采用不可变的
`sha256(term::bytea)` 唯一索引；检索时同时比较原始词项，哈希碰撞会失败而不是丢数据。

## 构建

新增或更新 chunk 后重建：

```powershell
uv run start1921 index build-keyword
```

该命令从 `data/processed/chunks/*.jsonl` 读取分片，写入新的 PostgreSQL 索引版本，
校验通过后在事务中切换 `keyword_active`。旧版本默认保留，需要时手工清理。

## 排序

BM25 参数为 `k1=1.2`、`b=0.75`，语料数量、平均长度和词项/短语文档频率均来自完整
索引，不随人物、时间、文献等过滤条件重新计算；非正 IDF 使用 `1e-6`。系统另减：

| 条件 | 排序奖励 |
| --- | ---: |
| 时间线问题命中年谱 | 4.0 |
| 观点问题命中选集 | 4.0 |
| 查询人物出现在文献作者中 | 2.0 |

对外分数保留六位小数。混合检索阶段只使用关键词排名，不比较 BM25 与向量分数的
绝对值。

## 测试

开发测试通过显式 `HISTORY_AGENT_TEST_POSTGRES_URL` 使用独立 PostgreSQL 数据库及
随机 schema；未配置时数据库用例明确跳过。`scripts/check.ps1` 运行 Ruff、mypy 和
pytest。向量部分见 [Qdrant 独立服务](QDRANT_SERVICE.md)，主库与会话库见
[PostgreSQL](POSTGRESQL.md)。
