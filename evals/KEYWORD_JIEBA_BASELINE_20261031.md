# 关键词索引 jieba 基线（2026-10-31）

## 当前实现

- 索引版本：`postgresql-bm25-jieba-v1`
- tokenizer：jieba `0.42.1`，`lcut_for_search`
- 领域词典：`config/jieba_userdict.txt`，281 条，由
  `scripts/build_jieba_userdict.py` 从人物别名、实体、文献目录和会议名生成
- 查询端：删除高 DF 泛词（默认 `df/N > 0.12`），人物/机构/事件/文献等词典词不受影响；
  查询词之间的 OR、年份扩展、停用词和虚词边缘过滤保持不变
- 索引：22,338 chunks，4,881,925 倒排记录，7,873,208 词位，约 135 MB
- 精确实词加权默认关闭（`HISTORY_AGENT_KEYWORD_WORD_BOOST=1.0`）；实验显示开启后
  Recall@10 从 0.619 降到 0.605，不采用

## 同管线基线

- 数据集：`golden-v2.7-selected-20-20261030` 的 18 道可答题；题目、证据组、人工标签和固定池未改动。
- 检索：`search_hybrid_index`，原问题直接检索，`candidate_k=30`、`top_k=20`、无 LLM 计划。
- 指标：`evaluate_stage` + 人工批准标签 + 固定池；unknown 不按 0 分，不可评不计入宏平均。

| 指标 | 全部 18 题 | 开发集 14 题 | 保留集 4 题 |
| --- | ---: | ---: | ---: |
| Recall@10 | 0.619 | 0.605（n14） | 0.667（n4） |
| Recall@20 | 0.684 | 0.671（n14） | 0.729（n4） |
| Precision@5 | 0.686（n7） | 0.733（n6） | 0.400（n1） |
| MRR@10 | 0.969（n16） | 1.000（n13） | 0.833（n3） |
| nDCG@5 | 0.737（n7） | 0.755（n6） | 0.628（n1） |

## 对比

切换前正式基线为 Recall@10 62.6%、Recall@20 67.0%、P@5 65.0%、MRR@10 0.971、
nDCG@5 0.724。当前 jieba + 词典 + DF 过滤为 Recall@10 61.9%、Recall@20 68.4%、
MRR@10 0.969：Recall@10 低 0.7pp，Recall@20 高 1.4pp，MRR 基本持平。
P@5/nDCG 的固定池仍按切换前候选采集，可评题数只有 7 题，不能与旧数直接比较。

较早的朴素 jieba（无词典、无 DF 过滤）为 Recall@10 0.551、Recall@20 0.635；
词典单独把 Recall@10 提到 0.579，DF 过滤再提到 0.619。

## 解释边界

- 18 道题样本量有限，开发集与保留集指标都列出，避免只报总表。
- P@5/nDCG 受固定池覆盖限制，unknown 不是不相关；当前不作为切换依据。
- 领域词典来自项目既有别名/实体目录，没有引入外部词表或模型。

## 复现

```powershell
# 重新生成词典（别名/实体变化后）
.\.venv\Scripts\python.exe -B scripts\build_jieba_userdict.py
# 重建关键词索引
uv run start1921 index build-keyword
```

## 后续

1. 只调 RRF 权重或 `candidate_k`，目标是把 Recall@10 从 0.619 拉回 0.63 以上，同时保持 MRR。
2. 扩池补标并增加题量，让 P@5/nDCG 有可比分母。
3. 继续补充领域词时，优先加入评测中实际漏召回的专名，并一次只改一个变量。
