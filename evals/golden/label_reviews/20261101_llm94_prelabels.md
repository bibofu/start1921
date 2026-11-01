# LLM 候选标签预标（94 条，待人工复核）

> 2026-11-01 使用配置模型对 Golden v1.2 草案的 10 个可答题候选池做 LLM 预标。全部标签 `basis=llm_judge`，不是人工批准；正式 Golden 仍需逐条人工复核。

## 运行信息

- 模型：`deepseek-v4-pro`
- Prompt：`candidate-relevance-v1`
- 数据：`evals/golden/DRAFT_v1.2_cases.json` + `evals/golden/DRAFT_v1.2_ranking_pools.json`
- Capture：`data/reports/golden12_draft_20261101_r2/capture.json`
- 复核包：`data/reports/golden12_draft_20261101_r2/reviews_llm/index.html`
- Token 用量：49700

## 总览

| 题 | 条数 | rel=2 | rel=1 | rel=0 | 缺 rel=2 的证据组 |
|---|---:|---:|---:|---:|---:|
| `dev_exact_mao_thought_party_constitution` | 10 | 3 | 0 | 7 | 0 |
| `holdout_exact_founding_ceremony` | 10 | 2 | 1 | 7 | 0 |
| `dev_semantic_double_hundred` | 7 | 3 | 4 | 0 | 1 |
| `holdout_semantic_angang_constitution` | 10 | 4 | 1 | 5 | 0 |
| `dev_multi_long_march_meetings` | 12 | 4 | 0 | 8 | 12 |
| `holdout_multi_two_bombs_satellite` | 9 | 3 | 2 | 4 | 2 |
| `dev_intersection_zhu_peng_command` | 9 | 4 | 0 | 5 | 0 |
| `holdout_intersection_mao_zhu_jinggangshan` | 10 | 3 | 3 | 4 | 0 |
| `dev_constraint_korean_war_decision` | 9 | 5 | 3 | 1 | 0 |
| `holdout_constraint_nanchang_uprising_background` | 8 | 2 | 1 | 5 | 0 |

## 逐条标签

### `dev_exact_mao_thought_party_constitution`

问题：毛泽东思想什么时候写入党章？

- `0fcd4fa8d5` · mao_zedong_chronology_volume_2 p604 · rel=2 · mao_thought_in_charter_1945
  - 明确提到七大修改党章报告确定毛泽东思想为一切工作的指针，直接支持mao_thought_in_charter_1945。
- `d522ec1b5e` · cpc_history_volume_1 p814 · rel=2 · mao_thought_in_charter_1945
  - 明确提到七大确立毛泽东思想为党的指导思想并写入党章，直接支持mao_thought_in_charter_1945。
- `f55ec618ed` · mao_selected_works_combined p3154 · rel=2 · seven_congress_1945, mao_thought_in_charter_1945
  - 明确提到七大召开日期和党章规定毛泽东思想为一切工作的指针，直接支持两个证据组。
- `49caabc168` · cpc_history_volume_2 p771 · rel=0 · —
  - 内容涉及九大准备和修改党章，与七大无关，不相关。
- `5830271726` · mao_zedong_chronology_volume_5 p324 · rel=0 · —
  - 内容涉及1954年关于毛泽东思想提法的通知，与七大无关，不相关。
- `5b32ea04b6` · mao_zedong_chronology_volume_5 p625 · rel=0 · —
  - 内容涉及八大预备会议，与七大无关，不相关。
- `6817d1ca51` · mao_zedong_chronology_volume_1 p129 · rel=0 · —
  - 内容涉及1924年国民党一大，与七大无关，不相关。
- `75276ac37c` · cpc_history_volume_2 p771 · rel=0 · —
  - 内容涉及九大筹备和革委会，与七大无关，不相关。
- `8840844d44` · mao_zedong_chronology_volume_2 p483 · rel=0 · —
  - 内容涉及1943年整风等，与七大无关，不相关。
- `f7f1876093` · mao_zedong_chronology_volume_9 p150 · rel=0 · —
  - 内容涉及1967年教育革命和韶山活动，与七大无关，不相关。

### `holdout_exact_founding_ceremony`

问题：开国大典的地点和时间？

- `d44e2b000c` · deng_xiaoping_chronology_1904_1974_middle p199 · rel=2 · founding_ceremony_1949
  - 明确写出10月1日出席在天安门广场举行的开国大典，支持地点和事件。
- `fba5a03bc0` · cpc_history_volume_2 p15 · rel=2 · founding_ceremony_1949
  - 明确写出1949年10月1日下午3时在天安门广场举行开国大典，并提及毛泽东宣告，直接支持必要事实。
- `647408cddd` · zhou_enlai_chronology_1949_1976 p429 · rel=1 · —
  - 提到开国大典筹备委员会及议程，但未给出具体时间和地点，仅部分相关。
- `169f47d90d` · mao_zedong_chronology_volume_4 p147 · rel=0 · —
  - 内容为1950年事务，仅注释提及丁张秀清参加开国大典游行，无时间地点细节，不相关。
- `2f1a785d89` · deng_xiaoping_chronology_1904_1974_lower p122 · rel=0 · —
  - 内容为1958年事务，与开国大典无关。
- `488191b199` · mao_zedong_chronology_volume_7 p303 · rel=0 · —
  - 内容为1960年事务，与开国大典无关。
- `c19f34b4cf` · zhou_enlai_chronology_1949_1976 p585 · rel=0 · —
  - 内容为外交接见，与开国大典无关。
- `f088575d3e` · deng_xiaoping_chronology_1904_1974_lower p190 · rel=0 · —
  - 内容为1959年国庆十周年庆典，非1949年开国大典，时间不符。
- `f9bb6e786c` · mao_selected_works_combined p1716 · rel=0 · —
  - 内容为1971年讲话，仅提及袁文才儿子和王佐儿子被邀请参加开国大典，无时间地点细节，不相关。
- `fff1bf1205` · zhou_enlai_chronology_1949_1976 p364 · rel=0 · —
  - 内容为1946年国大相关，与开国大典无关。

### `dev_semantic_double_hundred`

问题：1956年党中央为什么提出“百花齐放、百家争鸣”方针？

- `1e6a703308` · mao_zedong_chronology_volume_5 p579 · rel=2 · double_hundred_proposal_1956
  - 明确记载1956年5月2日最高国务会议上毛泽东正式提出双百方针，直接支持提案事实。
- `50424481c7` · cpc_history_volume_2 p395 · rel=2 · double_hundred_background, double_hundred_proposal_1956
  - 明确提到科学文化领域受教条主义影响，以及1956年4月28日和5月2日提出双百方针，直接支持背景和提案事实。
- `663bddcc8c` · mao_zedong_chronology_volume_5 p576 · rel=2 · double_hundred_proposal_1956
  - 包含毛泽东在1956年4月28日中央政治局扩大会议总结讲话中提出双百方针的内容，直接支持提案事实。
- `0e8ccf9192` · cpc_history_volume_2 p391 · rel=1 · —
  - 提及双百方针的提出，但未说明具体背景、目的或提出细节，仅作为历史背景提及。
- `8f6da2ebde` · cpc_history_volume_2 p395 · rel=1 · —
  - 涉及双百方针的阐述，但未直接说明提出背景或目的，也未提及1956年4月28日或5月2日的提出细节。
- `c25d8f119b` · zhou_enlai_chronology_1949_1976 p752 · rel=1 · —
  - 提到双百口号的目的，但时间是1957年，且未涉及1956年提出背景或具体提案事实。
- `e5e10796ef` · cpc_history_volume_2 p429 · rel=1 · —
  - 涉及双百方针提出后的反应，但未直接说明提出背景、目的或1956年提案细节。

### `holdout_semantic_angang_constitution`

问题：20世纪60年代中国工业战线所说的“两参一改三结合”具体指什么？

- `0d5788cb51` · zhou_enlai_chronology_1949_1976 p1405 · rel=2 · angang_constitution_1960
  - 明确写出两参一改三结合的内容：干部参加劳动，工人参加管理，改革不合理的规章制度；领导干部、技术管理人员和工人相结合。
- `7e616293a4` · cpc_history_volume_2 p670 · rel=2 · angang_constitution_1960
  - 明确写出两参一改三结合的具体内容：工人参加管理，干部参加劳动，改革不合理的规章制度，实行工人群众、技术人员、领导干部三结合。
- `8389997dc2` · deng_xiaoping_chronology_1904_1974_lower p491 · rel=2 · angang_constitution_1960
  - 注释中明确列出两参一改三结合的内容：干部参加劳动，工人参加管理，改革不合理的规章制度，领导干部、技术人员和工人群众三结合。
- `f7b5a03963` · mao_zedong_chronology_volume_6 p521 · rel=2 · angang_constitution_1960
  - 提到两参一改三结合，并说明工人参加行政管理、改革不合理的规章制度、工人技术人员和职员结合。
- `93162e33a1` · mao_selected_works_combined p2083 · rel=1 · —
  - 仅提及两参一改三结合，未展开具体内容，不足以直接支持必要事实。
- `44be8f9944` · cpc_history_volume_2 p647 · rel=0 · —
  - 内容关于国民经济调整和比例关系，与两参一改三结合无关。
- `99981e76dd` · cpc_history_volume_2 p662 · rel=0 · —
  - 内容关于备战备荒为人民和大寨红旗渠，与两参一改三结合无关。
- `a72b8a2d36` · cpc_history_volume_2 p661 · rel=0 · —
  - 内容关于三五计划和三线建设，与两参一改三结合无关。
- `b73a5c29f6` · cpc_history_volume_2 p222 · rel=0 · —
  - 内容关于工业布局，与两参一改三结合无关。
- `eed3fe5c80` · cpc_history_volume_2 p670 · rel=0 · —
  - 内容关于劳动模范技术革新，未提及两参一改三结合。

### `dev_multi_long_march_meetings`

问题：梳理长征期间，召开的会议。

- `3376cf7335` · mao_zedong_chronology_volume_1 p491 · rel=2 · long_march_wuqi
  - 提到吴起镇会议批准榜罗镇会议决策，宣告长征结束，直接支持吴起镇会议
- `3ea3f866cd` · cpc_history_volume_1 p481 · rel=2 · long_march_zunyi
  - 明确记载1935年1月15日至17日中央政治局在遵义召开扩大会议
- `5dfccec643` · mao_selected_works_combined p567 · rel=2 · long_march_zunyi
  - 明确提到1935年1月在遵义召开扩大的中央政治局会议，即遵义会议
- `a907723f3f` · mao_zedong_chronology_volume_1 p477 · rel=2 · long_march_maoergai
  - 提到毛儿盖会议及中央政治局通过补充决定，明确支持毛儿盖会议
- `124a8fcf75` · mao_zedong_chronology_volume_1 p610 · rel=0 · —
  - 内容为1936年10月三大主力会师，未提及长征期间会议
- `17144e03f4` · red_star_over_china p217 · rel=0 · —
  - 仅泛述长征，未提及任何具体会议
- `5f60f511c1` · cpc_history_volume_1 p497 · rel=0 · —
  - 内容为1936年三大主力会师，未提及长征期间会议
- `5f950251d3` · mao_zedong_chronology_volume_1 p510 · rel=0 · —
  - 内容为1935年12月瓦窑堡会议后事项，未提及长征期间会议
- `838dc7e053` · mao_zedong_chronology_volume_1 p576 · rel=0 · —
  - 内容为1936年8月征稿《长征记》等，未提及长征期间会议
- `9b49fac829` · mao_zedong_chronology_volume_1 p507 · rel=0 · —
  - 内容为1935年12月瓦窑堡会议相关，非长征期间会议
- `f3967474ff` · mao_zedong_chronology_volume_2 p403 · rel=0 · —
  - 内容为1942年整风学习等，与长征期间会议无关
- `ff87700fdd` · cpc_history_volume_1 p498 · rel=0 · —
  - 内容为长征胜利后宁夏战役部署，未提及长征期间会议

### `holdout_multi_two_bombs_satellite`

问题：梳理20世纪50—70年代中国“两弹一星”的主要节点。

- `049f685a99` · cpc_history_volume_2 p653 · rel=2 · two_bombs_missile_1960
  - 明确写出1960年第一枚探空火箭和近程导弹发射成功，直接支持two_bombs_missile_1960。
- `0a1580ed4b` · cpc_history_volume_2 p651 · rel=2 · two_bombs_plan_1956
  - 明确写出1956年制定远景规划，部署原子弹和导弹，直接支持two_bombs_plan_1956。
- `4f46007a3a` · cpc_history_volume_2 p653 · rel=2 · two_bombs_atomic_1964, two_bombs_hydrogen_theory_1965
  - 明确写出1964年10月16日第一颗原子弹爆炸成功，以及1965年突破氢弹关键技术，直接支持两个事实。
- `0994edc695` · cpc_history_volume_2 p651 · rel=1 · —
  - 提到1958年提出研制人造卫星，但未涉及1970年发射成功，仅背景信息。
- `cd6e0a032c` · cpc_history_volume_2 p654 · rel=1 · —
  - 提到东方红一号卫星和两弹一星成就，但未明确给出1970年4月24日发射日期，不足以直接支持卫星事实。
- `1fbcdc552a` · cpc_history_volume_2 p221 · rel=0 · —
  - 内容为苏联援助工业项目，与两弹一星无关。
- `3ed5b667b0` · cpc_history_volume_2 p723 · rel=0 · —
  - 内容为注释和表彰名单，无具体事件节点，不相关。
- `522d9fb573` · cpc_history_volume_2 p38 · rel=0 · —
  - 仅提及钱学森个人贡献，无具体事件节点，不相关。
- `674d9adabb` · mao_zedong_chronology_volume_5 p36 · rel=0 · —
  - 内容与两弹一星无关。

### `dev_intersection_zhu_peng_command`

问题：朱德和彭德怀是否都担任过八路军总指挥？

- `29fb7a62e6` · deng_xiaoping_chronology_1904_1974_upper p157 · rel=2 · zhu_peng_eighth_route_1937
  - 明确记载1937年8月25日朱德为总指挥、彭德怀为副总指挥，直接支持证据组。
- `7176100baa` · zhou_enlai_chronology_1949_1976 p197 · rel=2 · zhu_peng_eighth_route_1937
  - 明确记载1937年8月25日朱德为总指挥、彭德怀为副总指挥，直接支持证据组。
- `dbcc412741` · mao_zedong_chronology_volume_2 p22 · rel=2 · zhu_peng_eighth_route_1937
  - 明确记载1937年8月25日朱德任总指挥、彭德怀任副总指挥，直接支持证据组。
- `e0c334b931` · cpc_history_volume_1 p599 · rel=2 · zhu_peng_eighth_route_1937
  - 明确记载1937年8月22日国民政府任命朱德为总指挥、彭德怀为副总指挥，直接支持证据组。
- `12ce320fb5` · red_star_over_china p289 · rel=0 · —
  - 内容为彭德怀早期经历，未涉及八路军总指挥任命。
- `1399c64077` · deng_xiaoping_chronology_1904_1974_upper p180 · rel=0 · —
  - 内容为1938年军事部署，未涉及1937年八路军总指挥任命。
- `3b532f6bd3` · deng_xiaoping_chronology_1904_1974_upper p263 · rel=0 · —
  - 内容为1939年朱德、彭德怀等致电通报，与1937年八路军总指挥任命无关。
- `5023907b72` · mao_zedong_chronology_volume_4 p231 · rel=0 · —
  - 内容为抗美援朝时期彭德怀任志愿军司令员，与八路军总指挥无关。
- `84c5c62e37` · red_star_over_china p290 · rel=0 · —
  - 内容为彭德怀早期经历，未涉及八路军总指挥任命。

### `holdout_intersection_mao_zhu_jinggangshan`

问题：1928年4月朱德、陈毅率部与毛泽东领导的部队在井冈山会师后，合编成了什么部队？朱德和毛泽东分别担任什么职务？

- `6b467d2730` · cpc_history_volume_1 p330 · rel=2 · jinggangshan_meeting_1928
  - 明确写出1928年4月会师、合编为工农革命军第四军、朱德任军长、毛泽东任党代表，直接支持所有必要事实。
- `82d4cbe46c` · mao_zedong_chronology_volume_1 p249 · rel=2 · jinggangshan_meeting_1928
  - 明确写出1928年5月4日宣布工农革命军第四军成立，朱德任军长，毛泽东任党代表，直接支持合编和职务事实。
- `ceb369c522` · mao_zedong_chronology_volume_1 p247 · rel=2 · jinggangshan_meeting_1928
  - 明确写出1928年4月会师、编为工农革命军第四军、朱德任军长、毛泽东任党代表，直接支持所有必要事实。
- `2ad2858747` · mao_zedong_chronology_volume_1 p246 · rel=1 · —
  - 描述会师过程，但未提及合编部队名称和职务，仅部分支持会师事实。
- `44016ae623` · mao_zedong_chronology_volume_1 p248 · rel=1 · —
  - 提到会师和成立工农革命军第四军，但未明确职务，部分支持合编事实。
- `cd41be32f6` · mao_selected_works_combined p65 · rel=1 · —
  - 提到朱德、陈毅率部与毛泽东会师，但未提及合编部队名称和职务，仅部分支持会师事实。
- `4c03d5ddc8` · mao_zedong_chronology_volume_1 p253 · rel=0 · —
  - 内容为1928年6月事件，与4月会师无关。
- `53b0436762` · cpc_history_volume_1 p332 · rel=0 · —
  - 内容为1928年10月及以后事件，未涉及4月会师。
- `56283e988f` · mao_zedong_chronology_volume_1 p261 · rel=0 · —
  - 内容为1928年8月事件，与4月会师无关。
- `86c9b55f8b` · mao_zedong_chronology_volume_1 p260 · rel=0 · —
  - 内容为1928年8月事件，与4月会师无关。

### `dev_constraint_korean_war_decision`

问题：1950年10月，中共中央围绕出兵朝鲜作出了什么决策？请按时间顺序说明。

- `18b8092be4` · cpc_history_volume_2 p108 · rel=2 · korean_war_entry_oct19
  - 明确记载10月19日志愿军从安东、长甸河口、集安跨过鸭绿江入朝。
- `5ace0f5916` · mao_zedong_chronology_volume_4 p206 · rel=2 · korean_war_decision_oct2
  - 记载10月2日毛泽东起草致斯大林电报决定派志愿军，并说明因书记处会议多数不赞成而搁置。
- `7cbf2160f2` · cpc_history_volume_2 p106 · rel=2 · korean_war_decision_oct2, korean_war_decision_oct4_5
  - 明确记载10月2日毛泽东起草长电及书记处会议未一致、电稿搁置；10月4-5日政治局扩大会议作出派遣志愿军决定。
- `b9318add38` · zhou_enlai_chronology_1949_1976 p475 · rel=2 · korean_war_order_oct8
  - 明确记载10月8日毛泽东发布组成中国人民志愿军的命令，任命彭德怀为司令员兼政治委员。
- `e72684a29a` · mao_zedong_chronology_volume_4 p210 · rel=2 · korean_war_decision_oct4_5
  - 记载10月5日政治局扩大会议继续讨论并作出抗美援朝战略决策，决定彭德怀率志愿军入朝。
- `7a027bc9d0` · deng_xiaoping_chronology_1904_1974_middle p299 · rel=1 · —
  - 提及10月8日中共中央作出抗美援朝保家卫国战略决策，但未说明具体命令或组成志愿军，仅部分相关。
- `9cc8fdc409` · zhou_enlai_chronology_1949_1976 p474 · rel=1 · —
  - 记载10月5日周恩来出席政治局会议支持出兵，但未明确会议作出决定，仅部分相关。
- `e9cb8e6361` · mao_zedong_chronology_volume_4 p213 · rel=1 · —
  - 提及10月8日派周恩来、林彪赴苏商谈，但未直接记载组成志愿军命令或彭德怀任命，仅部分相关。
- `e2d4eb1c0d` · mao_zedong_chronology_volume_4 p173 · rel=0 · —
  - 内容为8月会议讨论对策，时间不符，与10月决策无关。

### `holdout_constraint_nanchang_uprising_background`

问题：只依据《中国共产党历史》第一卷，说明1927年南昌起义是在什么背景下发动的。

- `75b9a92450` · cpc_history_volume_1 p308 · rel=2 · nanchang_background_failure_1927, nanchang_background_jiujiang_1927, nanchang_background_independent_1927
  - 直接支持三个证据组：明确写出大革命失败后的严峻形势和要不要坚持革命的问题；7月中旬派李立三等赴九江准备起义；7月20日发现张发奎站在汪精卫一边，李立三等提议独立发动南昌起义。
- `b32d675a53` · cpc_history_volume_1 p309 · rel=2 · nanchang_background_front_committee_1927, nanchang_background_aug1_1927
  - 直接支持两个证据组：明确写出7月27日周恩来到南昌成立前委并决定7月30日起义；7月31日前委决定8月1日起义。
- `637b1b9806` · cpc_history_volume_1 p310 · rel=1 · —
  - 内容涉及南昌起义后的行动和意义，与背景部分相关，但不直接支持任何必要事实。
- `34086c0217` · cpc_history_volume_1 p322 · rel=0 · —
  - 内容涉及其他地区的武装起义，与南昌起义背景无关。
- `3b83c20100` · cpc_history_volume_1 p420 · rel=0 · —
  - 内容涉及社会民主党问题和人物注释，与南昌起义背景无关。
- `b0f2649344` · cpc_history_volume_1 p315 · rel=0 · —
  - 内容涉及八七会议前后的方针和秋收起义，与南昌起义背景无关。
- `bb3d16c848` · cpc_history_volume_1 p321 · rel=0 · —
  - 内容涉及其他地区的武装起义，与南昌起义背景无关。
- `c2150657fd` · cpc_history_volume_1 p319 · rel=0 · —
  - 内容涉及广州起义和其他武装起义，与南昌起义背景无关。
