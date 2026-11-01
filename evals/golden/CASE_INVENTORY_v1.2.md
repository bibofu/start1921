# Golden v1.2 新增 12 题逐题清单

> 2026-11-01 并入 Golden v1.2。12 题全部 `human_review.status=approved`；新增 119 条候选标签和 10 个固定池均人工复核。

## 总览

| 题 | 分层 | 类别 | 答案性 | 事实 | 证据组 | 标签 | 池 |
|---|---|---|---|---:|---:|---:|---:|
| `dev_exact_mao_thought_party_constitution` | development | `exact_fact` | answerable | 2 | 2 | 10 | 10 |
| `holdout_exact_founding_ceremony` | holdout | `exact_fact` | answerable | 2 | 1 | 10 | 10 |
| `dev_semantic_double_hundred` | development | `semantic_retrieval` | answerable | 3 | 3 | 7 | 7 |
| `holdout_semantic_angang_constitution` | holdout | `semantic_retrieval` | answerable | 4 | 1 | 10 | 10 |
| `dev_multi_long_march_meetings` | development | `multi_evidence` | answerable | 15 | 15 | 37 | 37 |
| `holdout_multi_two_bombs_satellite` | holdout | `multi_evidence` | answerable | 6 | 6 | 9 | 9 |
| `dev_intersection_zhu_peng_command` | development | `intersection_hard_negative` | answerable | 2 | 1 | 9 | 9 |
| `holdout_intersection_mao_zhu_jinggangshan` | holdout | `intersection_hard_negative` | answerable | 3 | 1 | 10 | 10 |
| `dev_constraint_korean_war_decision` | development | `constraints_routing` | answerable | 4 | 4 | 9 | 9 |
| `holdout_constraint_nanchang_uprising_background` | holdout | `constraints_routing` | answerable | 4 | 5 | 8 | 8 |
| `dev_refusal_marriage_law_concubinage` | development | `refusal_boundary` | unanswerable | 0 | 0 | 0 | — |
| `holdout_refusal_un_seat_timing` | holdout | `refusal_boundary` | unanswerable | 0 | 0 | 0 | — |

## `dev_exact_mao_thought_party_constitution`

- 分层：`development`
- 类别：`exact_fact`
- 答案性：`answerable`
- topic_group：`mao_thought_party_constitution_1945`
- 问题：毛泽东思想什么时候写入党章？
- 复核：`approved`；候选标签 10 条；固定池 10 个候选

必要事实：

- `seven_congress_dates`：中共七大于1945年4月23日至6月11日召开
- `mao_thought_written_into_charter`：七大通过的党章把毛泽东思想确立为党的指导思想并写入党章

证据组与锚点：

- `seven_congress_1945`：中共七大于1945年4月23日至6月11日在延安举行（cpc_history_volume_1 p809）
- `mao_thought_in_charter_1945`：七大党章把毛泽东思想确立为党的指导思想并写入党章（cpc_history_volume_1 p814）

参考答案：

1945年，中共七大（1945年4月23日至6月11日）通过的《中国共产党党章》把毛泽东思想确立为党的指导思想并写入党章。

禁止主张：

- 毛泽东思想在1942年延安整风时写入党章（语料明确写入党章是七大的历史性贡献，不是1942年整风。）
- 毛泽东思想在1956年中共八大写入党章（八大不是首次写入党章；语料明确为七大党章。）
- 毛泽东思想在1949年《共同纲领》中写入党章（《共同纲领》不是党章，语料明确为七大党章。）

---

## `holdout_exact_founding_ceremony`

- 分层：`holdout`
- 类别：`exact_fact`
- 答案性：`answerable`
- topic_group：`founding_ceremony_1949`
- 问题：开国大典的地点和时间？
- 复核：`approved`；候选标签 10 条；固定池 10 个候选

必要事实：

- `founding_time_place`：开国大典于1949年10月1日下午3时在北京天安门广场举行
- `founding_declaration`：毛泽东在天安门城楼上宣告中华人民共和国中央人民政府成立

证据组与锚点：

- `founding_ceremony_1949`：1949年10月1日下午3时开国大典在北京天安门广场举行（cpc_history_volume_2 p15；cpc_history_volume_2 p48）

参考答案：

1949年10月1日下午3时，在北京天安门广场举行；毛泽东在天安门城楼上宣告中华人民共和国中央人民政府成立。

禁止主张：

- 开国大典在1949年9月21日举行（9月21日是中国人民政治协商会议第一届全体会议开幕；开国大典是10月1日。）
- 开国大典在上午10时举行（语料记载为下午3时/3时许。）
- 开国大典在中南海怀仁堂举行（语料记载典礼在天安门广场举行，毛泽东在天安门城楼宣告。）

---

## `dev_semantic_double_hundred`

- 分层：`development`
- 类别：`semantic_retrieval`
- 答案性：`answerable`
- topic_group：`double_hundred_1956`
- 问题：1956年党中央为什么提出“百花齐放、百家争鸣”方针？
- 复核：`approved`；候选标签 7 条；固定池 7 个候选

必要事实：

- `double_hundred_background_fact`：新中国成立后头几年，科学文化领域受苏联学术批评中粗暴作风和教条主义影响，存在推崇一个学派、压制另一个学派、乱贴政治标签等现象
- `double_hundred_purpose_fact`：党中央提出“百花齐放、百家争鸣”作为繁荣和发展社会主义科学文化事业的指导方针
- `double_hundred_proposal_fact`：1956年4月28日毛泽东在中央政治局扩大会议总结讲话中提出艺术上百花齐放、学术上百家争鸣；5月2日最高国务会议正式提出这一方针

证据组与锚点：

- `double_hundred_background`：科学文化领域受苏联学术批评中粗暴作风和教条主义影响（cpc_history_volume_2 p394）
- `double_hundred_purpose`：双百方针是繁荣和发展社会主义科学文化事业的指导方针（cpc_history_volume_2 p394）
- `double_hundred_proposal_1956`：1956年4月28日毛泽东提出、5月2日最高国务会议正式提出双百方针（cpc_history_volume_2 p395；cpc_history_volume_2 p395）

参考答案：

新中国成立后头几年，科学文化领域受苏联学术批评中粗暴作风和教条主义影响，存在推崇一个学派、压制另一个学派、乱贴政治标签等问题。为繁荣和发展社会主义科学文化事业，党中央提出“百花齐放、百家争鸣”：艺术问题上的百花齐放，学术问题上的百家争鸣。1956年4月28日毛泽东在中央政治局扩大会议总结讲话中提出，5月2日最高国务会议正式提出。

禁止主张：

- “百花齐放、百家争鸣”方针是在1957年反右运动中提出的（语料明确为1956年4月提出、5月2日正式提出。）
- “百花齐放、百家争鸣”只适用于文学艺术（语料明确为艺术问题上的百花齐放、学术问题上的百家争鸣。）

---

## `holdout_semantic_angang_constitution`

- 分层：`holdout`
- 类别：`semantic_retrieval`
- 答案性：`answerable`
- topic_group：`angang_constitution_1960`
- 问题：20世纪60年代中国工业战线所说的“两参一改三结合”具体指什么？
- 复核：`approved`；候选标签 10 条；固定池 10 个候选

必要事实：

- `angang_workers_management`：工人参加管理
- `angang_cadres_labour`：干部参加劳动
- `angang_rules_reform`：改革不合理的规章制度
- `angang_three_way_combination`：实行工人群众、技术人员、领导干部三结合

证据组与锚点：

- `angang_constitution_1960`：“两参一改三结合”的基本精神（cpc_history_volume_2 p670）

参考答案：

工人参加管理；干部参加劳动；改革不合理的规章制度；实行工人群众、技术人员、领导干部三结合。

禁止主张：

- “两参”是干部参加管理、工人参加劳动（语料明确为工人参加管理、干部参加劳动；主体不能颠倒。）
- “三结合”是工人、农民、士兵三结合（语料明确为工人群众、技术人员、领导干部三结合。）
- “一改”是改革工资制度（语料明确为改革不合理的规章制度。）

---

## `dev_multi_long_march_meetings`

- 分层：`development`
- 类别：`multi_evidence`
- 答案性：`answerable`
- topic_group：`long_march_meetings_1934_1935`
- 问题：梳理长征期间，召开的会议。
- 复核：`approved`；候选标签 37 条；固定池 37 个候选

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

证据组与锚点：

- `long_march_tongdao`：通道会议（中央负责人紧急会议）（mao_zedong_chronology_volume_1 p448）
- `long_march_liping`：黎平会议（中央政治局会议）（mao_zedong_chronology_volume_1 p449）
- `long_march_houchang`：猴场会议（中央政治局会议）（mao_zedong_chronology_volume_1 p451）
- `long_march_zunyi`：遵义会议（中央政治局扩大会议）（cpc_history_volume_1 p483）
- `long_march_zhaxi`：扎西中央负责人会议（含鸡鸣三省常委分工）（mao_zedong_chronology_volume_1 p456）
- `long_march_huili`：会理会议（中央政治局扩大会议）（mao_zedong_chronology_volume_1 p464）
- `long_march_lianghekou`：两河口会议（中央政治局会议）（mao_zedong_chronology_volume_1 p469）
- `long_march_luhua`：芦花会议（中央政治局常委会议）（mao_zedong_chronology_volume_1 p472）
- `long_march_shawu`：沙窝会议（中央政治局会议）（mao_zedong_chronology_volume_1 p474）
- `long_march_shawu_standing`：沙窝中央政治局常委会议（mao_zedong_chronology_volume_1 p476）
- `long_march_maoergai`：毛儿盖会议（中央政治局会议）（mao_zedong_chronology_volume_1 p476）
- `long_march_axi`：阿西紧急会议（mao_zedong_chronology_volume_1 p480）
- `long_march_ejie`：俄界会议（中央政治局扩大会议）（mao_zedong_chronology_volume_1 p481）
- `long_march_bangluozhen`：榜罗镇会议（中央政治局常委会议）（mao_zedong_chronology_volume_1 p486）
- `long_march_wuqi`：吴起镇中央政治局会议（cpc_history_volume_1 p490）

参考答案：

以《中国共产党历史》第一卷和《毛泽东年谱》明确记载的中央政治局（扩大）会议、中央政治局常委会议、中央负责人会议为限，不声称穷尽。至少包括：通道会议（1934年12月12日，湖南通道）、黎平会议（1934年12月18日，贵州黎平）、猴场会议（1935年1月1日，贵州瓮安猴场）、遵义会议（1935年1月，贵州遵义）、扎西中央负责人会议（1935年2月，云南威信扎西）、会理会议（1935年5月12日，四川会理）、两河口会议（1935年6月26日，四川懋功两河口）、芦花会议（1935年7月18日，四川芦花）、沙窝会议（1935年8月4—6日，四川毛儿盖附近沙窝）、沙窝中央政治局常委会议（1935年8月19日）、毛儿盖会议（1935年8月20日）、阿西紧急会议（1935年9月9/10日，四川阿西）、俄界会议（1935年9月12日，甘肃迭部俄界）、榜罗镇会议（1935年9月27日，甘肃通渭榜罗镇）、吴起镇中央政治局会议（1935年10月22日）。

禁止主张：

- 长征期间只召开了遵义会议（语料还记载通道、黎平、猴场、会理、两河口、沙窝、毛儿盖、俄界、榜罗镇、吴起镇等会议。）
- 通道会议在贵州黎平召开（通道会议在湖南通道；黎平会议在贵州黎平，二者是不同会议。）
- 遵义会议在1935年10月召开（遵义会议在1935年1月；1935年10月是长征到达陕北前后。）
- 榜罗镇会议决定南下川康（榜罗镇会议决定把落脚点放在陕北，保卫和扩大苏区。）

---

## `holdout_multi_two_bombs_satellite`

- 分层：`holdout`
- 类别：`multi_evidence`
- 答案性：`answerable`
- topic_group：`two_bombs_satellite_1956_1970`
- 问题：梳理20世纪50—70年代中国“两弹一星”的主要节点。
- 复核：`approved`；候选标签 9 条；固定池 9 个候选

必要事实：

- `two_bombs_plan_fact`：1956年制定1956—1967年科学技术发展远景规划，把原子能列为重点，并部署原子弹和导弹
- `two_bombs_missile_fact`：1960年第一枚探空火箭和近程导弹发射成功
- `two_bombs_atomic_fact`：1964年10月16日第一颗原子弹爆炸成功
- `two_bombs_hydrogen_theory_fact`：1965年中国科学家突破氢弹研制中的关键技术
- `two_bombs_hydrogen_fact`：1967年6月第一颗氢弹爆炸成功
- `two_bombs_satellite_fact`：1970年4月24日第一颗人造地球卫星“东方红一号”发射成功

证据组与锚点：

- `two_bombs_plan_1956`：1956年制定科学技术发展远景规划，部署原子弹和导弹（cpc_history_volume_2 p651）
- `two_bombs_missile_1960`：1960年第一枚探空火箭和近程导弹发射成功（cpc_history_volume_2 p653）
- `two_bombs_atomic_1964`：1964年10月16日第一颗原子弹爆炸成功（cpc_history_volume_2 p653）
- `two_bombs_hydrogen_theory_1965`：1965年突破氢弹研制关键技术（cpc_history_volume_2 p653）
- `two_bombs_hydrogen_1967`：1967年6月第一颗氢弹爆炸成功（cpc_history_volume_2 p919）
- `two_bombs_satellite_1970`：1970年4月24日第一颗人造地球卫星发射成功（cpc_history_volume_2 p41；cpc_history_volume_2 p919）

参考答案：

1956年制定1956—1967年科学技术发展远景规划，把原子能列为重点，并部署原子弹和导弹；1960年第一枚探空火箭和近程导弹发射成功；1964年10月16日第一颗原子弹爆炸成功；1965年中国科学家突破氢弹研制中的关键技术；1967年6月第一颗氢弹爆炸成功；1970年4月24日第一颗人造地球卫星“东方红一号”发射成功。

禁止主张：

- 中国在1964年爆炸了第一颗氢弹（1964年10月16日是原子弹；第一颗氢弹是1967年6月。）
- 中国在1967年爆炸了第一颗原子弹（第一颗原子弹是1964年10月16日；1967年6月是氢弹。）
- 中国在1970年发射了第一枚近程导弹（1970年4月24日发射的是第一颗人造地球卫星；近程导弹是1960年。）

---

## `dev_intersection_zhu_peng_command`

- 分层：`development`
- 类别：`intersection_hard_negative`
- 答案性：`answerable`
- topic_group：`eighth_route_army_command_1937`
- 问题：朱德和彭德怀是否都担任过八路军总指挥？
- 复核：`approved`；候选标签 9 条；固定池 9 个候选

必要事实：

- `zhu_de_commander`：朱德任八路军总指挥
- `peng_dehuai_deputy`：彭德怀任八路军副总指挥

证据组与锚点：

- `zhu_peng_eighth_route_1937`：1937年8月红军改编为八路军，朱德任总指挥、彭德怀任副总指挥（cpc_history_volume_1 p599；cpc_history_volume_1 p599）

参考答案：

不是。1937年8月红军改编为八路军时，朱德任总指挥，彭德怀任副总指挥。

禁止主张：

- 彭德怀任八路军总指挥（语料明确朱德任总指挥，彭德怀任副总指挥。）
- 朱德和彭德怀都担任过八路军总指挥（两人分别是总指挥、副总指挥，不是都任总指挥。）
- 朱德任八路军副总指挥（朱德任总指挥；彭德怀任副总指挥。）

---

## `holdout_intersection_mao_zhu_jinggangshan`

- 分层：`holdout`
- 类别：`intersection_hard_negative`
- 答案性：`answerable`
- topic_group：`jinggangshan_meeting_1928`
- 问题：1928年4月朱德、陈毅率部与毛泽东领导的部队在井冈山会师后，合编成了什么部队？朱德和毛泽东分别担任什么职务？
- 复核：`approved`；候选标签 10 条；固定池 10 个候选

必要事实：

- `jinggangshan_meeting_fact`：1928年4月，朱德、陈毅率南昌起义保留的一部分部队和湘南起义农军与毛泽东领导的部队在宁冈砻市会师
- `jinggangshan_fourth_army`：会师后合编为工农革命军第四军（后改称红军第四军）
- `jinggangshan_roles`：朱德任军长，毛泽东任党代表

证据组与锚点：

- `jinggangshan_meeting_1928`：1928年4月朱毛井冈山会师后合编为工农革命军第四军（cpc_history_volume_1 p330）

参考答案：

1928年4月，朱德、陈毅率南昌起义保留的一部分部队和湘南起义农军与毛泽东领导的部队在宁冈砻市会师。会师后合编为工农革命军第四军（后改称红军第四军），朱德任军长，毛泽东任党代表。

禁止主张：

- 井冈山会师后合编为红五军（语料明确合编为工农革命军第四军（后改称红军第四军）；红五军是彭德怀、滕代远所部。）
- 井冈山会师后朱德任党代表、毛泽东任军长（语料明确朱德任军长、毛泽东任党代表。）
- 井冈山会师后成立了红一方面军（会师后成立的是工农革命军第四军；红一方面军是 later 的编制。）

---

## `dev_constraint_korean_war_decision`

- 分层：`development`
- 类别：`constraints_routing`
- 答案性：`answerable`
- topic_group：`korean_war_decision_1950`
- 问题：1950年10月，中共中央围绕出兵朝鲜作出了什么决策？请按时间顺序说明。
- 复核：`approved`；候选标签 9 条；固定池 9 个候选

必要事实：

- `korean_oct2_telegram`：10月2日，毛泽东起草决定派遣志愿军入朝作战的长电；当天书记处会议未取得一致意见，电稿被搁置
- `korean_oct4_5_decision`：10月4日至5日，中央政治局扩大会议讨论并作出派遣中国人民志愿军入朝作战的决定
- `korean_oct8_order`：10月8日，毛泽东发布命令，将东北边防军组成中国人民志愿军，任命彭德怀为司令员兼政治委员
- `korean_oct19_entry`：10月19日，志愿军从安东、长甸河口、集安跨过鸭绿江入朝

证据组与锚点：

- `korean_war_decision_oct2`：10月2日毛泽东起草决定派遣志愿军入朝的长电（cpc_history_volume_2 p106）
- `korean_war_decision_oct4_5`：10月4日至5日中央政治局扩大会议作出出兵决定（cpc_history_volume_2 p106）
- `korean_war_order_oct8`：10月8日毛泽东发布命令组成中国人民志愿军（cpc_history_volume_2 p107）
- `korean_war_entry_oct19`：10月19日志愿军跨过鸭绿江入朝（cpc_history_volume_2 p108）

参考答案：

10月2日，毛泽东起草决定派遣志愿军入朝作战的长电，但当天书记处会议未取得一致意见，电稿被搁置；10月4日至5日，中央政治局扩大会议讨论并作出派遣中国人民志愿军入朝作战的决定；10月8日，毛泽东发布命令，将东北边防军组成中国人民志愿军，任命彭德怀为司令员兼政治委员；10月19日，志愿军从安东、长甸河口、集安跨过鸭绿江入朝。

禁止主张：

- 中共中央在1950年6月就决定出兵朝鲜（语料显示出兵决策发生在1950年10月。）
- 10月19日志愿军入朝时才作出出兵决定（10月4日至5日政治局扩大会议已作出出兵决定，10月8日发布命令，10月19日入朝。）
- 彭德怀任中国人民志愿军总参谋长（语料明确彭德怀任志愿军司令员兼政治委员。）

---

## `holdout_constraint_nanchang_uprising_background`

- 分层：`holdout`
- 类别：`constraints_routing`
- 答案性：`answerable`
- topic_group：`nanchang_uprising_1927`
- 问题：只依据《中国共产党历史》第一卷，说明1927年南昌起义是在什么背景下发动的。
- 复核：`approved`；候选标签 8 条；固定池 8 个候选

必要事实：

- `nanchang_failure_context`：1927年大革命失败后，革命处于严重失败形势；中国共产党面临要不要坚持革命、如何坚持革命的问题
- `nanchang_jiujiang_preparation`：1927年7月中旬，中共中央临时政治局常委会派李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织党掌握和影响的国民革命军一部分，联合张发奎重回广东
- `nanchang_independent_decision`：7月20日发现张发奎站在汪精卫一边后，李立三等提议独立发动反对南京和武汉国民党政府的军事行动，即南昌起义
- `nanchang_front_committee`：7月27日周恩来抵南昌成立前委，决定7月30日起义；后因张国焘主张等待张发奎同意被前委否决，7月31日决定8月1日起义

证据组与锚点：

- `nanchang_background_failure_1927`：大革命失败后的严峻形势和要不要坚持革命的问题（cpc_history_volume_1 p308）
- `nanchang_background_jiujiang_1927`：1927年7月中旬派李立三、邓中夏、谭平山、恽代英等赴九江准备起义（cpc_history_volume_1 p308）
- `nanchang_background_independent_1927`：7月20日发现张发奎站在汪精卫一边，李立三等提议独立发动南昌起义（cpc_history_volume_1 p308）
- `nanchang_background_front_committee_1927`：7月27日周恩来到南昌成立前委并决定7月30日起义（cpc_history_volume_1 p309）
- `nanchang_background_aug1_1927`：7月31日前委决定8月1日起义（cpc_history_volume_1 p309）

参考答案：

1927年大革命失败后，革命处于严重失败形势，中国共产党面临要不要坚持革命、如何坚持革命的问题。7月中旬，中共中央临时政治局常委会派李立三、邓中夏、谭平山、恽代英等赴江西九江，准备组织党掌握和影响的国民革命军一部分，联合张发奎重回广东。7月20日发现张发奎已站在汪精卫一边，李立三等提议独立发动反对南京和武汉国民党政府的军事行动，即南昌起义。7月27日周恩来抵南昌成立前委，决定7月30日起义；后因张国焘主张等待张发奎同意被前委否决，7月31日决定8月1日起义。

禁止主张：

- 南昌起义是在国共合作背景下由国民党领导的（语料显示起义是中国共产党在革命失败后独立发动的武装行动。）
- 南昌起义最初决定在7月27日举行（7月27日前委成立后决定7月30日起义；后改为8月1日。）
- 南昌起义由张发奎领导（发现张发奎站在汪精卫一边后，李立三等放弃依赖张发奎的计划，独立发动起义。）

---

## `dev_refusal_marriage_law_concubinage`

- 分层：`development`
- 类别：`refusal_boundary`
- 答案性：`unanswerable`
- topic_group：`marriage_law_1950`
- 问题：1950年《婚姻法》是否允许纳妾？
- 复核：`approved`；候选标签 0 条；固定池 — 个候选

参考答案：

不允许。1950年《婚姻法》第二条规定禁止重婚、纳妾、童养媳、干涉寡妇婚姻自由、借婚姻关系索取财物。

拒答口径：

- 类型：`false_premise`
- 正确口径：1950年《婚姻法》第二条规定禁止重婚、纳妾、童养媳、干涉寡妇婚姻自由、借婚姻关系索取财物。

禁止主张：

- 1950年《婚姻法》允许纳妾（第二条规定禁止纳妾。）
- 1950年《婚姻法》只禁止重婚，不禁止纳妾（第二条同时禁止重婚、纳妾、童养媳等。）
- 1950年《婚姻法》没有涉及纳妾问题（第二条明确禁止纳妾。）

---

## `holdout_refusal_un_seat_timing`

- 分层：`holdout`
- 类别：`refusal_boundary`
- 答案性：`unanswerable`
- topic_group：`un_seat_1971`
- 问题：中国是在1972年尼克松访华之后才恢复联合国合法席位的吗？
- 复核：`approved`；候选标签 0 条；固定池 — 个候选

参考答案：

不是。1971年10月25日，第二十六届联合国大会通过2758号决议，恢复中华人民共和国在联合国的一切合法权利；尼克松访华是1972年2月。

拒答口径：

- 类型：`false_premise`
- 正确口径：1971年10月25日，第二十六届联合国大会通过2758号决议，恢复中华人民共和国在联合国的一切合法权利；尼克松访华是1972年2月。

禁止主张：

- 中国是在1972年尼克松访华之后才恢复联合国合法席位的（恢复席位是1971年10月25日；尼克松访华是1972年2月。）
- 尼克松访华发生在1971年（语料明确尼克松访华是1972年2月。）
- 中国在1972年恢复联合国合法席位（语料明确为1971年10月25日第26届联大2758号决议。）

---
