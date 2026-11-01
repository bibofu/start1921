# LLM judge 人工校准队列（C01–C12）

> 2026-11-01 生成。当前 32 题答案/引用判断是 `agent_review`（LLM fact/citation judge 预标 + 规则归类），不是 `human_review`。本队列用于人工校准 judge。
>
> judge：`fact-coverage-v1` + `citation-entailment-v1`，模型 `deepseek-v4-pro`。

回复格式：

```text
C01 fact lm_tongdao missing 同意
C01 fact lm_zunyi covered 改 partial，理由：...
C01 citation pass 改 fail，理由：...
C01 process fail 同意
C01 note 重点核对结论
```

## 总览

| 编号 | 题 | 事实 covered/partial/missing | citation | process |
|---|---|---|---|---|
| C01 | `dev_multi_long_march_meetings` | 2/2/11 | fail | fail |
| C02 | `dev_constraint_history_isolation` | 3/1/6 | fail | pass |
| C03 | `holdout_multi_two_bombs_satellite` | 4/1/1 | fail | pass |
| C04 | `dev_multi_zhou_periods` | 3/1/3 | fail | pass |
| C05 | `holdout_intersection_positive` | 1/1/1 | fail | fail |
| C06 | `holdout_exact_founding_ceremony` | 1/0/1 | pass | pass |
| C07 | `dev_refusal_einstein` | 0/0/0 | not_applicable | pass |
| C08 | `holdout_exact_date` | 0/0/2 | fail | pass |
| C09 | `holdout_semantic_observation` | 0/0/5 | fail | pass |
| C10 | `dev_exact_deng_1954` | 2/0/0 | pass | pass |
| C11 | `holdout_semantic_angang_constitution` | 4/0/0 | pass | pass |
| C12 | `dev_intersection_zhu_peng_command` | 2/0/0 | pass | fail |

## C01 · `dev_multi_long_march_meetings`

- 问题：梳理长征期间，召开的会议。
- 答案性：`answerable`；split：`development`；类别：`multi_evidence`
- 当前 citation_support：**fail**；process：**fail**
- 重点：重点：吴起镇团以上干部会议与批准榜罗镇决策的会议是否被合并；1935-12 瓦窑堡是否超出“长征期间”。

事实核对：

- `lm_tongdao`：当前 **covered** / supported
  - LLM 理由：回答明确提到“通道紧急会议（1934年12月12日）”，并描述中共中央负责人在湖南通道举行紧急会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_liping`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及黎平会议，仅在资料限制部分指出“黎平会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_houchang`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及猴场会议，仅在资料限制部分指出“猴场会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_zunyi`：当前 **covered** / supported
  - LLM 理由：回答明确提到“遵义会议（1935年1月）”，并描述为“扩大的中央政治局会议”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_zhaxi`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及扎西中央负责人会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_huili`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及会理会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_lianghekou`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及两河口会议，仅在资料限制部分指出“两河口会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_luhua`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及芦花会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_shawu`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及沙窝会议，仅在资料限制部分指出“沙窝会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_shawu_standing`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及沙窝中央政治局常委会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_maoergai`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及毛儿盖会议，仅在资料限制部分指出“毛儿盖会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_axi`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及阿西紧急会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_ejie`：当前 **partial** / partial
  - LLM 理由：回答明确提到“俄界会议（1935年）”，并说明是长征途中召开的会议，虽未注明“中央政治局扩大会议”但提及会议本身。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_bangluozhen`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及榜罗镇会议，仅在资料限制部分指出“榜罗镇会议……缺乏直接记载”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `lm_wuqi`：当前 **partial** / partial
  - LLM 理由：回答提及“吴起镇相关会议（1935年10月）”，但未明确指定为中央政治局会议，仅描述为“会议”和“另一次会议”，无法确认是中央政治局会议。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**fail**
- judge 列出的未支持主张：
  - 吴起镇相关会议（1935年10月）
  - 毛泽东出席陕甘支队团以上干部会议并作报告，指出胜利到达目的地、革命形势已到拂晓，并提出军事政治教育、争取群众、扩大红军、改善生活等当前任务。另有一次会议批准了榜罗镇会议的战略决策，宣告中央红军长征结束；与会者一致同意毛泽东的报告和结论。但该会议名称在证据中未明确记载[E14]。
- judge 理由：回答将毛泽东出席陕甘支队团以上干部会议并作报告与批准榜罗镇会议战略决策的会议描述为同一次会议，但引文[E14]显示毛出席团以上干部会议是10月25日，而批准榜罗镇会议战略决策的会议是另一次会议，两者并非同一会议，引文不支持该合并描述。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：存在未获引用支持的主张：吴起镇相关会议（1935年10月）；毛泽东出席陕甘支队团以上干部会议并作报告，指出胜利到达目的地、革命形势已到拂晓，并提出军事政治教育、争取群众、扩大红军、改善生活等当前任务。另有一次会议批准了榜罗镇会议的战略决策，宣告中央红军长征结束；与会者一致同意毛泽东的报告和结论。但该会议名称在证据中未明确记载[E14]。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **fail**；理由：题目限定长征期间，但答案纳入了1935年12月瓦窑堡会议，超出长征结束时间。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**fail**；理由：计划时间窗过宽（1934—1936），答案纳入瓦窑堡会议；查询理解未收窄到长征结束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C02 · `dev_constraint_history_isolation`

- 问题：详细介绍淮海战役。
- 答案性：`answerable`；split：`development`；类别：`constraints_routing`
- 当前 citation_support：**fail**；process：**pass**
- 重点：重点：E10 引文实际包含“起承前启后/敌占相对优势”；E5 只是示意图标题；E8/E6 是否支持对应主张。

事实核对：

- `battle_geography`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及淮海战役以徐州为中心，东起海州、西至商丘、北起临城、南达淮河的地理范围。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_forces`：当前 **partial** / partial
  - LLM 理由：回答未给出解放军参战兵力约60万人的数字，仅描述了国民党军队兵力。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_planning`：当前 **covered** / supported
  - LLM 理由：回答提到粟裕提出淮海战役建议，中央军委接受并于10月11日拟定第一阶段集中歼灭黄百韬兵团的方针。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_command`：当前 **covered** / supported
  - LLM 理由：回答明确提到总前委由刘伯承、陈毅、邓小平、粟裕、谭震林组成，邓小平任书记，统一领导作战。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_stage_one`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及第一阶段具体时间和碾庄圩歼灭黄百韬兵团约10万人的细节。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_stage_two`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及第二阶段双堆集歼灭黄维兵团约12万人的事实。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_stage_three`：当前 **covered** / supported
  - LLM 理由：回答提到1949年1月6日总攻，1月10日全歼邱清泉、李弥兵团约20万人，俘杜聿明、击毙邱清泉，吻合第三阶段及战役结束。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_result`：当前 **missing** / not_applicable
  - LLM 理由：回答未提到战役历时66天、歼灭国民党军队55.5万人的数字。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_impact`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及胜利使长江以北华东、中原基本解放，威胁南京、上海，为渡江作战创造条件。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `battle_civilian_support`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及人民群众支前的作用和陈毅“小车推出来的胜利”的概括。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**fail**
- judge 列出的未支持主张：
  - 淮海战役是解放战争战略决战三大战役中起承前启后作用的第二个大战役，也是三大战役中在战场兵力对比上敌占相对优势的情况下进行的一次大规模歼灭战[E10]。
  - 战役时间为1948年11月至1949年1月[E5]。
  - 徐州“剿总”总司令刘峙、副总司令杜聿明指挥黄百韬、邱清泉、李弥、孙元良四个兵团，和冯治安、李延年、刘汝明、周暑的四个绥靖区部队，连同从华中赶来增援的黄维兵团，以及战役期间自东北战场撤到蚌埠的两个军、自长江中游增援到浦口的两个军，总兵力近80万人，其中大多是国民党军队的主力和精锐部队[E8]。
  - 1949年1月6日，华东野战军发起对杜聿明部的总攻，经四天激战，于1月10日全歼邱清泉、李弥两个兵团约20万人，俘杜聿明，击毙邱清泉，仅李弥等少数人逃脱。至此，淮海战役以大获全胜而结束[E10]。
  - 从更宏观的角度看，淮海战役与辽沈、平津并列为三大战役，三大战役以后严重的战争时期已经过去[E6]。
- judge 理由：回答中多处事实主张所引用的材料并未直接支持其陈述。如[E10]仅记载战役结束及“大获全胜”，未提及“起承前启后”“敌占相对优势”等评价；[E5]仅为示意图标题，未明确战役时间范围；[E8]引文内容与回答表述存在出入，且未显示“相对优势”结论；[E6]的引文出处与内容不符。因此判定为未获支持。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：存在未获引用支持的主张：淮海战役是解放战争战略决战三大战役中起承前启后作用的第二个大战役，也是三大战役中在战场兵力对比上敌占相对优势的情况下进行的一次大规模歼灭战[E10]。；战役时间为1948年11月至1949年1月[E5]。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **not_applicable**；理由：题目没有可核时间约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C03 · `holdout_multi_two_bombs_satellite`

- 问题：梳理20世纪50—70年代中国“两弹一星”的主要节点。
- 答案性：`answerable`；split：`holdout`；类别：`multi_evidence`
- 当前 citation_support：**fail**；process：**pass**
- 重点：重点：E7 是 1999 年表彰页，不是 1958 年改名；E21 引文实际写了“同日晚上成功发射”；E3 是否支持 1965 年专委会改称及卫星纳入。

事实核对：

- `two_bombs_plan_fact`：当前 **covered** / supported
  - LLM 理由：回答中写明1956年国家制定科学技术远景规划，将原子能列为重点并部署原子弹和导弹两个项目。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `two_bombs_missile_fact`：当前 **covered** / supported
  - LLM 理由：回答中写明1960年第一枚探空火箭和近程导弹发射成功。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `two_bombs_atomic_fact`：当前 **covered** / supported
  - LLM 理由：回答中写明1964年10月16日第一颗原子弹爆炸成功。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `two_bombs_hydrogen_theory_fact`：当前 **missing** / not_applicable
  - LLM 理由：回答中未提到1965年中国科学家突破氢弹研制中的关键技术。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `two_bombs_hydrogen_fact`：当前 **covered** / supported
  - LLM 理由：回答中写明1967年6月第一颗氢弹爆炸成功。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `two_bombs_satellite_fact`：当前 **partial** / partial
  - LLM 理由：回答中写明1970年4月成功发射第一颗人造地球卫星“东方红一号”，且未对日期24日产生矛盾，可视为覆盖。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**fail**
- judge 列出的未支持主张：
  - 1958年2月，二届全国人大五次会议决定将第三机械工业部改名为第二机械工业部，任务和职能不变[E7]。
  - 1965年，中央十五人专门委员会改称中央专门委员会，导弹和人造卫星研制统一纳入其领导范围[E3]。
  - 1970年4月，毛泽东对发射请示批示“照办”；同日晚，中国成功发射第一颗人造地球卫星“东方红一号”，重173公斤[E21]。
- judge 理由：回答中有三条主张所标注的引文不支持相关事实：E7未提及1958年人大改名内容；E3虽提及改称但未说明导弹和人造卫星纳入领导范围；E21中毛泽东批示“照办”与卫星发射成功的时间同日，但该主张用分号连接并标注E21，可能让人误以为E21直接记载“同日晚发射成功”，而E21原文没有明确发射时间在同日晚，故列为未获支持。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：存在未获引用支持的主张：1958年2月，二届全国人大五次会议决定将第三机械工业部改名为第二机械工业部，任务和职能不变[E7]。；1965年，中央十五人专门委员会改称中央专门委员会，导弹和人造卫星研制统一纳入其领导范围[E3]。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C04 · `dev_multi_zhou_periods`

- 问题：按时间和主题梳理周恩来从1954年至1956年的主要经历，并说明这三年工作重点的变化。
- 答案性：`answerable`；split：`development`；类别：`multi_evidence`
- 当前 citation_support：**fail**；process：**pass**
- 重点：重点：E2 引文片段是否包含 4 月 19 日和“中央人民政府主席毛泽东任命”完整关系。

事实核对：

- `zhou_1954_geneva`：当前 **covered** / supported
  - LLM 理由：回答提到1954年出席日内瓦会议，开展国际和平外交，符合事实。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_1954_government`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及1954年9月任国务院总理兼外交部长、12月当选全国政协主席。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_1955_bandung`：当前 **covered** / supported
  - LLM 理由：回答提到1955年4月出席亚非会议（万隆会议），强调求同存异、争取团结合作。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_1955_plan`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及1955年6月向全国人大常委会说明第一个五年计划草案。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_1956_intellectuals`：当前 **partial** / partial
  - LLM 理由：回答未提及1956年1月作知识分子问题报告，未提及知识分子绝大部分是工人阶级的一部分。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_1956_balance`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及1956年6月针对经济建设急躁冒进提出压缩支出、基建，主张综合平衡。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `zhou_synthesis`：当前 **covered** / supported
  - LLM 理由：回答概括了1954年和平外交与国家制度建设、1955年亚非团结与国内建设、1956年国内建设探索，符合综合概述。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**fail**
- judge 列出的未支持主张：
  - 4月19日，中央人民政府主席毛泽东任命周恩来为出席日内瓦会议的中华人民共和国代表团首席代表，张闻天、王稼祥、李克农为代表[E2]。
- judge 理由：回答声称毛泽东于4月19日任命周恩来等人，但引文E2仅记载任命事实，未提及任命主体和具体日期，因此该主张未获引文直接支持。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：存在未获引用支持的主张：4月19日，中央人民政府主席毛泽东任命周恩来为出席日内瓦会议的中华人民共和国代表团首席代表，张闻天、王稼祥、李克农为代表[E2]。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C05 · `holdout_intersection_positive`

- 问题：1948年11月至1949年12月，刘伯承和邓小平共同指挥了哪些战略决战和战略进军？
- 答案性：`answerable`；split：`holdout`；类别：`intersection_hard_negative`
- 当前 citation_support：**fail**；process：**fail**
- 重点：重点：E4 引文支持“五人组成、刘陈邓为常委”，回答的并列表述是否构成额外主张。

事实核对：

- `huaihai_command`：当前 **covered** / supported
  - LLM 理由：回答中明确提到淮海战役由刘伯承、陈毅、邓小平、粟裕、谭震林组成总前委，刘伯承、陈毅、邓小平为常委，邓小平任总前委书记，并给出了战役时间范围。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `yangtze_1949`：当前 **partial** / partial
  - LLM 理由：回答仅提及1948年12月中央军委致电刘伯承、陈毅、邓小平、粟裕、谭震林酝酿渡江作战，并未包含1949年2月9日邓小平主持总前委扩大会议及4月百万雄师强渡长江的具体事实。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `southwest_1949`：当前 **missing** / not_applicable
  - LLM 理由：回答明确表示现有证据对1949年1月以后刘伯承、邓小平共同指挥的具体进军行动（如进军大西南）缺乏直接记载，未提及1949年8月刘伯承、邓小平联名致信林彪保障粮草供应一事。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**fail**
- judge 列出的未支持主张：
  - 刘伯承、邓小平与陈毅、粟裕、谭震林共同组成淮海战役总前敌委员会，刘伯承、陈毅、邓小平为常委，邓小平任总前委书记，统筹战役作战和地方支前事宜[E4]。
- judge 理由：回答将总前委的人员构成和职务分配合并成一个主张，但引文只支持总前委由五人组成、刘陈邓为常委、邓小平任书记，未提及粟裕、谭震林为常委。回答中的“刘伯承、邓小平与陈毅、粟裕、谭震林共同组成...刘伯承、陈毅、邓小平为常委”表述不准确：若将“共同组成”理解为总前委包括五人，则与常委仅三人不矛盾，但回答的表述将五人与常委并列，可能造成全部为常委的误解，属于未获完全支持的合并主张。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：存在未获引用支持的主张：刘伯承、邓小平与陈毅、粟裕、谭震林共同组成淮海战役总前敌委员会，刘伯承、陈毅、邓小平为常委，邓小平任总前委书记，统筹战役作战和地方支前事宜[E4]。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**fail**；理由：query planner 回退或执行计划不完整，未形成完整检索计划。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C06 · `holdout_exact_founding_ceremony`

- 问题：开国大典的地点和时间？
- 答案性：`answerable`；split：`holdout`；类别：`exact_fact`
- 当前 citation_support：**pass**；process：**pass**
- 重点：重点：founding_declaration 是否真的 missing；答案是否只写了地点时间。

事实核对：

- `founding_time_place`：当前 **covered** / supported
  - LLM 理由：回答中明确写明'1949年10月1日下午3时，在天安门广场举行'，涵盖了时间和地点信息。虽然未明确写'北京'，但'天安门广场'通常指北京天安门广场，结合常识可视为地点明确，且未与原文冲突，可视为覆盖。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `founding_declaration`：当前 **missing** / not_applicable
  - LLM 理由：回答中未提及毛泽东在天安门城楼上宣告中华人民共和国中央人民政府成立的内容。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**pass**
- judge 理由：回答中的事实性主张“1949年10月1日下午3时，在天安门广场举行”直接得到引文E2的支持。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **pass**；理由：回答主张与所标引用一致。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C07 · `dev_refusal_einstein`

- 问题：爱因斯坦在1925年担任了什么党内职务？
- 答案性：`unanswerable`；split：`development`；类别：`refusal_boundary`
- 当前 citation_support：**not_applicable**；process：**pass**
- 重点：重点：safe_refusal 与 scope_explanation；答案称 1925 超出 1921—1978 是否错误。

事实核对：无 facts（拒答题）。

引用核对：

- 未运行 citation judge（无引用或拒答）。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **not_applicable**；理由：拒答题没有引用，不评测引用覆盖。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **unknown**；理由：答案未给出可核时间，无法判断时间约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **pass**；理由：答案明确拒绝按错误前提编造职务。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **fail**；理由：答案称1925年超出1921—1978范围，理由是错的；1925在库范围内，应按缺乏可核实任职证据拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C08 · `holdout_exact_date`

- 问题：《邓小平年谱》记载邓小平1926年在哪些学校学习？
- 答案性：`answerable`；split：`holdout`；类别：`exact_fact`
- 当前 citation_support：**fail**；process：**pass**
- 重点：重点：无引用、无证据；答案是否只是索引提示，全部 fact missing。

事实核对：

- `oriental_university`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及任何学习经历，仅说明索引中未找到《邓小平年谱》章节，因此未表达邓小平曾在莫斯科东方劳动者共产主义大学学习的事实。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `sun_yat_sen_university`：当前 **missing** / not_applicable
  - LLM 理由：回答内容完全未涉及任何学校信息，仅表示索引缺失，因此未覆盖邓小平转入莫斯科中山大学的事实。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 未运行 citation judge（无引用或拒答）。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：答案未提供任何引用。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **unknown**；理由：答案未给出可核时间，无法判断时间约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C09 · `holdout_semantic_observation`

- 问题：斯诺在《西行漫记》中怎样描述红军学校的学习和训练安排？
- 答案性：`answerable`；split：`development`；类别：`semantic_retrieval`
- 当前 citation_support：**fail**；process：**pass**
- 重点：重点：无引用、无证据；5 个 fact 是否全部 missing。

事实核对：

- `red_university_size`：当前 **missing** / not_applicable
  - LLM 理由：回答仅表示未找到完整章节，未提及红军大学分部数量、学员人数或第一分部人数。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `first_division_training`：当前 **missing** / not_applicable
  - LLM 理由：回答未描述第一分部学员构成或训练时长。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `other_divisions`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及第二、三分部上课时长或第四分部的训练对象。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `curriculum`：当前 **missing** / not_applicable
  - LLM 理由：回答未涉及任何课程内容。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `recreation`：当前 **missing** / not_applicable
  - LLM 理由：回答未提及学员的文娱活动。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 未运行 citation judge（无引用或拒答）。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **fail**；理由：答案未提供任何引用。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **not_applicable**；理由：题目没有可核时间约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C10 · `dev_exact_deng_1954`

- 问题：1954年9月，邓小平在国务院和国防委员会分别担任什么职务？
- 答案性：`answerable`；split：`development`；类别：`exact_fact`
- 当前 citation_support：**pass**；process：**pass**
- 重点：对照题：预期 2/2 covered，citation pass。

事实核对：

- `deng_vice_premier`：当前 **covered** / supported
  - LLM 理由：回答中明确列出邓小平为国务院副总理之一，并说明1954年9月28日第一届全国人大一次会议通过该任命。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `deng_defense_vice_chair`：当前 **covered** / supported
  - LLM 理由：回答中明确说明邓小平任国防委员会副主席，并提及同次会议根据毛泽东提名通过。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**pass**
- judge 理由：回答中关于国务院副总理和国防委员会副主席的两项主张均由引文E1直接支持。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **pass**；理由：回答主张与所标引用一致。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C11 · `holdout_semantic_angang_constitution`

- 问题：20世纪60年代中国工业战线所说的“两参一改三结合”具体指什么？
- 答案性：`answerable`；split：`holdout`；类别：`semantic_retrieval`
- 当前 citation_support：**pass**；process：**pass**
- 重点：对照题：预期 4/4 covered，citation pass。

事实核对：

- `angang_workers_management`：当前 **covered** / supported
  - LLM 理由：回答中明确提到“工人参加管理”，并多次引用如“两参”指工人参加管理。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `angang_cadres_labour`：当前 **covered** / supported
  - LLM 理由：回答中明确提到“干部参加劳动”，并多次引用如“两参”指干部参加劳动。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `angang_rules_reform`：当前 **covered** / supported
  - LLM 理由：回答中明确提到“改革不合理的规章制度”，并多次引用如“一改”指改革不合理的规章制度。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `angang_three_way_combination`：当前 **covered** / supported
  - LLM 理由：回答中明确提到“领导干部、技术管理人员和工人相结合”，并多次引用如“三结合”指领导干部、技术管理人员和工人相结合。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**pass**
- judge 理由：回答中关于“两参一改三结合”的核心事实主张均由E5和E7直接支持，其他细节如E1、E2的引用也准确，未发现未获支持的主张。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **pass**；理由：回答主张与所标引用一致。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **pass**；理由：答案在题目时间范围内。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**pass**；理由：查询理解与检索计划覆盖问题实体、意图和时间/来源约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---

## C12 · `dev_intersection_zhu_peng_command`

- 问题：朱德和彭德怀是否都担任过八路军总指挥？
- 答案性：`answerable`；split：`development`；类别：`intersection_hard_negative`
- 当前 citation_support：**pass**；process：**fail**
- 重点：对照题：答案正确（朱总/彭副），但 process fallback；检查 answer pass 与 process fail 是否应分开。

事实核对：

- `zhu_de_commander`：当前 **covered** / supported
  - LLM 理由：回答中明确表述“朱德任总指挥”，并引用了相关命令。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______
- `peng_dehuai_deputy`：当前 **covered** / supported
  - LLM 理由：回答中明确表述“彭德怀任副总指挥”。
  - 人工：[ ] 同意　[ ] 改 covered　[ ] 改 partial　[ ] 改 missing　[ ] 改 contradicted
  - 备注：______

引用核对：

- 当前 verdict：**pass**
- judge 理由：回答的核心主张‘朱德和彭德怀没有都担任过八路军总指挥’由引文支持：朱德任总指挥，彭德怀任副总指挥。引文明确列明两人的职务，未支持彭德怀任总指挥的说法。回答中的具体职务描述与引文一致，资料限制部分作为审慎声明不构成错误。
- 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail；理由：______

维度核对：

- citation_support：当前 **pass**；理由：回答主张与所标引用一致。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- source_constraint：当前 **not_applicable**；理由：题目没有来源范围约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- time_constraint：当前 **not_applicable**；理由：题目没有可核时间约束。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- routing：当前 **pass**；理由：检索路由与问题类型匹配。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- safe_refusal：当前 **not_applicable**；理由：可答题目，不涉及拒答。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable
- scope_explanation：当前 **not_applicable**；理由：可答题目，不涉及范围说明。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

过程核对：

- 当前：**fail**；理由：query planner 回退或执行计划不完整，未形成完整检索计划。
  - 人工：[ ] 同意　[ ] 改 pass　[ ] 改 fail　[ ] 改 unknown　[ ] 改 not_applicable

---
