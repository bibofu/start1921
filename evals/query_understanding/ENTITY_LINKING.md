# 实体索引与链接 shadow 报告（P1）

状态：**shadow，仅检测和锚定，不改变线上检索**。  
索引版本：`entity-index-v1-20261030`。  
评测数据：`query-understanding-seed-v1-20261030`（30 条，agent-prepared）。

## 索引内容

共 145 条记录：

| 类型 | 数量 | 来源 |
|---|---:|---|
| 人物 | 49 | `config/person_aliases.json` + `config/entities/extra_persons.json` |
| 文献 | 20 | `config/corpus_catalog.json` + `extra_documents.json` |
| 会议 | 20 | 中共一大到二十大，别名由序数生成 |
| 事件/时期 | 22 | `config/entities/extra_events.json` |
| 地点 | 13 | `config/entities/extra_places.json` |
| 组织 | 11 | `config/entities/extra_organizations.json` |
| 组合简称 | 10 | `config/entities/group_aliases.json`，一个 mention 对多个实体 |

构建命令：

```powershell
.\.venv\Scripts\python.exe -B scripts\build_entity_index.py --write
```

索引从 `data/processed/chunks` 统计人物共现、文档分布和语料内活动年份；不引入外部历史知识。会议时间范围留空，避免把章节讨论年份误当成会议年份。

## 检测与锚定

- 检测：词典最长匹配 + 模糊匹配（编辑相似度 ≥0.82，长度差 ≤2），支持一个 mention 对应多个实体（`刘邓`、`国共`）。
- 回指：问句含“他/她/它/其/该人”时，从最近历史中解析人物；年份式短追问（≤12 字）继承最近人物。
- 锚定评分：

```text
0.70 * 别名精确匹配
+ 0.20 * 时间兼容性（实体 active 与问句时间相交；缺元数据取 0.5）
+ 0.10 * 与其它已检测实体的语料共现
```

- `>= 0.75` 锚定；`0.50–0.75` 候选；`< 0.50` 未解决。
- 未解决 mention 保留原文，不进入硬过滤。

## Shadow 结果

| 指标 | 结果 |
|---|---:|
| 检测 Precision | 100.0% |
| 检测 Recall | 98.4% |
| 检测 F1 | 99.2% |
| 锚定 Precision | 100.0% |
| 锚定 Recall | 98.4% |
| 锚定 F1 | 99.2% |
| 未解决 mention 比例 | 0.0% |
| 查询臂总数 | 112 |
| 查询臂校验通过率 | 100.0% |

逐题结果在 [entity_linking/report.md](entity_linking/report.md)。查询臂 A/B 结论见 [QUERY_ARMS_AB.md](QUERY_ARMS_AB.md)：目前不接入生产。LLM 候选生成见 [LLM_CANDIDATES.md](LLM_CANDIDATES.md)。

## 剩余缺口

1. **索引外人物**：`习近平` 不在索引中，检测为空；这符合“不锚定索引外实体”的原则。LLM 候选生成尚未接入。
2. **回指是启发式**：只处理代词和“年份+呢”的短追问，复杂省略式追问仍可能漏。
3. **模糊匹配阈值未调优**：0.82/长度差 2 是在 30 条种子上选的经验值，需更大样本验证误报。
4. **事件/地点/组织没有文档引用**：索引里 documents 为空，不能用于过滤或共现加权，只能用于 mention 识别。
5. **活动年份来自语料共现**：人物 active 是“语料中出现过的最早/最晚年份”，不是生平活动期，时间兼容只能作弱信号。
6. **查询臂未接入检索**：目前只生成并校验 raw/canonical/per-entity 三类臂，112 条全部通过锁定校验，但没有在检索里做 A/B。

## 下一步（P2 剩余）

1. LLM 候选生成：对未命中 span 让模型只在实体索引内提名，再由模糊匹配校验；
2. 查询臂接入检索：raw/canonical/per-entity 三路 RRF，开关控制，只在开发题做 A/B；
3. 用更大样本验证模糊阈值和回指规则；
4. 在 shadow 日志中记录每次 mention、候选、锚定分数，积累误判样本。
