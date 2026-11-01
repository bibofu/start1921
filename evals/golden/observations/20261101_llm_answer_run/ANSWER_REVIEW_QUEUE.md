# LLM 答案与过程人工复核队列（A01–A12）

> 2026-11-01 生成。数据来自 `data/reports/golden12_llm_20261101/capture.json`（12 题，LLM 正式回答）。候选标签和固定池已人工批准；本队列用于答案与过程复核。
>
> 本文件是复核工作稿；A01/A02 的勾选为工作笔记，最终事实判断以 [REVIEWED.md](REVIEWED.md) 和 `data/reports/golden12_llm_20261101/reviewed/answer_reviews.json` 为准。

回复格式：

```text
A01 fact seven_congress_dates covered supported E3
A01 dim citation_support pass
A01 dim source_constraint not_applicable
A01 process pass 查询理解覆盖了“七大/党章/时间”三个要素
A11 refusal safe_refusal pass scope_explanation pass
A12 refusal safe_refusal pass scope_explanation pass
```

允许值：

- fact status：`covered` / `partial` / `missing` / `contradicted` / `unknown`
- support_status：`supported` / `partial` / `unsupported` / `unknown` / `not_applicable`
- dimension status：`pass` / `fail` / `unknown` / `not_applicable`
- process status：`pass` / `fail` / `unknown` / `not_applicable`

回填位置：

- `answer_reviews.json`：`cases[].facts[].status/support_status/answer_excerpt/cited_evidence_ids`，`cases[].dimensions.<dimension>.status/reason`
- `process_reviews.json`：`cases[].status/reason`，`criterion` 保持只读
- 两份文件都要填 `basis: "human_review"`、`reviewer`、`reviewed_at`（带时区）
- 不要改 hash、capture 快照、`executed_query_plan` 或分母

## 总览

| 编号 | 题 | 分层 | 答案性 | 答案长度 | 引用 | planner | reflection |
|---|---|---|---|---:|---:|---|---|
| A01 | `dev_exact_mao_thought_party_constitution` | development | answerable | 402 | 2 | used | skipped |
| A02 | `holdout_exact_founding_ceremony` | holdout | answerable | 43 | 1 | used | skipped |
| A03 | `dev_semantic_double_hundred` | development | answerable | 1560 | 9 | used | retried |
| A04 | `holdout_semantic_angang_constitution` | holdout | answerable | 409 | 3 | used | skipped |
| A05 | `dev_multi_long_march_meetings` | development | answerable | 983 | 6 | used | retried |
| A06 | `holdout_multi_two_bombs_satellite` | holdout | answerable | 1734 | 12 | used | retried |
| A07 | `dev_intersection_zhu_peng_command` | development | answerable | 351 | 4 | fallback | skipped |
| A08 | `holdout_intersection_mao_zhu_jinggangshan` | holdout | answerable | 348 | 2 | used | skipped |
| A09 | `dev_constraint_korean_war_decision` | development | answerable | 1874 | 6 | used | skipped |
| A10 | `holdout_constraint_nanchang_uprising_background` | holdout | answerable | 1095 | 2 | used | skipped |
| A11 | `dev_refusal_marriage_law_concubinage` | development | unanswerable | 369 | 2 | used | skipped |
| A12 | `holdout_refusal_un_seat_timing` | holdout | unanswerable | 348 | 2 | used | skipped |

## 共性观察

- 12/12 `llm_status=used`，0 degraded，34 次 HTTP 调用全部 200。
- 12/12 `evidence_status=partial`，`uncited_claims=0`。
- `dev_intersection_zhu_peng_command` 的 query planner 为 `fallback`（`invalid_plan`）。
- `dev_semantic_double_hundred`、`dev_multi_long_march_meetings`、`holdout_multi_two_bombs_satellite` 的 retrieval reflection 为 `retried`。
- 总 Token 106,310；回答平均 13,061 ms，最长 42,955 ms。

## A01 · `dev_exact_mao_thought_party_constitution`

- 分类：`exact_fact`
- 分层：`development`
- 答案性：`answerable`
- 问题：毛泽东思想什么时候写入党章？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `seven_congress_dates`：中共七大于1945年4月23日至6月11日召开
- `mao_thought_written_into_charter`：七大通过的党章把毛泽东思想确立为党的指导思想并写入党章

证据组：

- `seven_congress_1945`：中共七大于1945年4月23日至6月11日在延安举行
- `mao_thought_in_charter_1945`：七大党章把毛泽东思想确立为党的指导思想并写入党章

### 答案原文

```text
**毛泽东思想写入党章的时间是1945年，在党的第七次全国代表大会上。**[E3][E9]

### 关键事实

- **1945年，中共七大**：七大“确立毛泽东思想为党的指导思想并写入党章”，这是七大的历史性贡献。七大党章提出：“毛泽东思想，就是马克思列宁主义的理论与中国革命的实践之统一的思想，就是中国的共产主义，中国的马克思主义。”[E3]

- **1945年5月14日、15日**：刘少奇在中共七大上作关于修改党章的报告，其中说明：“党章的总纲上确定以毛泽东思想作为我党一切工作的指针，在党章的条文上又规定：努力地领会马克思列宁主义、毛泽东思想的基础，是每一个共产党员的义务。这是我们这次修改的党章一个最大的历史特点。”[E9]

### 资料限制

现有证据直接支持七大（1945年）将毛泽东思想写入党章这一结论。证据中未包含七大党章原文的完整条文，也未提供其他历史时期党章修改的对比材料。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E3 | cpc_history_volume_1 | 814 | 下 册 > 第四编 党在全民族抗日战争时期（1937年7月—1945年8月） > 第十七章 争取人民抗战的最后胜利 > 四、党的第七次全国代表大会 | 七大是中国共产党在新民主主义革命时期极其重要的一次、也是最后一次代表大会。它总结中国新民主主义革命20多年曲折发展的历史经验，制定了正确的路线、纲领和策略，克服了党内的错误思想，使全党特别是党的高级干部对于中国民主革命的发展规律有了比较明确的认识，从而使全党在马克思列宁主义、毛泽东思想的基础上达到了空前的团结。这次大会作为“团结的大会，胜利的大会”而载入史册… |
| E9 | mao_zedong_chronology_volume_2 | 604 | 1945年（1月—8月） | ……5 月8 日在枣园主持中共七大主席团和各代表团主任会议，会议听取各代表团讨论情况的汇报。在听汇报后说：结论缓一点作，多酝酿些好，小组中有许多好的意见。对中国的斯科比(2J估计得严重些好，蒋介石一定要反共。总之，这次苏联强大了，人民觉悟了，我们党也强大了。同志们强调困难是好的，但结论要多指出光明才好。同日德国无条件投降，欧洲反法西斯战争胜利结束。5 月日朱… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：毛泽东思想何时被写入党章？
- search_queries：["毛泽东思想 写入党章", "七大 党章 毛泽东思想 指导思想", "中国共产党章程 毛泽东思想 确立"]
- entities：[{"type": "other", "text": "毛泽东思想", "canonical": "毛泽东思想"}, {"type": "document", "text": "党章", "canonical": "中国共产党章程"}]
- start_year/end_year：None / None
- constraints：[]

### 复核填写

事实：

- `seven_congress_dates`：中共七大于1945年4月23日至6月11日召开
  - 事实状态：[covered ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ supported ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `mao_thought_written_into_charter`：七大通过的党章把毛泽东思想确立为党的指导思想并写入党章
  - 事实状态：[ covered] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[supported ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ pass] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ pass] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ pass] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[pass ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[pass ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A02 · `holdout_exact_founding_ceremony`

- 分类：`exact_fact`
- 分层：`holdout`
- 答案性：`answerable`
- 问题：开国大典的地点和时间？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `founding_time_place`：开国大典于1949年10月1日下午3时在北京天安门广场举行
- `founding_declaration`：毛泽东在天安门城楼上宣告中华人民共和国中央人民政府成立

证据组：

- `founding_ceremony_1949`：1949年10月1日下午3时开国大典在北京天安门广场举行

### 答案原文

```text
**开国大典的地点和时间**：1949年10月1日下午3时，在天安门广场举行[E2]。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E2 | cpc_history_volume_2 | 15 | 插图 | 1949年10月1日下午3时，中华人民共和国中央人民政府成立典礼（即开国大典）在天安门广场隆重举行。图为毛泽东庄严宣告：“中华人民共和国中央人民政府今天成立了！” |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：开国大典的地点和时间？
- search_queries：["开国大典 地点 时间", "中华人民共和国开国大典 举行地点 日期"]
- entities：[{"type": "event", "text": "开国大典", "canonical": "中华人民共和国开国大典"}]
- start_year/end_year：None / None
- constraints：[]

### 复核填写

事实：

- `founding_time_place`：开国大典于1949年10月1日下午3时在北京天安门广场举行
  - 事实状态：[ covered] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ supported] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `founding_declaration`：毛泽东在天安门城楼上宣告中华人民共和国中央人民政府成立
  - 事实状态：[ covered] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ supported] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A03 · `dev_semantic_double_hundred`

- 分类：`semantic_retrieval`
- 分层：`development`
- 答案性：`answerable`
- 问题：1956年党中央为什么提出“百花齐放、百家争鸣”方针？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `double_hundred_background_fact`：新中国成立后头几年，科学文化领域受苏联学术批评中粗暴作风和教条主义影响，存在推崇一个学派、压制另一个学派、乱贴政治标签等现象
- `double_hundred_purpose_fact`：党中央提出“百花齐放、百家争鸣”作为繁荣和发展社会主义科学文化事业的指导方针
- `double_hundred_proposal_fact`：1956年4月28日毛泽东在中央政治局扩大会议总结讲话中提出艺术上百花齐放、学术上百家争鸣；5月2日最高国务会议正式提出这一方针

证据组：

- `double_hundred_background`：科学文化领域受苏联学术批评中粗暴作风和教条主义影响
- `double_hundred_purpose`：双百方针是繁荣和发展社会主义科学文化事业的指导方针
- `double_hundred_proposal_1956`：1956年4月28日毛泽东提出、5月2日最高国务会议正式提出双百方针

### 答案原文

```text
根据现有证据，1956年党中央提出“百花齐放、百家争鸣”方针的直接理由，可从毛泽东和陆定一当时的阐述中得到部分确认，但提纲中关于“社会主义改造基本完成后工作重心转向经济文化建设”“正确处理人民内部矛盾”“苏共二十大后反思苏联模式”“克服官僚主义、主观主义和宗派主义”等动因，在本轮证据中缺乏直接支持。

**一、证据明确支持的提出理由**

- **促进文学艺术和科学研究中的自由讨论与独立思考。** 1956年5月26日，陆定一在知识界会议上作《百花齐放、百家争鸣》报告，代表党中央阐述该方针，指出其提倡在文学艺术工作和科学研究工作中有独立思考、辩论、创作和批评的自由，有发表、坚持和保留自己意见的自由[E1]。
- **打破学术上“一种学术压倒一切”的局面。** 毛泽东在1956年谈到学术问题时说：“讲学术，这种学术可以讲，那种学术也可以讲，不要拿一种学术压倒一切”[E2]。
- **继承并发展文艺界已有的“百花齐放”提法，同时借鉴历史上诸子百家自由争论的传统。** 毛泽东说明，“百花齐放”是文艺界提出的，他写了“百花齐放，推陈出新”；“百家争鸣”指春秋战国时代诸子百家自由争论，现在也需要这个[E3]。
- **在宪法范围内允许各种学术思想发表，不强行干涉。** 毛泽东表示，在中华人民共和国宪法范围之内，各种学术思想，正确的、错误的，让他们去说，不去干涉[E1]。
- **毛泽东明确肯定这一方针“有必要”。** 1956年5月2日，毛泽东在最高国务会议第七次会议上系统阐述十大关系问题，并专门谈到“百花齐放、百家争鸣”问题，称“在艺术方面的百花齐放的方针，学术方面的百家争鸣的方针，是有必要的”[E3]。

**二、证据支持的提出背景与定位**

- 该方针是在毛泽东作《论十大关系》报告前后提出的，与党在新形势下对知识分子的政策、“向现代科学进军”的任务并列提出[E15]。
- 该方针属于1956年前后党提出的一系列新方针之一，与探索中国自己的建设社会主义道路相关联[E15]。
- 方针提出后，中央仍继续研究推动。1956年10月17日，毛泽东主持召开中共中央政治局常委扩大会议，专门讨论“百家争鸣”问题，陆定一、胡乔木、张际春、周扬、田家英参加[E9]。

**三、提纲中未能得到证据支持的内容**

- 提纲称提出双百方针是为了适应“社会主义改造基本完成后工作重心转向经济文化建设”的新形势，本轮证据未直接说明这一因果关系[E1][E2][E3][E15]。
- 提纲称提出双百方针是为了“正确处理人民内部矛盾”、用说服教育方法解决思想问题、避免压服和强制手段，本轮证据未提供直接支持[E1][E2][E3][E8][E12][E13]。
- 提纲称提出双百方针与苏共二十大后对斯大林错误的批判、反思苏联模式有关，本轮证据未涉及这一国际背景[E3][E15]。
- 提纲称提出双百方针是为了克服党内官僚主义、主观主义和宗派主义，通过鼓励自由讨论和批评改进党的工作作风，本轮证据未提供直接支持[E4][E8][E12]。
- 提纲称提出双百方针是为了在学术和艺术领域打破教条主义束缚，本轮证据中虽有“不要拿一种学术压倒一切”的表述[E2]，但未明确使用“教条主义”概念，也未直接说明其与打破教条主义的关系。

**四、资料限制**

现有证据主要来自1956年毛泽东讲话、陆定一报告及中央会议记录，能够说明方针的提出过程、内容表述和毛泽东、陆定一阐述的理由，但缺少党中央作出该决策的完整内部讨论过程，也没有提供关于社会主义改造完成后形势判断、人民内部矛盾理论、苏共二十大影响、反官僚主义整风动因等方面的直接政策文件或讲话依据。因此，提纲中多项动因只能视为待进一步核实的推断，不能仅凭现有证据确认。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | cpc_history_volume_2 | 395 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十章 党的八大和探索中国自己的建设社会主义道路的良好开端 > 二、毛泽东的《论十大关系》和一系列新方针的提出 | 在中华人民共和国宪法范围之内，各种学术思想，正确的、错误的，让他们去说，不去干涉他们。5月26日，在中南海怀仁堂召开的知识界会议上，中央宣传部部长陆定一作《百花齐放、百家争鸣》的报告，代表党中央对这一基本方针作了详尽的阐述。陆定一指出，我们所主张的“百花齐放、百家争鸣”是提倡在文学艺术工作和科学研究工作中有独立思考的自由，有辩论的自由，有创作和批评的自由，有… |
| E2 | mao_zedong_chronology_volume_5 | 576 | 1956年（1月-9月） | 术问题上的百家争鸣，我看这个应该成为我们的方针。“百花齐放”是群众中提出来的，人们要我题词，我就写了“百花齐放，推陈出新”。“百家争鸣“，这是两千年以前的事，春秋战国时代，百家争鸣。讲学术，这种学术可以讲，那种学术也可以讲，不要拿一种学术压倒一切。关于民主管理问题，他说：现在集体化了，能听命令，一起上工，这就有极大的利益。但是什么都得听命令，这就宽了。命令要… |
| E3 | mao_zedong_chronology_volume_5 | 579 | 1956年（1月-9月） | ……5 月2 日下午三时，同周恩来、张治中谈关于张治中给台湾当局有关领导人写信的问题，朱德参加。同日下午四时，在中南海勤政殿主持召开最高国务会议第七次会议。参加会议的共一百一十多人。毛泽东发表讲话，又一次系统阐述十大关系问题。在与会者发言之后，毛泽东再次讲话。关千“百花齐放、百家争鸣”问题，他说：我们在有省市自治区党委书记参加的政治局扩大会议上还谈到这一点，… |
| E4 | cpc_history_volume_2 | 429 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十一章 全党整风和反右派斗争 > 一、关于社会主义社会矛盾问题的学说 | 分子，在“百花齐放、百家争鸣”方针提出后，思想日趋活跃，批评教条主义，在政治、经济、文化、教育、科学等问题上发表各种意见。有些人对党和政府工作中的缺点以及干部作风上的问题提出批评，其中有不少尖锐意见，也有一些错误议论。面对新出现的矛盾，许多党员和干部思想上缺乏准备，往往用老眼光，把群众闹事和尖锐批评一概视为阶级斗争的表现，认为凡是聚众闹事的，就是敌我矛盾；一… |
| E8 | cpc_history_volume_2 | 437 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十一章 全党整风和反右派斗争 > 一、关于社会主义社会矛盾问题的学说 | ……针对近半年来发生的工人罢工、学生罢课和群众性游行等事件，中央连续发出《关于处理罢工、罢课问题的指示》、《关于研究有关工人阶级的几个重要问题的通知》。中央认为：“这类事件的发生，首先是由于我们的工作没有作好，特别是由于领导者的官僚主义”。防止这类事情的发生，根本的办法是随时调整社会主义社会内部关系中存在的问题，“首先是克服官僚主义”。中央决定在年内召开的工… |
| E9 | mao_zedong_chronology_volume_6 | 17 | 1956年（10月-12月） | ……工作改革问题的文件，已经写出一个初稿，准备再讨论几次并征求有关同志意见修改后，送毛主席阅，如果需要在中央常委会上谈一下也可以。毛泽东表示同意。10 月17 日晚上，在中南海颐年堂主持召开中共中央政治局常委扩大会议，讨论“百家争鸣”问题和彭德怀提出的缩减军队问题，刘少奇、周恩来、朱德、陈云、邓小平、彭德怀出席。讨论“百家争鸣”问题时，陆定一、胡乔木、张际春… |
| E12 | cpc_history_volume_2 | 434 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十一章 全党整风和反右派斗争 > 一、关于社会主义社会矛盾问题的学说 | ……批评和自我批评是人民内部教育自己和发展自己事业的一个方针。毛泽东提出这些方针政策，接续了《论十大关系》的基本方针和八大的政治路线。它的着眼点，在于调动一切积极因素，团结一切可以团结的人，尽可能将消极因素转变为积极因素，为建设社会主义这一伟大事业服务。1957年3月6日至13日，中共中央在北京召开全国宣传工作会议。会议的主要议题，是传达贯彻毛泽东《关于正确… |
| E13 | cpc_history_volume_2 | 433 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十一章 全党整风和反右派斗争 > 一、关于社会主义社会矛盾问题的学说 | 在科学文化工作中贯彻“百花齐放、百家争鸣”；在与民主党派的关系上实行“长期共存、互相监督”；在汉族和少数民族方面一定要搞好关系，关键是克服大汉族主义，同时应当克服地方民族主义；对知识分子应当从根本上改善同他们的关系，给予信任，善于团结，同时加强对他们的教育和思想政治工作。毛泽东还特别强调：对知识分子和青年学生要加强思想政治工作。思想政治工作，共产党应该管，青… |
| E15 | cpc_history_volume_2 | 391 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十章 党的八大和探索中国自己的建设社会主义道路的良好开端 > 二、毛泽东的《论十大关系》和一系列新方针的提出 | 毛泽东回顾这段历史时多次说过：前几年经济建设主要学外国经验，1956年4月论十大关系，开始提出自己的建设路线，有我们自己的一套内容。后来，邓小平也曾对《论十大关系》作出这样的评价：“这篇东西太重要了，对当前和以后，都有很大的针对性和理论指导意义”【10】。“向现代科学进军”和“百花齐放、百家争鸣”的方针在毛泽东作《论十大关系》报告前后，党还提出了新形势下对知… |

限制/说明：

- 尚缺证据：苏共二十大等国际形势影响；1956年提出原因的直接论述；1956年党中央提出双百方针的具体决策过程，如中央会议讨论细节、不同领导人的意见等。；双百方针提出时对苏联模式反思的具体内容，以及国际共产主义运动变化的影响。；双百方针提出前知识分子的具体状况和诉求，以及党对知识分子政策的调整过程。；双百方针与当时经济、政治领域其他方针政策（如十大关系、长期共存互相监督）的关联和互动。；双百方针提出后初期的实施效果和知识界的反应。
- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`retried`；retrieval_rounds：3
- retrieval_mode：`research_hybrid`；intent：`causal_analysis`；coverage：`relevance`
- normalized_question：1956年党中央为什么提出“百花齐放、百家争鸣”方针？
- search_queries：["1956年 百花齐放 百家争鸣 方针 提出 原因", "双百方针 1956 背景 党中央", "百花齐放 百家争鸣 知识分子 政策 1956"]
- entities：[{"type": "organization", "text": "党中央", "canonical": "中国共产党中央委员会"}]
- start_year/end_year：1956 / 1956
- constraints：["1956年", "党中央提出", "原因"]

### 复核填写

事实：

- `double_hundred_background_fact`：新中国成立后头几年，科学文化领域受苏联学术批评中粗暴作风和教条主义影响，存在推崇一个学派、压制另一个学派、乱贴政治标签等现象
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `double_hundred_purpose_fact`：党中央提出“百花齐放、百家争鸣”作为繁荣和发展社会主义科学文化事业的指导方针
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `double_hundred_proposal_fact`：1956年4月28日毛泽东在中央政治局扩大会议总结讲话中提出艺术上百花齐放、学术上百家争鸣；5月2日最高国务会议正式提出这一方针
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A04 · `holdout_semantic_angang_constitution`

- 分类：`semantic_retrieval`
- 分层：`holdout`
- 答案性：`answerable`
- 问题：20世纪60年代中国工业战线所说的“两参一改三结合”具体指什么？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `angang_workers_management`：工人参加管理
- `angang_cadres_labour`：干部参加劳动
- `angang_rules_reform`：改革不合理的规章制度
- `angang_three_way_combination`：实行工人群众、技术人员、领导干部三结合

证据组：

- `angang_constitution_1960`：“两参一改三结合”的基本精神

### 答案原文

```text
“两参一改三结合”在20世纪60年代中国工业战线上的具体内容是：**工人参加管理，干部参加劳动，改革不合理的规章制度，实行领导干部、技术管理人员和工人相结合**[E4][E7]。

具体要点如下：

- **“两参”**：指干部参加劳动、工人参加管理[E5][E7]。
- **“一改”**：指改革不合理的规章制度[E5][E7]。
- **“三结合”**：指领导干部、技术管理人员和工人相结合[E7]。

这一方针在1960年3月毛泽东对中共鞍山市委报告的批示中被概括为管理社会主义企业的原则之一，后来被称为“鞍钢宪法”的主要内容[E5][E7]。1964年邓小平视察鞍钢时，也要求把贯彻“工业七十条”和贯彻“鞍钢宪法”结合起来，其中“鞍钢宪法”即包含“两参一改三结合”[E5]。

**资料限制**：现有证据对“两参一改三结合”的具体解释较为一致，但缺少60年代工业战线推行该制度时的更详细操作规定或各地实施案例。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E4 | cpc_history_volume_2 | 670 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十七章 国民经济调整任务的完成和“四个现代化”目标的提出 > 三、团结一致战胜困难和奋发图强的社会风貌 | ……社论说：“我国的经济形势，从农业到工业、从乡村到城市都在一天一天地好起来。”“整个国民经济的调整工作见效之快，农业生产在连年大灾以后恢复速度之快，都超过了预计。”渡过暂时困难，人民迎来了祖国欣欣向荣的春天。1963年春节，全国人民沉浸在喜庆祥和的气氛中。北京的厂甸庙会重新开放，给久已沉寂的市场带来一份生机，传达出国家经济走向复苏、市场初现繁荣的信息。尽管… |
| E5 | deng_xiaoping_chronology_1904_1974_lower | 491 | 1964年 | ……在谈到办学校的问题时指出：办学校要两条腿走路，即要办正规学校，也要办简易学校，还可以办职业学校。普通中学，有的可以改为技工学校或职业学校。但是，不能增加在校职工。对职业学校的学生也不能包分配。在谈到市委工作时指出：旅大农村人口这么多，地面也很大，只靠一个农村工作部是管不了的。应设立农村工作委员会，由其独当一面。城乡工作要区分开，不分开就会顾了这头顾不了那… |
| E7 | zhou_enlai_chronology_1949_1976 | 1405 | 1973年 | [303] “鞍钢宪法”是一九六○年三月毛泽东对鞍钢开展技术革新和技术革命运动经验的称誉。“鞍钢宪法”的主要内容是：加强党的领导，坚持政治挂帅，大搞群众运动，实行“两参一改三结合”（干部参加劳动，工人参加管理，改革不舍理的规章制度；领导干部、技术管理人员和工人相结合），大搞技术革新和技术革命。 |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：20世纪60年代中国工业战线所说的“两参一改三结合”具体指什么？
- search_queries：["两参一改三结合", "两参一改三结合 具体内容", "工业战线 两参一改三结合 60年代", "鞍钢宪法 两参一改三结合"]
- entities：[{"type": "other", "text": "两参一改三结合", "canonical": "两参一改三结合"}]
- start_year/end_year：None / None
- constraints：["20世纪60年代", "中国工业战线"]

### 复核填写

事实：

- `angang_workers_management`：工人参加管理
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `angang_cadres_labour`：干部参加劳动
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `angang_rules_reform`：改革不合理的规章制度
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `angang_three_way_combination`：实行工人群众、技术人员、领导干部三结合
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A05 · `dev_multi_long_march_meetings`

- 分类：`multi_evidence`
- 分层：`development`
- 答案性：`answerable`
- 问题：梳理长征期间，召开的会议。
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `lm_tongdao`：长征期间召开了通道会议（中央负责人紧急会议）
- `lm_liping`：长征期间召开了黎平会议（中央政治局会议）
- `lm_houchang`：长征期间召开了猴场会议（中央政治局会议）
- `lm_zunyi`：长征期间召开了遵义会议（中央政治局扩大会议）
- `lm_zhaxi`：长征期间召开了扎西中央负责人会议
- `lm_huili`：长征期间召开了会理会议（中央政治局扩大会议）
- `lm_lianghekou`：长征期间召开了两河口会议（中央政治局会议）
- `lm_luhua`：长征期间召开了芦花会议（中央政治局常委会议）
- `lm_shawu`：长征期间召开了沙窝会议（中央政治局会议）
- `lm_shawu_standing`：长征期间召开了沙窝中央政治局常委会议
- `lm_maoergai`：长征期间召开了毛儿盖会议（中央政治局会议）
- `lm_axi`：长征期间召开了阿西紧急会议
- `lm_ejie`：长征期间召开了俄界会议（中央政治局扩大会议）
- `lm_bangluozhen`：长征期间召开了榜罗镇会议（中央政治局常委会议）
- `lm_wuqi`：长征期间召开了吴起镇中央政治局会议

证据组：

- `long_march_tongdao`：通道会议（中央负责人紧急会议）
- `long_march_liping`：黎平会议（中央政治局会议）
- `long_march_houchang`：猴场会议（中央政治局会议）
- `long_march_zunyi`：遵义会议（中央政治局扩大会议）
- `long_march_zhaxi`：扎西中央负责人会议（含鸡鸣三省常委分工）
- `long_march_huili`：会理会议（中央政治局扩大会议）
- `long_march_lianghekou`：两河口会议（中央政治局会议）
- `long_march_luhua`：芦花会议（中央政治局常委会议）
- `long_march_shawu`：沙窝会议（中央政治局会议）
- `long_march_shawu_standing`：沙窝中央政治局常委会议
- `long_march_maoergai`：毛儿盖会议（中央政治局会议）
- `long_march_axi`：阿西紧急会议
- `long_march_ejie`：俄界会议（中央政治局扩大会议）
- `long_march_bangluozhen`：榜罗镇会议（中央政治局常委会议）
- `long_march_wuqi`：吴起镇中央政治局会议

### 答案原文

```text
根据现有证据，可梳理出长征期间召开的会议如下：

## 一、长征途中重要会议

### 1935年

**遵义会议（中共中央政治局扩大会议）**  
1935年1月15日至17日在遵义召开。毛泽东出席并作长篇发言，批评秦邦宪、李德的军事指挥和战略战术错误，意见得到大多数与会者支持；会议委托张闻天起草《中央关于反对敌人五次“围剿”的总结的决议》[E5]。遵义会议集中纠正了军事上和组织上的错误，结束了“左”倾路线在党中央的统治，开始了以毛泽东为首的中央新的领导[E4]。

**沙窝会议（中共中央政治局常委会议）**  
1935年8月19日在沙窝召开。毛泽东出席，会议研究常委分工等问题，决定张闻天负责组织部、秦邦宪负责宣传部、毛泽东负责军事，王稼祥负责政治部、何凯丰负责少数民族委员会工作；并决定常委会每周至少召开一次[E10]。

**毛儿盖会议（中共中央政治局会议）**  
1935年8月20日在毛儿盖召开。毛泽东出席，会议听取毛泽东关于夏洮战役后行动问题的报告，确定红军主力应向东、向陕甘边界发展，不应向黄河以西[E10]。

**榜罗镇会议**  
1935年召开，具体时间、地点和议程细节在证据中未提供。相关记载提到某次会议“批准了榜罗镇会议的战略决策，宣告了中央红军长征结束”[E13]，表明这是长征结束阶段的一次重要战略决策会议。

**陕甘支队团以上干部会议**  
1935年10月25日召开。毛泽东出席并作报告，指出胜利到达目的地、革命形势已到拂晓，并提出当前任务是进行军事政治教育、争取群众扩大红军、改善生活充实被服[E13]。

**瓦窑堡会议（中央政治局扩大会议）**  
1935年12月在瓦窑堡召开。会议通过了《中央关于军事战略问题的决议》，确定党的总任务是“以坚决的民族战争反抗日本帝国主义进攻中国”[E12]。

### 1936年

**中共中央政治局会议**  
1936年10月11日、12日召开。毛泽东出席，会议讨论红军政治工作问题，毛泽东就政治工作成绩、干部教育、干部政策等发言[E11]。

## 资料限制

现有证据未提供长征途中其他会议（如通道会议、黎平会议、猴场会议、扎西会议、会理会议、两河口会议、俄界会议、巴西会议等）的直接记载，无法据以梳理完整会议清单。榜罗镇会议的具体时间、地点和议程细节也缺乏材料。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E4 | mao_selected_works_combined | 567 | 毛选1-7(静火+赤旗+草堂) > 正文 > 毛泽东选集 第一至七卷 静火版 > 第三卷 > 抗日战争时期（下） > 学习和时局 | ……在中央所在地区红军长征开始后，这种怀疑和不满更加增长，以至有些曾经犯过“左”倾错误的同志，这时也开始觉悟，站在反对“左”倾错误的立场上来了。于是广大的反对“左”倾路线的干部和党员，都在毛泽东同志的领导下团结起来，因而在一九三五年一月，在毛泽东同志所领导的在贵州省遵义城召开的扩大的中央政治局会议上，得以胜利地结束了“左”倾路线在党中央的统治，在最危急的关头… |
| E5 | mao_zedong_chronology_volume_1 | 452 | 1935年 | ……在大会上发表演说，讲述共产党与红军的各项政策，指出共产党愿意联合国内各界人民、各方军队一致抗日，强调只有苏维埃才能救中国。大会宣布成立遵义县革命委员会。1 月1S 日— 17 日出席在遵义召开的中共中央政治局扩大会议（通称遵义会议）。在会上就长征以来各种争论问题，主要是最紧迫的军事路线问题，作长篇发言。发言批评秦邦宪在向大会报告中谈到的第五次反“围剿”失… |
| E10 | mao_zedong_chronology_volume_1 | 476 | 1935年 | ……8 月19 日出席在沙窝召开的中共中央政治局常委会议，研究常委分工等问题。会议决定，张闻天负责组织部工作，秦邦宪负责宣传部工作，毛泽东负责军事工作；并决定由王稼祥负责政治部工作，何凯丰负责少数民族委员会工作。会上，王稼祥提出要同张国焘作斗争的问题。毛泽东说：在毛儿盖时已经说过，斗争是需要的，但目前开展斗争是不适宜的。目前我们应采取教育的方式。写文章，不指… |
| E11 | mao_zedong_chronology_volume_1 | 605 | 1936年 | 的影响与力量，造成我们自己工作中的困难。10 月11 日、12 日出席中共中央政治局会议，会议讨论红军政治工作问题。毛泽东发言指出：红军的政治工作，在克服长征中的疲劳现象、提高政治情绪上有成绩。应特别注意干部教育，在这方面过去有成绩，也有很多经验，主要是：军事与政治并重；理论与实际并重；理论与实际相联系；教育课少而精。政治工作的方式要有计划性、纲领性和灵活性… |
| E12 | cpc_history_volume_1 | 492 | 上 册 > 第三编 党在土地革命战争时期（1927年8月—1937年7月） > 第十二章 遵义会议和红军长征的胜利 > 三、红一、红二、红四方面军胜利会师 | 三、红一、红二、红四方面军胜利会师红一方面军的东征和西征当中共中央和红军还在长征途中的时候，民族危机日益加深，全国人民的抗日救亡运动又高涨起来，国内政局出现一些新的变化。但是，国民党统治集团仍然不肯放弃“剿共”政策。这时，它除在南方继续“清剿”留在老根据地的红军外，还企图以重兵消灭中共中央所在的陕甘根据地。1936年初，陕甘根据地的南部和西南部，有杨虎城的第… |
| E13 | mao_zedong_chronology_volume_1 | 491 | 1935年 | ……提高战斗力，扩大红军，解决物质问题，是目前部队的中心工作。要加强白区、白军工作和游击工作的配合。要尊重地方群众的意见，不要自高自大地压制他们。动员群众主要依靠地方工作，不依靠他们没有办法。与会者一致同意毛泽东的报告和结论。这次会议，批准了榜罗镇会议的战略决策，宣告了中央红军长征结束。随后，派白区工作部部长贾拓夫作为先遣队寻找陕北红军和刘志丹，李维汉同行。… |

限制/说明：

- 尚缺证据：长征途中其他重要会议；会议时间地点序列；会议决策与影响
- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`retried`；retrieval_rounds：3
- retrieval_mode：`research_hybrid`；intent：`event_overview`；coverage：`per_item`
- normalized_question：梳理长征期间召开的会议
- search_queries：["长征 会议", "长征途中 召开 会议", "红军长征 重要会议"]
- entities：[{"type": "event", "text": "长征", "canonical": "中国工农红军长征"}]
- start_year/end_year：1934 / 1936
- constraints：["长征期间"]

### 复核填写

事实：

- `lm_tongdao`：长征期间召开了通道会议（中央负责人紧急会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_liping`：长征期间召开了黎平会议（中央政治局会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_houchang`：长征期间召开了猴场会议（中央政治局会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_zunyi`：长征期间召开了遵义会议（中央政治局扩大会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_zhaxi`：长征期间召开了扎西中央负责人会议
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_huili`：长征期间召开了会理会议（中央政治局扩大会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_lianghekou`：长征期间召开了两河口会议（中央政治局会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_luhua`：长征期间召开了芦花会议（中央政治局常委会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_shawu`：长征期间召开了沙窝会议（中央政治局会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_shawu_standing`：长征期间召开了沙窝中央政治局常委会议
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_maoergai`：长征期间召开了毛儿盖会议（中央政治局会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_axi`：长征期间召开了阿西紧急会议
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_ejie`：长征期间召开了俄界会议（中央政治局扩大会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_bangluozhen`：长征期间召开了榜罗镇会议（中央政治局常委会议）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `lm_wuqi`：长征期间召开了吴起镇中央政治局会议
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A06 · `holdout_multi_two_bombs_satellite`

- 分类：`multi_evidence`
- 分层：`holdout`
- 答案性：`answerable`
- 问题：梳理20世纪50—70年代中国“两弹一星”的主要节点。
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `two_bombs_plan_fact`：1956年制定1956—1967年科学技术发展远景规划，把原子能列为重点，并部署原子弹和导弹
- `two_bombs_missile_fact`：1960年第一枚探空火箭和近程导弹发射成功
- `two_bombs_atomic_fact`：1964年10月16日第一颗原子弹爆炸成功
- `two_bombs_hydrogen_theory_fact`：1965年中国科学家突破氢弹研制中的关键技术
- `two_bombs_hydrogen_fact`：1967年6月第一颗氢弹爆炸成功
- `two_bombs_satellite_fact`：1970年4月24日第一颗人造地球卫星“东方红一号”发射成功

证据组：

- `two_bombs_plan_1956`：1956年制定科学技术发展远景规划，部署原子弹和导弹
- `two_bombs_missile_1960`：1960年第一枚探空火箭和近程导弹发射成功
- `two_bombs_atomic_1964`：1964年10月16日第一颗原子弹爆炸成功
- `two_bombs_hydrogen_theory_1965`：1965年突破氢弹研制关键技术
- `two_bombs_hydrogen_1967`：1967年6月第一颗氢弹爆炸成功
- `two_bombs_satellite_1970`：1970年4月24日第一颗人造地球卫星发射成功

### 答案原文

```text
# 20世纪50—70年代中国“两弹一星”主要节点

## 一、决策与规划起点（1956年）

- 1956年，国家制定科学技术发展第一个远景规划，将原子能和平利用列为12项重点任务第一项，同时部署原子弹和导弹两个更大项目[E3]。
- 1956年4月，毛泽东在中央政治局扩大会议上表示“还要有原子弹”[E3]。
- 1956年4月，周恩来主持中央军委会议，听取钱学森关于发展导弹技术的规划设想[E3]。

## 二、管理体制的建立（1961—1965年）

- 1961年7月16日，党中央作出《关于加强原子能工业建设若干问题的决定》，要求集中力量加速原子能工业建设[E12]。
- 1962年11月3日，毛泽东对二机部“两年规划”报告作出指示：“要大力协同做好这件工作”[E12]。
- 1962年11月17日，中央十五人专门委员会成立，周恩来任主任，负责原子能工业建设和核武器研制试验的领导[E12]。
- 1965年，中央十五人专门委员会改称中央专门委员会，导弹和人造卫星研制统一纳入其领导范围[E12]。
- 1965年，中央专门委员会原则批准中国科学院《关于发展我国人造卫星工作规划方案建议》，计划在1970年至1971年发射第一颗人造卫星[E11]。

## 三、导弹与航天技术的阶段性突破（1960—1965年）

- 导弹和喷气技术经历仿制、改进到自行研制三个阶段[E11]。
- 1960年，第一枚探空火箭和近程导弹发射成功[E11]。
- 1964年，中近程导弹发射成功[E11]。
- 人造卫星随后进入工程研制阶段，代号“651”任务[E13]。

## 四、第一颗原子弹爆炸（1964年）

- 1964年4月，周恩来在会议上提出原子弹爆炸试验工作按9月10日前做好一切准备，试验时间由中央常委会决定，并要求国家气象局搞准气象预报[E20]。
- 1964年10月15日，周恩来亲自下达核装置就位命令，并打电话给刘杰询问核试验可能出现的结果，叮嘱做好以防万一的准备[E19]。
- 1964年10月16日15时，中国第一颗原子弹在西部地区爆炸成功；同日中国政府发表声明，宣布在任何时候、任何情况下都不会首先使用核武器[E19][E22]。

## 五、导弹与国防工业规划（1965—1966年）

- 1965年12月29日至31日，周恩来主持中央专委会第十四次会议，讨论国防工业争取两年时间完成三年任务等问题；发言中称“今年为两弹结合试验年，明年是导弹年”，会议批准了1966、1967两年规划，其中包括各种战术导弹、核潜艇、人造卫星等重大课题[E16]。

## 六、“文化大革命”时期的重大成果（1966—1971年）

- 1966年10月，首次成功进行发射导弹核武器试验[E15]。
- 1967年6月，成功爆炸第一颗氢弹[E15]。
- 1969年9月，首次成功进行地下核试验[E15]。
- 1970年4月14日，周恩来主持中央专委会会议，听取钱学森、李福泽、杨国宇、任新民、戚发轫等汇报，批准“东方红一号”卫星和“长征一号”火箭进入发射工作位置；20日通过罗舜初发出指示，要求做到“安全可靠，万无一失，准确入轨，及时预报”[E23]。
- 1970年4月24日，毛泽东对发射请示批示“照办”；同日晚上，中国成功发射第一颗人造地球卫星“东方红一号”，重173公斤[E21]。
- 1970年10月15日，因中国西部上空进行核试验，周恩来临时决定多留法国前总理德姆维尔一天，并说明中国进行“必要的和有限制的核试验”[E9]。
- 1971年3月，发射科学实验卫星“实践”一号[E15]。
- 1971年9月，第一艘核潜艇建成并试航成功，洲际火箭首次飞行试验基本成功[E15]。

## 资料限制

现有证据未覆盖1957年尖端武器研制启动、1958年第二机械工业部改名、1975年返回式卫星发射等节点的直接记载；提纲中关于1956年成立国防部航空工业委员会、5月中央作出发展导弹技术决策、10月成立国防部第五研究院、11月成立第三机械工业部等内容，在本轮证据中均无对应材料支持。1971年之后至70年代末的后续节点也缺乏直接材料。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E11 | cpc_history_volume_2 | 653 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十七章 国民经济调整任务的完成和“四个现代化”目标的提出 > 二、60年代前期社会主义建设的突出业绩 | 中央强调，两弹为主，导弹第一，要实现原子弹与导弹结合。在导弹和喷气技术领域，经过仿制、改进到自行研制三个阶段的飞跃。1960年，我国第一枚探空火箭和近程导弹发射成功。在近程导弹的研制取得重大进展的同时，我国又开始自行设计和研制中近程地对地导弹。1964年，中近程导弹发射成功。人造卫星的研制也经过了艰苦的过程。度过三年严重困难时期之后，中国科学院研制人造卫星的… |
| E3 | cpc_history_volume_2 | 651 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十七章 国民经济调整任务的完成和“四个现代化”目标的提出 > 二、60年代前期社会主义建设的突出业绩 | ……二、60年代前期社会主义建设的突出业绩以原子弹研制为核心的国防尖端科技的突破性进展在调整国民经济的同时，我国以研制原子弹、导弹、氢弹和人造地球卫星为核心的国防尖端科学技术，取得长足的进步和举世瞩目的成就。20世纪五六十年代，中国面对着严峻的国际形势。为了抵御帝国主义的武力威胁和打破大国的核讹诈、核垄断，党中央果断决定研制“两弹一星”，重点突破国防尖端技术… |
| E12 | cpc_history_volume_2 | 652 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十七章 国民经济调整任务的完成和“四个现代化”目标的提出 > 二、60年代前期社会主义建设的突出业绩 | 1961年7月16日，党中央作出《关于加强原子能工业建设若干问题的决定》。《决定》指出：“为了自力更生，突破原子能技术，加速我国原子能工业建设，中央认为有必要进一步缩短战线，集中力量，加强各有关方面对原子能工业建设的支援。”1962年11月3日，对二机部提出的争取在1964年、最迟在1965年上半年爆炸我国第一颗原子弹的规划的报告（即“两年规划”），毛泽东指… |
| E13 | cpc_history_volume_2 | 654 | 第二编 社会主义建设的全面展开和对中国建设社会主义道路的艰辛探索（1956年9月—1966年5月） > 第十七章 国民经济调整任务的完成和“四个现代化”目标的提出 > 二、60年代前期社会主义建设的突出业绩 | 颗人造卫星，命名为“东方红一号”。人造卫星进入工程研制阶段，代号为“651”任务。火箭技术的突破和人造卫星的研制，为我国的航天技术打下了坚实基础。以“两弹一星”为核心的国防尖端科技的辉煌成就，不仅是我国国防现代化的伟大成就，也是中国现代科学技术事业发展的重要标志。它带动了中国现代科学技术的发展，填补了许多学科空白，为我国实现技术发展的跨越积累了宝贵经验。邓小… |
| E15 | cpc_history_volume_2 | 919 | 第三编 “文化大革命”的内乱和林彪、江青两个反革命集团的覆灭（1966年5月—1976年10月） > 第二十八章 对“文化大革命”十年的基本分析 > 二、“文化大革命”时期社会主义建设事业的若干进展 | 1976年，我国又建成一条纵贯8个省市的全长1700多公里的中同轴1800路载波通信干线和连通全国20多个省市的微波通信干线。北京、上海还各建成一座卫星地面站。这些成果，大大增强了我国的交通运输能力、原油输送能力和邮电通信能力。科学技术方面也取得若干重要成就。1966年10月我国第一次成功地进行了发射导弹核武器的试验，1967年6月成功地爆炸了第一颗氢弹，1… |
| E16 | zhou_enlai_chronology_1949_1976 | 1114 | 1966年 | ……【1965 年12 月29 日－31 日】△主持中央专委会第十四次会议，讨论国防工业争取两年时间完成三年任务等问题。在发言中提出：原子弹爆炸成功是群策群力的结果。今年为两弹结合试验年，明年是导弹年，明年在导弹上要前进一步，希望后年要出更大的成果。任何事情都要一分为二，要总结经验，有所发现，有所发明，有所创造，有所前进，否则会落后。任何时候都要谦虚谨慎。号… |
| E9 | zhou_enlai_chronology_1949_1976 | 1308 | 1970年 | ……”【1970 年10 月7 日】△同西哈努克会谈，转述毛泽东对当前世界划分问题的看法：亚洲、非洲和拉丁美洲属于第一中间地带，而法国、意大利、西德、英国，包括加拿大和日本，则属于第二中间地带。△会见中岛健藏为团长的日本日中文化交流协会代表团，告知：中日乒乓球友谊赛，可以采取中国方面邀请日本乒乓球队来华进行的办法。【1970 年10 月8 日、10 日】△陪… |
| E19 | zhou_enlai_chronology_1949_1976 | 1067 | 1964年 | 附信说，“这次试验，决定采取公开宣传办法，以便主动地击破一切诬蔑和挑拨的阴谋，并利今后斗争。爆炸时间，前方还在作最后研讨，今晚若能定夺，当另告。”当日，亲自下达核装置就位的命令。【1964 年10 月15 日】△打电话给刘杰，询问核试验可能出现的结果，并叮嘱：要做好以防万一的准备工作。【1964 年10 月16 日】△十五时，中国第一颗原子弹在本国西部地区爆… |
| E20 | zhou_enlai_chronology_1949_1976 | 1046 | 1964年 | 在会上提出：原子弹爆炸试验工作按九月十日前做好一切准备，等待中央常委派骨干到现场，试验时间由中央常委会决定。请国家气象局负责把气象预报搞准。还提出，要防止事故，把革命干劲同科学精神结合起来。【1964 年4 月12 日】△为中共中央起草致陈毅电，提请在第二次亚非会议筹备会议上注意：“明年开会，地点如在非洲，也会出现开罗、亚的斯亚贝巴、阿尔及尔和某一黑非首都之… |
| E21 | mao_zedong_chronology_volume_9 | 299 | 1970年 | 颗卫星，早在一九六八年初得到主席、林副主席批准，直到今春才完成各项准备工作。三月底，运载火箭和卫星已运至基地，经检查测试，认为可行。四月中旬在京开会，经各方论证，认为可以发射。目前火箭和卫星已在发射阵地竖起，经检查测试，对发现的问题，均已解决。现拟同意千今夜发射，请主席批示。毛泽东批示：“照办。”同日晚上，我国成功发射第一颗人造地球卫星“东方红一号“，重一百… |
| E22 | cpc_history_volume_2 | 32 | 插图 | 1964年10月16日，我国第一颗原子弹爆炸成功。左图为原子弹爆炸后升起的蘑菇状烟云，右图为《人民日报》号外刊登原子弹爆炸成功的消息。 |
| E23 | zhou_enlai_chronology_1949_1976 | 1289 | 1970年 | 多数政治局成员同意由毛泽东担任国家主席，并将讨论意见报告毛泽东。毛泽东在报告上批：“我不能再作此事。此议不妥。”本月下旬，毛泽东回京后在中央政治局会议上再次表示他不当国家主席、不设国家主席。林彪仍然坚持原来的主张。【1970 年4 月13 日】△同越南民主共和国祖国阵线中央委员会主席团委员黄国越、老挝爱国战线党中央委员会总书记富米·冯维希会谈，讨论召开“三国… |

限制/说明：

- 部分证据覆盖未能完成模型核查。
- 尚缺证据：氢弹研制过程中关键技术突破的具体时间节点（如1965年突破氢弹原理）；导弹核武器试验的具体日期（1966年10月27日）；第一颗氢弹爆炸的具体日期（1967年6月17日）；地下核试验的具体日期（1969年9月23日）；核潜艇下水或服役的具体日期；洲际火箭首次飞行试验的具体日期；返回式遥感卫星的具体型号或名称；“两弹一星”功勋奖章表彰的23位科学家名单（证据E1中已列出，但未作为节点）；“两弹一星”精神的具体表述（证据E1中已提及，但未作为节点）；中央专委会在1965年后对导弹和人造卫星研制的具体领导活动；“651”任务的具体实施过程；“东方红一号”卫星的研制和发射准备细节
- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`retried`；retrieval_rounds：3
- retrieval_mode：`research_hybrid`；intent：`timeline`；coverage：`relevance`
- normalized_question：梳理20世纪50—70年代中国“两弹一星”的主要节点
- search_queries：["原子弹 研制 试验 时间节点", "氢弹 试验 时间节点", "导弹 研制 发射 节点", "人造卫星 东方红一号 1970", "两弹一星 主要节点 梳理"]
- entities：[{"type": "event", "text": "两弹一星", "canonical": "两弹一星"}]
- start_year/end_year：None / None
- constraints：["时间范围：20世纪50—70年代", "主题：两弹一星", "要求梳理主要节点"]

### 复核填写

事实：

- `two_bombs_plan_fact`：1956年制定1956—1967年科学技术发展远景规划，把原子能列为重点，并部署原子弹和导弹
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `two_bombs_missile_fact`：1960年第一枚探空火箭和近程导弹发射成功
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `two_bombs_atomic_fact`：1964年10月16日第一颗原子弹爆炸成功
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `two_bombs_hydrogen_theory_fact`：1965年中国科学家突破氢弹研制中的关键技术
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `two_bombs_hydrogen_fact`：1967年6月第一颗氢弹爆炸成功
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `two_bombs_satellite_fact`：1970年4月24日第一颗人造地球卫星“东方红一号”发射成功
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A07 · `dev_intersection_zhu_peng_command`

- 分类：`intersection_hard_negative`
- 分层：`development`
- 答案性：`answerable`
- 问题：朱德和彭德怀是否都担任过八路军总指挥？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `zhu_de_commander`：朱德任八路军总指挥
- `peng_dehuai_deputy`：彭德怀任八路军副总指挥

证据组：

- `zhu_peng_eighth_route_1937`：1937年8月红军改编为八路军，朱德任总指挥、彭德怀任副总指挥

### 答案原文

```text
**朱德和彭德怀都担任过八路军总指挥，但并非同时担任同一职务。**

- **朱德**：1937年8月25日，中共中央军委发布红军改编命令，朱德任八路军总指挥[E1][E2][E3][E4]。
- **彭德怀**：同日任命为八路军副总指挥[E1][E2][E3][E4]。

**关键说明**：证据中彭德怀的职务是“副总指挥”，而非“总指挥”。因此，严格来说，只有朱德担任过八路军总指挥，彭德怀担任的是副总指挥。若问题意在询问两人是否都进入八路军总指挥部领导层，则答案是肯定的；若严格按“总指挥”一职判断，则彭德怀未担任过该职。

**资料限制**：现有证据仅覆盖1937年8月改编命令及相关记载，未提供此后八路军（第十八集团军）总司令部职务变动的材料，无法进一步确认后续是否有人接任或改任总指挥一职。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | zhou_enlai_chronology_1949_1976 | 197 | 1937年 | ……【1937 年8 月25 日】△中共中央革命军事委员会主席毛泽东，副主席朱德、周恩来发布命令：根据与国民党及南京谈判结果，宣布主力红军改编为国民革命军第八路军，朱德为总指挥，彭德怀为副总指挥，任弼时为政治部主任，邓小平为副主任，叶剑英为参谋长，左权为副参谋长。第八路军下辖第一一五师，林彪为师长，聂荣臻为副师长，周昆为参谋长，罗荣桓为政训处主任，肖华为副主… |
| E2 | cpc_history_volume_1 | 599 | 下 册 > 第四编 党在全民族抗日战争时期（1937年7月—1945年8月） > 第十四章 争取实现全面抗战路线 > 一、日本发动全面侵华战争和抗日民族统一战线的建立 | ……8月25日，中共中央军委发布命令：红军改编为八路军，朱德任总指挥，彭德怀任副总指挥，叶剑英任参谋长，左权任副参谋长，任弼时任政治部主任，邓小平任政治部副主任。八路军全军约4.6万人，下辖三个师：第一一五师以原红军第一方面军为主编成，师长林彪，副师长聂荣臻，政训处主任罗荣桓，下辖第三四三旅（旅长陈光）、第三四四旅（旅长徐海东）；第一二〇师以原红军第二方面军… |
| E3 | deng_xiaoping_chronology_1904_1974_upper | 157 | 1937年 | ……会议决定成立由毛泽东、朱德、周恩来、彭德怀、任弼时、林彪、贺龙、刘伯承、林育英〔2]、徐向前、叶剑英组成的中共中央革命军事委员会，毛泽东为书记（实际称主席），朱德、周恩来为副书记。8月22日和左权致电朱德、彭德怀、任弼时：“一军团已于今晨出动。”“十五军团是否于二十七或二十四日继续出发请即告。”8月25日毛泽东、朱德、周恩来发出关于红军改编为国民革命军第… |
| E4 | mao_zedong_chronology_volume_2 | 22 | 1937年（7月-12月） | ……《为动员一切力量争取抗战胜利而斗争》（一九三七年八月二十五日）这个宣传提纲编入《毛泽东选集》。8 月22 日国民党政府军事委员会委员长蒋介石委任朱德、彭德怀为国民革命军第八路军总指挥、副总指挥。8 月25 日中共中央革命军事委员会主席毛泽东和副主席朱德、周恩来发出关千红军改编为国民革命军第八路军(1) 的命令。红军前敌总指挥部改为第八路军总指挥部，朱德任… |

限制/说明：

- 查询规划未通过（invalid_plan），使用保守计划处理原问题。
- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`fallback`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`hybrid_rrf`；intent：`general`；coverage：`relevance`
- normalized_question：朱德和彭德怀是否都担任过八路军总指挥？
- search_queries：[]
- entities：[{"type": "person", "text": "彭德怀", "canonical": "彭德怀"}, {"type": "person", "text": "朱德", "canonical": "朱德"}]
- start_year/end_year：None / None
- constraints：[]

### 复核填写

事实：

- `zhu_de_commander`：朱德任八路军总指挥
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `peng_dehuai_deputy`：彭德怀任八路军副总指挥
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A08 · `holdout_intersection_mao_zhu_jinggangshan`

- 分类：`intersection_hard_negative`
- 分层：`holdout`
- 答案性：`answerable`
- 问题：1928年4月朱德、陈毅率部与毛泽东领导的部队在井冈山会师后，合编成了什么部队？朱德和毛泽东分别担任什么职务？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `jinggangshan_meeting_fact`：1928年4月，朱德、陈毅率南昌起义保留的一部分部队和湘南起义农军与毛泽东领导的部队在宁冈砻市会师
- `jinggangshan_fourth_army`：会师后合编为工农革命军第四军（后改称红军第四军）
- `jinggangshan_roles`：朱德任军长，毛泽东任党代表

证据组：

- `jinggangshan_meeting_1928`：1928年4月朱毛井冈山会师后合编为工农革命军第四军

### 答案原文

```text
1928年4月井冈山会师后，两支部队合编为**工农革命军第四军**（后改称红军第四军）[E1][E2]。朱德任**军长**，毛泽东任**党代表**[E1][E2]。

**具体记载：**

- 根据中共湘南特委决定，两支部队编为工农革命军第四军，朱德任军长，毛泽东任党代表。下辖两个师一个教导大队：朱德兼第十师师长，宛希先任党代表；毛泽东兼代第十一师师长（本任张子清，因负伤未到任），何挺颖任党代表；陈毅任教导大队大队长[E1]。
- 会师后，毛泽东和朱德所率部队合编，成立工农革命军第四军（后改称红军第四军），朱德任军长，毛泽东任党代表，王尔琢任参谋长，下辖第十、第十一、第十二师（不久改编为四个团）[E2]。

**资料限制：** 现有证据对会师合编的记载一致，未提供其他不同说法或补充细节。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | mao_zedong_chronology_volume_1 | 247 | 1928年 | ……根据毛泽东的意见，确定了以罗霄山脉中段为根据地，发动群众斗争，实行土地革命，向北发展，向南游击的方针。4 月25 日中共江西省委致信中央：“据吉安来人报告，毛泽东部确与朱德部汇合(2) ，现已乘虚重复占领宁冈，并向永新方向发展。”“至于现时西南党的组织，因为没有人的关系，暂时将湘赣边特委建立，以毛泽东为书记，万安、永新、宁冈、遂川等地的工作由他指挥。”劝… |
| E2 | cpc_history_volume_1 | 330 | 上 册 > 第三编 党在土地革命战争时期（1927年8月—1937年7月） > 第八章 武装反抗国民党反动统治的斗争 > 四、井冈山的斗争和工农武装割据思想的提出 | ……1928年4月，朱德、陈毅率南昌起义保留下来的一小部分部队和湘南起义农军1万余人陆续转移到井冈山地区，与毛泽东领导的部队在宁冈砻市会师。会师后，毛泽东和朱德所率部队合编，成立工农革命军第四军（后改称红军第四军），朱德任军长，毛泽东任党代表，王尔琢任参谋长，下辖第十、第十一、第十二师（不久改编为四个团）。在这期间，还召开第四军党的第一次代表大会，成立了第四… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：1928年4月朱德、陈毅率部与毛泽东领导的部队在井冈山会师后，合编成了什么部队？朱德和毛泽东分别担任什么职务？
- search_queries：["1928年4月 朱德 陈毅 毛泽东 井冈山会师 合编 部队", "井冈山会师 合编 工农革命军 第四军 朱德 毛泽东 职务", "1928 井冈山 会师 红四军 军长 党代表"]
- entities：[{"type": "person", "text": "朱德", "canonical": "朱德"}, {"type": "person", "text": "陈毅", "canonical": "陈毅"}, {"type": "person", "text": "毛泽东", "canonical": "毛泽东"}, {"type": "event", "text": "井冈山会师", "canonical": "井冈山会师"}]
- start_year/end_year：1928 / 1928
- constraints：["1928年4月", "井冈山会师", "合编部队名称", "朱德职务", "毛泽东职务"]

### 复核填写

事实：

- `jinggangshan_meeting_fact`：1928年4月，朱德、陈毅率南昌起义保留的一部分部队和湘南起义农军与毛泽东领导的部队在宁冈砻市会师
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `jinggangshan_fourth_army`：会师后合编为工农革命军第四军（后改称红军第四军）
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `jinggangshan_roles`：朱德任军长，毛泽东任党代表
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A09 · `dev_constraint_korean_war_decision`

- 分类：`constraints_routing`
- 分层：`development`
- 答案性：`answerable`
- 问题：1950年10月，中共中央围绕出兵朝鲜作出了什么决策？请按时间顺序说明。
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `korean_oct2_telegram`：10月2日，毛泽东起草决定派遣志愿军入朝作战的长电；当天书记处会议未取得一致意见，电稿被搁置
- `korean_oct4_5_decision`：10月4日至5日，中央政治局扩大会议讨论并作出派遣中国人民志愿军入朝作战的决定
- `korean_oct8_order`：10月8日，毛泽东发布命令，将东北边防军组成中国人民志愿军，任命彭德怀为司令员兼政治委员
- `korean_oct19_entry`：10月19日，志愿军从安东、长甸河口、集安跨过鸭绿江入朝

证据组：

- `korean_war_decision_oct2`：10月2日毛泽东起草决定派遣志愿军入朝的长电
- `korean_war_decision_oct4_5`：10月4日至5日中央政治局扩大会议作出出兵决定
- `korean_war_order_oct8`：10月8日毛泽东发布命令组成中国人民志愿军
- `korean_war_entry_oct19`：10月19日志愿军跨过鸭绿江入朝

### 答案原文

```text
### 简明结论

1950年10月，中共中央围绕出兵朝鲜经历了从初步酝酿、内部意见分歧、赴苏磋商到最终定案的过程。核心决策是：**决定以“中国人民志愿军”名义出兵朝鲜，抗美援朝、保家卫国，并确定彭德怀挂帅、周恩来和林彪赴苏商谈军事援助与空军掩护问题；在斯大林表示苏联空军暂不能入朝掩护后，中央政治局仍于10月13日一致得出“应当参战，必须参战”的结论，最终确定志愿军于10月19日入朝作战**[E1][E2][E3][E7][E8][E9]。

---

### 按时间顺序说明

#### 10月4日—5日：中央政治局扩大会议讨论出兵，彭德怀支持出兵并接受挂帅

- **10月4日**，周恩来会见来北京的朝鲜劳动党中央常务委员、内务相朴一禹，就朝鲜作战的各项问题交换意见[E2]。
- **10月5日**，毛泽东在中南海颐年堂主持中共中央政治局扩大会议，继续讨论朝鲜战局和中国出兵援朝问题。讨论中仍有两种意见。周恩来支持出兵援朝的主张。彭德怀发言说：“出兵援朝是必要的，打烂了，等于解放战争晚胜利几年。”毛泽东针对林彪提出的美军高度现代化、还有原子弹等观点，表示“它有它的原子弹，我有我的手榴弹”[E1]。
- 同日，毛泽东与彭德怀谈话，彭德怀表示“赞成你出兵援朝的决策”，并接受毛泽东提出的由他挂帅的意见，表示“我服从中央的决定”[E1]。

#### 10月6日：周恩来主持党政军高级干部会议，部署志愿军入朝作战事宜

- **10月6日**，周恩来主持召开党政军高级干部会议，商议部署志愿军入朝作战事宜。他指出：“现在不是我们要不要打的问题，而是敌人逼着我们非打不可。”“党中央、毛主席决心已定，因此现在不是考虑出不出兵的问题，而是考虑出兵后如何去争取胜利的问题。”[E2]

#### 10月8日：毛泽东发布组成志愿军命令，周恩来、林彪赴苏

- **10月8日**，毛泽东发布《关于组成中国人民志愿军的命令》，任命彭德怀为中国人民志愿军司令员兼政治委员[E8]。
- 同日，毛泽东派周恩来、林彪代表中共中央去苏联，同斯大林商谈抗美援朝和中国如果出兵苏联给予军事物资援助，特别是向志愿军提供空军掩护的问题[E9]。周恩来代表中共中央，和林彪前往苏联同斯大林、莫洛托夫等会谈抗美援朝和苏联给予中国军事援助及向志愿军提供空军掩护问题[E8]。

#### 10月10日—11日：周恩来、林彪与斯大林会谈，苏方表示空军暂不能出动

- **10月10日**，周恩来抵达莫斯科[E8]。
- **10月11日**，周恩来和林彪抵达苏联高加索黑海边的克里米亚，同斯大林会谈。周恩来介绍了中共中央政治局会议讨论朝鲜局势和要否出兵援朝问题的情况，说明中国的实际困难，提出只要苏联同意出动空军给予空中掩护，中国就可以出兵援朝。斯大林表示可以完全满足中国抗美援朝所需的飞机、大炮、坦克等军事装备，但苏联空军尚未准备好，须待两个月或两个半月才能出动空军支持志愿军的作战[E8]。

#### 10月13日：中央政治局一致得出“应当参战，必须参战”的结论

- **10月13日**，毛泽东电告周恩来：中央政治局一致得出“应当参战，必须参战，参战利益极大，不参战损害极大”的结论[E7]。
- 苏联方面在得知中共中央已决定立即出兵后，同意向中国提供军事装备，并同意派遣苏联空军到中国帮助防空和训练，但苏联空军不入朝掩护志愿军作战[E7]。

#### 10月18日—19日：周恩来返京汇报，中央最终决定19日入朝作战

- **10月18日**，周恩来返回北京向中央汇报与斯大林会谈的情况。当晚，毛泽东向中国人民志愿军下达入朝作战的正式命令[E7]。
- 周恩来出席毛泽东主持的再次研究出兵援朝问题的中共中央会议，介绍同斯大林、莫洛托夫等会谈出兵援朝等问题的情况。鉴于斯大林虽不同意出动苏联空军入朝掩护志愿军作战，但毕竟答应给中国提供军事援助，会议决定中国人民志愿军按预定计划于**十九日**入朝作战[E3]。

---

### 资料限制说明

现有证据主要来自毛泽东年谱、周恩来年谱和《中国共产党历史》第二卷，覆盖了1950年10月中央决策的关键节点。但证据中缺少10月1日至3日中央书记处会议及政治局会议讨论出兵问题的直接记录，也缺少10月13日中央政治局会议本身的详细过程记载，仅能通过毛泽东致周恩来的电报间接确认其结论[E7]。此外，10月8日之前中央内部关于出兵与否的争论细节，证据仅显示“讨论中仍有两种意见”，未提供更多具体分歧内容[E1]。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | mao_zedong_chronology_volume_4 | 210 | 1950年 | 谈中国出兵援朝问题。毛泽东对彭德怀说：昨天你没来得及发言。我们确实存在严重困难，但是我们还有哪些有利条件呢？彭德怀说：昨天晚上我反复考虑，赞成你出兵援朝的决策。毛泽东问：你看，出兵援朝谁挂帅合适？彭德怀反问：中央不是已决定派林彪同志去吗？毛泽东谈了林彪的情况后说：我们的意见，这担子，还得你来挑，你思想上没有这个准备吧？彭德怀表示：我服从中央的决定。毛泽东说：… |
| E2 | zhou_enlai_chronology_1949_1976 | 474 | 1950年 | △会见来北京的朝鲜劳动党中央常务委员、内务相朴一禹，就朝鲜作战的各项问题交换意见。【1950 年10 月4 日】△致电倪志亮：“根据目前情况，我武官观察组不要去三八线以南，应分为两个小组：一个调查平壤附近度平壤安东线、平壤辑安线的各种情况；一个调查平壤元山线及其以北山区的各种情况，平壤元山线至三八线之间的情况如有可能亦应略作调查，但勿深入。”【1950 年1… |
| E3 | zhou_enlai_chronology_1949_1976 | 476 | 1950年 | ……△出席毛泽东主持的再次研究出兵援朝问题的中共中央会议，介绍同斯大林、莫洛托夫等会谈出兵援朝等问题的情况。鉴于斯大林虽不同意出动苏联空军入朝掩护志愿军作战，但毕竟答应给中国提供军事援助，会议决定中国人民志愿军按预定计划于十九日入朝作战。△致电联合国，抗议美国侵朝飞机十月十三日、十四日多次侵入中国领空，要求安理会制止美国扩大侵略的行为。【1950 年10 月… |
| E7 | cpc_history_volume_2 | 108 | 第一编 中华人民共和国的成立和向社会主义过渡的实现（1949年10月—1956年9月） > 第二章 抗美援朝战争 > 二、抗美援朝 保家卫国 | 10月8日，周恩来乘飞机赶赴莫斯科。访问苏联期间，他同斯大林、莫洛托夫等商谈了中国出动志愿军抗美援朝的问题，苏联给予军事援助并向志愿军提供空军掩护等问题。由于斯大林在磋商开始时表示，苏联空军尚未作好准备，要待两个月或两个半月之后才能出动，中国方面也再次考虑了出兵时机。10月13日，毛泽东电告周恩来：中央政治局一致得出“应当参战，必须参战，参战利益极大，不参战… |
| E8 | zhou_enlai_chronology_1949_1976 | 475 | 1950年 | 【1950 年10 月8 日】△代表中共中央，和林彪前往苏联同斯大林、莫洛托夫等会谈抗美援朝和苏联给予中国军事援助及向志愿军提供空军掩护问题。△毛泽东发布《关于组成中国人民志愿军的命令》，任命彭德怀为中国人民志愿军司令员兼政治委员。【1950 年10 月10 日】△抵达莫斯科。【1950 年10 月11 日】△午后，和林彪抵达苏联高加索黑海边的克里米亚，同在… |
| E9 | mao_zedong_chronology_volume_4 | 213 | 1950年 | 会商与中国人民志愿军进入朝鲜境内作战有关的诸项问题。（彭、高二同志本日由北京去沈阳。）”同日派周恩来、林彪代表中共中央去苏联，同斯大林商谈抗美援朝和中国如果出兵(1) 苏联给予军事物资援助，特别是向志愿军提供空军掩护的问题。10 月9 日起草周恩来致倪志亮并告高岗电：“中央己委托高岗同志负责处理一切有关援助朝鲜同志的问题，嗣后关千此类事务均向高岗同志直接接洽… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：1950年10月，中共中央围绕出兵朝鲜作出了什么决策？请按时间顺序说明。
- search_queries：["1950年10月 中共中央 出兵朝鲜 决策", "1950年10月 抗美援朝 决策 时间顺序", "中共中央 出兵朝鲜 1950年10月 会议"]
- entities：[{"type": "organization", "text": "中共中央", "canonical": "中国共产党中央委员会"}, {"type": "event", "text": "出兵朝鲜", "canonical": "抗美援朝出兵决策"}]
- start_year/end_year：1950 / 1950
- constraints：["1950年10月", "按时间顺序说明"]

### 复核填写

事实：

- `korean_oct2_telegram`：10月2日，毛泽东起草决定派遣志愿军入朝作战的长电；当天书记处会议未取得一致意见，电稿被搁置
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `korean_oct4_5_decision`：10月4日至5日，中央政治局扩大会议讨论并作出派遣中国人民志愿军入朝作战的决定
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `korean_oct8_order`：10月8日，毛泽东发布命令，将东北边防军组成中国人民志愿军，任命彭德怀为司令员兼政治委员
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `korean_oct19_entry`：10月19日，志愿军从安东、长甸河口、集安跨过鸭绿江入朝
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A10 · `holdout_constraint_nanchang_uprising_background`

- 分类：`constraints_routing`
- 分层：`holdout`
- 答案性：`answerable`
- 问题：只依据《中国共产党历史》第一卷，说明1927年南昌起义是在什么背景下发动的。
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

必要事实：

- `nanchang_failure_context`：1927年大革命失败后，革命处于严重失败形势；中国共产党面临要不要坚持革命、如何坚持革命的问题
- `nanchang_jiujiang_preparation`：1927年7月中旬，中共中央临时政治局常委会派李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织党掌握和影响的国民革命军一部分，联合张发奎重回广东
- `nanchang_independent_decision`：7月20日发现张发奎站在汪精卫一边后，李立三等提议独立发动反对南京和武汉国民党政府的军事行动，即南昌起义
- `nanchang_front_committee`：7月27日周恩来抵南昌成立前委，决定7月30日起义；后因张国焘主张等待张发奎同意被前委否决，7月31日决定8月1日起义

证据组：

- `nanchang_background_failure_1927`：大革命失败后的严峻形势和要不要坚持革命的问题
- `nanchang_background_jiujiang_1927`：1927年7月中旬派李立三、邓中夏、谭平山、恽代英等赴九江准备起义
- `nanchang_background_independent_1927`：7月20日发现张发奎站在汪精卫一边，李立三等提议独立发动南昌起义
- `nanchang_background_front_committee_1927`：7月27日周恩来到南昌成立前委并决定7月30日起义
- `nanchang_background_aug1_1927`：7月31日前委决定8月1日起义

### 答案原文

```text
**简明结论**

依据《中国共产党历史》第一卷，南昌起义是在大革命遭受严重失败的形势下，党为回答“要不要坚持革命、如何坚持革命”而发动的武装反抗行动。直接背景是：中共中央原拟联合张发奎回广东建立根据地，因发现张发奎已站在汪精卫一边，遂放弃依赖张发奎的计划，决定独立发动南昌起义[E1]。

**一、总背景：革命遭受严重失败**

南昌起义发动时，革命正处在“遭受严重失败的极为严峻的形势下”，党面临“要不要坚持革命”“如何坚持革命”两个根本性问题。党以武装起义的实际行动对此作出回答，目的是“使革命走向复兴”[E1]。

**二、直接起因：联合张发奎计划失败**

1927年7月中旬，中共中央临时政治局常务委员会派遣李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织党掌握和影响的国民革命军一部分力量，联合第二方面军总指挥张发奎重回广东，建立新的革命根据地，实行土地革命[E1]。

7月20日，因发现张发奎已经站在汪精卫一边，李立三等立即抛弃依赖张发奎的计划，提议独立发动反对南京和武汉国民党政府的军事行动，即南昌起义。中央临时政治局常委会获悉后，正式确定在南昌举行武装起义的部署，并向共产国际报告了起义计划[E1]。

**三、起义决策的确认与执行**

7月27日，周恩来从武汉经九江到达南昌。根据中央决定，中共前敌委员会成立，由周恩来、李立三、恽代英、彭湃组成，周恩来任书记。前委当即决定于7月30日起义[E2]。

起义准备期间，中共中央收到共产国际电报，电报称“如果有成功的把握，我们认为你们的计划是可行的”。中共中央分析形势后认为南昌起义有成功的把握，决定派张国焘以中央代表身份赴南昌传达指示[E2]。

7月30日晨，张国焘赶到南昌，因仍对张发奎存有幻想，主张一定要得到张发奎同意后方能举行起义，这一意见被前委否决。7月31日，前委决定8月1日凌晨举行起义[E2]。

**四、起义的军事力量基础**

南昌起义的主要军事力量是“党在大革命时期培植和给予重要影响的正规革命武装的主要部分”。其中，国民革命军第二方面军所辖的第十一军第二十四师由共产党人叶挺指挥；第四军第二十五师第七十三、第七十五团也是党掌握和影响的部队[E1][E2]。

8月1日凌晨，在以周恩来为首的前委领导下，贺龙、叶挺、朱德、刘伯承等率领在党直接掌握和影响下的军队2万余人，举行南昌起义[E2]。

**资料限制**

现有证据仅覆盖《中国共产党历史》第一卷中关于南昌起义背景的直接叙述，未包含起义前更早时期国共关系演变、四一二政变等更宏观背景的专门段落，因此上述说明以证据明确记载的内容为限。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | cpc_history_volume_1 | 308 | 上 册 > 第三编 党在土地革命战争时期（1927年8月—1937年7月） > 第八章 武装反抗国民党反动统治的斗争 > 二、各地的武装起义 | 二、各地的武装起义南昌起义在革命遭受严重失败的极为严峻的形势下，要不要坚持革命？如何坚持革命？这是摆在中国共产党面前的两个带根本性的问题。党以武装起义的实际行动，对此作出了初步而又明确的回答。为了使革命走向复兴，党领导人民进行艰苦卓绝的斗争。1927年7月中旬，中共中央临时政治局常务委员会派遣李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织中国共产党掌握… |
| E2 | cpc_history_volume_1 | 309 | 上 册 > 第三编 党在土地革命战争时期（1927年8月—1937年7月） > 第八章 武装反抗国民党反动统治的斗争 > 二、各地的武装起义 | 党在大革命时期培植和给予重要影响的正规革命武装的主要部分，也是举行南昌起义的主要军事力量。7月27日，周恩来从武汉经九江到达南昌。根据中央的决定，中共前敌委员会（简称前委）成立，由周恩来、李立三、恽代英、彭湃组成，周恩来任书记。前委当即决定于7月30日起义。正当起义准备工作紧张进行时，中共中央收到共产国际根据联共（布）中央政治局决定发来的电报。电报指出：“如… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：只依据《中国共产党历史》第一卷，说明1927年南昌起义是在什么背景下发动的。
- search_queries：["《中国共产党历史》第一卷 南昌起义 背景", "1927年 南昌起义 发动 背景", "大革命失败 南昌起义 背景"]
- entities：[{"type": "event", "text": "南昌起义", "canonical": "南昌起义"}, {"type": "document", "text": "《中国共产党历史》第一卷", "canonical": "《中国共产党历史》第一卷"}]
- start_year/end_year：1927 / 1927
- constraints：["只依据《中国共产党历史》第一卷", "1927年"]

### 复核填写

事实：

- `nanchang_failure_context`：1927年大革命失败后，革命处于严重失败形势；中国共产党面临要不要坚持革命、如何坚持革命的问题
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `nanchang_jiujiang_preparation`：1927年7月中旬，中共中央临时政治局常委会派李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织党掌握和影响的国民革命军一部分，联合张发奎重回广东
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `nanchang_independent_decision`：7月20日发现张发奎站在汪精卫一边后，李立三等提议独立发动反对南京和武汉国民党政府的军事行动，即南昌起义
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______
- `nanchang_front_committee`：7月27日周恩来抵南昌成立前委，决定7月30日起义；后因张国焘主张等待张发奎同意被前委否决，7月31日决定8月1日起义
  - 事实状态：[ ] covered　[ ] partial　[ ] missing　[ ] contradicted　[ ] unknown
  - 引用支持：[ ] supported　[ ] partial　[ ] unsupported　[ ] unknown　[ ] not_applicable
  - 答案摘录/引用：______

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- source_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- time_constraint：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal / scope_explanation：可答题目通常为 `not_applicable`，除非回答涉及拒答或范围说明

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A11 · `dev_refusal_marriage_law_concubinage`

- 分类：`refusal_boundary`
- 分层：`development`
- 答案性：`unanswerable`
- 问题：1950年《婚姻法》是否允许纳妾？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

证据组：无（拒答题不声明正向证据）

拒答口径：

- 类型：`false_premise`
- 正确口径：1950年《婚姻法》第二条规定禁止重婚、纳妾、童养媳、干涉寡妇婚姻自由、借婚姻关系索取财物。

### 答案原文

```text
**结论：1950年《婚姻法》不允许纳妾。** 该法明确规定实行“一夫一妻”的新民主主义婚姻制度，从制度上排除了纳妾的合法性[E2]。

**依据要点：**

- **法律条文直接规定一夫一妻**：1950年4月30日公布的《中华人民共和国婚姻法》规定：“废除包办强迫、男尊女卑、漠视子女利益的封建主义婚姻制度。实行男女婚姻自由、**一夫一妻**、男女权利平等、保护妇女和子女合法利益的新民主主义婚姻制度。”[E2]

- **立法过程**：该法于1950年4月13日经中央人民政府委员会第七次会议审议通过，4月30日由毛泽东签发命令公布，自5月1日起施行，是新中国成立后制定的第一部基本法律[E1]。

**资料限制：** 现有证据仅包含婚姻法条文中关于“一夫一妻”的原则性规定，未提供该法对纳妾问题的专门解释、实施细则或司法实践材料。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | cpc_history_volume_2 | 135 | 第一编 中华人民共和国的成立和向社会主义过渡的实现（1949年10月—1956年9月） > 第三章 完成反封建的土地改革和各项民主改革 > 二、全社会的民主改革运动 | 中央人民政府成立后，政务院政治法律委员会同中华全国民主妇女联合会【96】等有关部门召开联席会议，多次就新婚姻法草案的各章各条进行研究、讨论和修改。1950年4月13日，中央人民政府委员会举行第七次会议，审议通过了《中华人民共和国婚姻法（草案）》。4月30日，毛泽东主席签发命令公布《中华人民共和国婚姻法》，自5月1日起施行。这是新中国成立后制定的第一部基本法律… |
| E2 | mao_zedong_chronology_volume_4 | 132 | 1950年 | ……婚姻法规定：“废除包办强迫、男尊女卑、漠视子女利益的封建主义婚姻制度。实行男女婚姻自由、一夫一妻、男女权利平等、保护妇女和子女合法利益的新民主主义婚姻制度。”同日将邓子恢四月二十五日关于起草土改条例意见的电报转发饶漱石，作为起草土改法令的参考，并征询他的意见。邓子恢的电报着重申述了主张动富农出租土地的理由。同日复信田厚卿：“四月二十二日来信收到。吾兄既与… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：1950年《婚姻法》是否允许纳妾？
- search_queries：["1950年婚姻法 纳妾", "1950 婚姻法 妾 规定"]
- entities：[{"type": "document", "text": "1950年《婚姻法》", "canonical": "中华人民共和国婚姻法"}, {"type": "event", "text": "纳妾", "canonical": "纳妾"}]
- start_year/end_year：1950 / 1950
- constraints：["1950年《婚姻法》", "是否允许纳妾"]

### 复核填写

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- scope_explanation：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

## A12 · `holdout_refusal_un_seat_timing`

- 分类：`refusal_boundary`
- 分层：`holdout`
- 答案性：`unanswerable`
- 问题：中国是在1972年尼克松访华之后才恢复联合国合法席位的吗？
- evidence_status：`partial`；llm_status：`used`；uncited_claims：0

证据组：无（拒答题不声明正向证据）

拒答口径：

- 类型：`false_premise`
- 正确口径：1971年10月25日，第二十六届联合国大会通过2758号决议，恢复中华人民共和国在联合国的一切合法权利；尼克松访华是1972年2月。

### 答案原文

```text
**不是。** 中国恢复联合国合法席位发生在1971年，早于尼克松1972年2月访华。

**关键时间顺序：**

- **1971年11月15日**，以外交部副部长乔冠华为团长的中国代表团首次出席联合国大会，标志着中国在联合国合法席位的恢复。[E1]
- **1972年2月21日**，美国总统尼克松抵达北京开始访华，标志中美关系正常化进程正式开始。[E1]
- **1972年2月28日**，中美《联合公报》在上海发表，两国开始走向关系正常化。[E2]

**资料限制：** 现有证据明确显示联合国席位恢复（1971年11月）先于尼克松访华（1972年2月），但未提供1971年10月联合国大会表决恢复中国席位当天的具体记录，也未包含中国恢复联合国合法席位与尼克松访华之间因果关系的直接论述。
```

### 引用

| 引用 | 文档 | PDF 页 | 章节 | 引文摘要 |
|---|---|---|---|---|
| E1 | cpc_history_volume_2 | 850 | 第三编 “文化大革命”的内乱和林彪、江青两个反革命集团的覆灭（1966年5月—1976年10月） > 第二十五章 外交战略的转变和对外关系的新局面 > 三、对外关系新局面的出现 | ……1971年11月15日，以外交部副部长乔冠华为团长、黄华为副团长的中国代表团肩负全国人民的重托，首次出现在联合国大会上，受到大多数国家代表极其热烈的欢迎。乔冠华在大会上讲话，代表中国政府对为恢复中国在联合国的合法权利进行了不懈努力的众多友好国家表示衷心的感谢，并全面阐述了中国政府在一系列重大问题上的原则立场。中国在联合国合法席位的恢复，是中国外交工作的一… |
| E2 | zhou_enlai_chronology_1949_1976 | 1364 | 1972年 | 【1972 年2 月26 日】△凌晨，中美联合公报草案基本谈定。上午，周恩来在机场休息室同尼克松举行第二次大范围会谈。之后，又陪同尼克松和夫人前往杭州和上海访问。【1972 年2 月27 日】△中美双方就《联合公报》达成协议。双方在中外记者招待会上公布中美《联合公报》内容。【1972 年2 月28 日】△在上海锦江饭店同尼克松举行第五次限制性会谈。随后，尼克… |

限制/说明：

- 答案仅代表当前已入库文献，不等同于完整历史结论。

### 过程

- planner_status：`used`
- reflection_status：`skipped`；retrieval_rounds：1
- retrieval_mode：`planned_hybrid_rrf`；intent：`event_overview`；coverage：`relevance`
- normalized_question：中国恢复联合国合法席位是否发生在1972年尼克松访华之后？
- search_queries：["尼克松访华 1972年 时间", "恢复中华人民共和国在联合国的一切合法权利 决议"]
- entities：[{"type": "event", "text": "恢复联合国合法席位", "canonical": "中华人民共和国恢复在联合国的合法席位"}, {"type": "event", "text": "尼克松访华", "canonical": "尼克松访华"}, {"type": "person", "text": "尼克松", "canonical": "理查德·尼克松"}]
- start_year/end_year：1972 / 1972
- constraints：["比较恢复联合国合法席位与1972年尼克松访华的先后关系"]

### 复核填写

维度：

- citation_support：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- safe_refusal：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- scope_explanation：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- routing：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable

过程：

- query understanding：[ ] pass　[ ] fail　[ ] unknown　[ ] not_applicable
- 理由：______

---

