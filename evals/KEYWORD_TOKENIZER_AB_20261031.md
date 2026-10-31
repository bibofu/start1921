# 关键词分词切换：bigram → jieba（2026-10-31）

## 决定

按用户 2026-10-31 的决定，生产关键词索引从 CJK 二元字 bigram 切换为 jieba。切换只改变 tokenizer，不改 BM25 参数、过滤、向量分支、RRF 或回答流程。

- jieba 版本：`0.42.1`
- 分词模式：`jieba.lcut_for_search`（search mode；词项 + 词典内子词）
- 索引版本：`postgresql-bm25-jieba-v1`
- 年份扩展、查询停用词、虚词边缘过滤、人物/年份/文献过滤保持不变
- 旧 bigram generation 保留在 PostgreSQL 中，但代码不再使用

## 对照口径

- 数据集：`golden-v2.7-selected-20-20261030`，18 道可答题；题目、证据组、人工标签、固定池未改动。
- 检索：`search_hybrid_index`，原问题直接检索，`candidate_k=30`、`top_k=20`、无 LLM 计划。
- 指标：`evaluate_stage` + 人工批准标签 + 固定池；unknown 不按 0 分。
- 单变量：只替换关键词 tokenizer，向量索引、RRF、来源奖励、按页去重、时间覆盖均未变。
- bigram 一侧复现了正式基线（Recall@10 62.6%、P@5 65.0%、MRR@10 0.971、nDCG@5 0.724），说明对照管线可信。

## 结果

### 完整混合检索

| 指标 | bigram | jieba search | 配对差值 | 共同可评 |
| --- | ---: | ---: | ---: | ---: |
| Recall@10 | 0.626 | 0.551 | -0.075 | 18 |
| Recall@20 | 0.670 | 0.635 | -0.036 | 18 |
| Precision@5 | 0.650 | 0.673 | 0.000 | 11 |
| MRR@10 | 0.971 | 0.971 | 0.000 | 17 |
| nDCG@5 | 0.724 | 0.779 | +0.011 | 11 |

### 仅关键词分支

| 指标 | bigram | jieba precise | jieba search | jieba + bigram 混合索引 |
| --- | ---: | ---: | ---: | ---: |
| Recall@10 | 0.540 | 0.506 | 0.532 | 0.540 |
| Recall@20 | 0.566 | 0.538 | 0.536 | 0.544 |
| MRR@10（共同可评） | 0.812 | 0.917 | 0.967 | 0.889 |

### 索引规模

| 指标 | bigram | jieba search | 词 + bigram 混合 |
| --- | ---: | ---: | ---: |
| 词项数 | 455,590 | 126,099 | 501,943 |
| 倒排记录 | 7,927,005 | 4,881,925 | 9,326,838 |
| 词位数 | 10,438,350 | 7,873,208 | 16,390,316 |
| 索引体积 | 约 163 MB | 134 MB | 227 MB |
| 混合检索耗时 | 394 ms | 303 ms | 325 ms |

## 结论

1. jieba 的索引更小、检索更快，MRR 更好，但混合检索 Recall@10 下降 7.5pp；关键词分支 Recall@10 下降 0.8pp。
2. jieba 把“遵义会议”“淮海战役”等合成整词后，只匹配同一词形；bigram 的相邻两字覆盖是召回安全网。精确模式下降更多（关键词 Recall@10 -3.3pp）。
3. 词 + bigram 混合索引把最终差距收回到 2.8pp，但索引比 bigram 大 39%，且逐题看只有 `holdout_intersection_negative` 一题下降；没有效率或质量优势。
4. bigram 与 jieba 双分支 RRF 也没有超过 bigram 的召回（Recall@10 0.532）。
5. Precision/nDCG 的固定池是按 bigram 时代候选采集的，jieba 新召回的池外页面是 unknown，不是不相关；两边可评题数不同，只有配对子集可比（6–11 题）。
6. 18 道题的样本量不足以确认 0.8–7.5pp 的差异；当前数字用于记录切换代价，不作为 jieba 优于 bigram 的证据。

## 切换后的状态与后续

- 生产关键词索引已用 jieba search mode 重建并切换；旧 bigram generation 仍保留，可用于回滚。
- 下一步优先：
  1. 领域自定义词典：人物别名、文献标题、机构名、历史专名；通过 `HISTORY_AGENT_JIEBA_DICT` 或 `config/jieba_userdict.txt` 加载。
  2. 在自定义词典基础上重跑本对照，确认召回是否回到或超过 bigram。
  3. RRF 权重 / candidate_k 单变量实验。
  4. 扩池补标与增加题量，之后再判断是否正式切换评测口径。
- 回滚：恢复 `keyword_common` 的 bigram tokenizer 与 `INDEX_VERSION`，把 `keyword_active` 指回旧 generation，重启服务。
