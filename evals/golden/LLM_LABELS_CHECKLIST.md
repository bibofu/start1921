# 78 条待抽检 LLM 标签（紧凑清单）

只列 `basis=llm_judge` 的 78 条；20 条人工处理过的标签不在本表。原文摘录、锚点页对照和自动标记见 [LLM_LABELS_PENDING.md](LLM_LABELS_PENDING.md)。

回复格式：`题ID / 候选ID / 通过 或 改判为 0|1|2 / 理由`。

### 78 条待抽检清单（按题）

#### `dev_exact_zunyi_election`

问题：遵义会议选举毛泽东担任什么党内职务？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `f84ee4c70b` | mao_selected_works_combined PDF 2527 | 1 | — | 提到遵义会议及张闻天会后分工，但未明确毛泽东当选职务，仅背景相关。 |
| `a4d40f1a74` | cpc_history_volume_1 PDF 483 | 2 | zunyi_election | 明确写出遵义会议选举毛泽东为中央政治局常委。 |
| `d84a62939d` | mao_zedong_chronology_volume_2 PDF 486 | 0 | — | 内容为1943年整风讲话，与遵义会议选举无关。 |
| `d5e4aa5a2b` | mao_selected_works_combined PDF 2376 | 0 | — | 内容涉及苏联政治和四清运动，与遵义会议无关。 |
| `02b7b7dafc` | mao_selected_works_combined PDF 62 | 0 | — | 内容为井冈山时期特委选举，与遵义会议无关。 |
| `f75f5ffcc9` | mao_selected_works_combined PDF 2623 | 1 | — | 提到遵义会议及张闻天会后分工，但未明确毛泽东当选职务。 |
| `aa0e7b86ca` | zhou_enlai_chronology_1949_1976 PDF 1068 | 0 | — | 仅评价遵义会议意义，未提及选举职务。 |
| `b41e283c43` | mao_selected_works_combined PDF 2623 | 1 | — | 提到王稼祥在遵义会议后被增选为政治局委员，但未提及毛泽东职务。 |
| `d0c43c829e` | mao_selected_works_combined PDF 1708 | 0 | — | 内容为秋收起义后处分及王明路线背景，与遵义会议选举无关。 |
| `5c40d3509a` | mao_selected_works_combined PDF 1683 | 0 | — | 内容为1954年宪法及国家主席选举，与遵义会议无关。 |

#### `holdout_exact_date`

问题：《邓小平年谱》记载邓小平1926年在哪些学校学习？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `e8fbd60295` | deng_xiaoping_chronology_1904_1974_upper PDF 33 | 2 | oriental_university, sun_yat_sen_university | 原文明确记载1926年1月中旬到达莫斯科，先入莫斯科东方劳动者共产主义大学学习，不久转入莫斯科中山大学，直接支持两个必要事实。 |
| `ae55014d8a` | deng_xiaoping_chronology_1904_1974_upper PDF 23 | 0 | — | 内容为1922年旅欧少年共产党成立及求学未成，与1926年在莫斯科的学校无关。 |
| `373dd98397` | deng_xiaoping_chronology_1904_1974_upper PDF 36 | 1 | — | 提及莫斯科中山大学和东方劳动者共产主义大学，但未明确说明邓小平先后入学，仅涉及1926年5月后的活动，不足以直接支持必要事实。 |
| `19f4f87094` | deng_xiaoping_chronology_1904_1974_upper PDF 20 | 0 | — | 内容为1921年留法勤工俭学活动，与1926年在莫斯科的学校无关。 |
| `8906ad82c6` | deng_xiaoping_chronology_1904_1974_upper PDF 32 | 0 | — | 内容为1926年1月离开巴黎赴苏联的经过，未提及到达莫斯科后入读的学校。 |
| `4034515a63` | deng_xiaoping_chronology_1904_1974_upper PDF 25 | 0 | — | 内容为1923年加入旅欧共青团及编辑刊物，与1926年在莫斯科的学校无关。 |

#### `holdout_semantic_observation`

问题：斯诺在《西行漫记》中怎样描述红军学校的学习和训练安排？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `a7f87c3700` | red_star_over_china PDF 52 | 0 | — | 仅目录，无具体描述 |
| `acfc0bb601` | red_star_over_china PDF 3 | 0 | — | 仅书名和译者，无内容 |
| `47e97f2006` | red_star_over_china PDF 308 | 1 | — | 描述列宁室和军事训练，但未直接支持任何必要事实 |
| `7fd0129792` | red_star_over_china PDF 38 | 0 | — | 出版说明，无相关内容 |
| `89b2e351a6` | red_star_over_china PDF 41 | 0 | — | 出版背景，无相关内容 |
| `12b3732f91` | red_star_over_china PDF 39 | 0 | — | 斯诺生平，无相关内容 |
| `571e7e2d0d` | red_star_over_china PDF 265 | 1 | — | 提到红军大学等学校，但未给出具体规模和训练安排 |
| `c44c60f964` | red_star_over_china PDF 37 | 0 | — | 出版说明，无相关内容 |
| `2b85dd969e` | red_star_over_china PDF 53 | 0 | — | 仅目录，无具体描述 |

#### `dev_multi_mao_hunan`

问题：逐年梳理毛泽东1921—1926年在湖南的活动。

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `a2654187b7` | cpc_history_volume_1 PDF 246 | 1 | — | 涉及1926年湖南工农运动背景，但未直接支持任何必要事实，仅提供背景。 |
| `07189eaae4` | mao_zedong_chronology_volume_1 PDF 184 | 1 | — | 涉及1926年12月毛泽东在湖南的活动，但未直接支持任何必要事实，仅部分相关。 |
| `fc93ef0f94` | mao_zedong_chronology_volume_1 PDF 161 | 0 | — | 内容涉及国民党二大决议案修改，与问题中毛泽东在湖南的活动无关。 |
| `3253e3ec73` | mao_zedong_chronology_volume_1 PDF 183 | 2 | y1926_hunan_peasant_congress, y1926_workers_peasants_welcome_speech | 明确记载1926年12月17日由汉口到长沙参加湖南全省第一次农民代表大会，并同湖南同志商讨起草决议案；12月20日出席欢迎大会并作演说，直接支持y1926_hunan_peasant_congress和y1926_workers_peasants_welcome_speech。 |
| `a722b83e50` | mao_zedong_chronology_volume_1 PDF 211 | 0 | — | 内容涉及1927年6月马日事变后的活动，与问题时间范围不符。 |
| `b4308a73ff` | mao_zedong_chronology_volume_1 PDF 145 | 0 | — | 内容涉及1925年9月毛泽东离开湖南赴广州，与问题中1921-1926年在湖南的活动无关。 |
| `a020df2627` | mao_zedong_chronology_volume_1 PDF 104 | 2 | y1922_xiang_committee | 明确记载1922年5月底中共湘区执行委员会成立，毛泽东任书记，区委机关设在长沙清水塘，直接支持y1922_xiang_committee。 |
| `0b7a35d0df` | mao_zedong_chronology_volume_1 PDF 98 | 0 | — | 内容涉及1921年10月湖南支部活动，但未直接支持任何必要事实，且部分信息与必要事实不符。 |
| `60c21f68ff` | mao_zedong_chronology_volume_1 PDF 182 | 1 | — | 涉及1926年12月湖南农民代表大会电请毛泽东指导，但未直接支持任何必要事实。 |
| `ad013bb4cf` | mao_zedong_chronology_volume_1 PDF 163 | 0 | — | 内容涉及1926年1月国民党二大及中央宣传部代理部长任命，与问题中毛泽东在湖南的活动无关。 |

#### `dev_multi_meetings`

问题：比较遵义会议和1959年庐山会议各自讨论的核心问题、会议进程和后续影响。

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `147ae167f5` | mao_selected_works_combined PDF 1705 | 1 | — | 提到1959年庐山会议与彭德怀的斗争是两个司令部的斗争，但未提供具体日期、内容或决议，仅部分相关。 |
| `aa95f9e238` | mao_zedong_chronology_volume_7 PDF 120 | 1 | — | 提到庐山会议议定记录修正草案的讨论，但信息不完整，未直接支持任何必要事实。 |
| `7c69df789f` | cpc_history_volume_2 PDF 529 | 2 | lushan_letter_content | 详细描述彭德怀写信的背景和内容，包括肯定成绩、提出左倾倾向、陈述经验教训，支持彭德怀信的内容。 |
| `42afeccc96` | zhou_enlai_chronology_1949_1976 PDF 859 | 1 | — | 涉及庐山会议后的工作布置和传达反右倾精神，但未直接支持任何必要事实。 |
| `6dc18d3e08` | cpc_history_volume_2 PDF 531 | 1 | — | 描述黄克诚、周小舟对彭德怀信的看法，但未直接支持任何必要事实。 |

#### `holdout_multi_period`

问题：邓小平在1938年承担了哪些主要工作任务？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `bd2c980abe` | deng_xiaoping_chronology_1904_1974_upper PDF 237 | 0 | — | 内容涉及1938年9月后的行程和六届六中全会，未提及任何必要事实中的具体任务。 |
| `a7256fd6f0` | deng_xiaoping_chronology_1904_1974_upper PDF 174 | 2 | d129_commissar | 明确记载1938年1月5日邓小平接替张浩任一二九师政治委员，直接支持d129_commissar。 |
| `9567843f97` | deng_xiaoping_chronology_1904_1974_upper PDF 243 | 0 | — | 内容为1938年12月收阅电报，涉及区划调整，与必要事实无关。 |
| `c435c64e05` | deng_xiaoping_chronology_1904_1974_upper PDF 223 | 0 | — | 内容为1938年6月活动，未涉及必要事实中的具体任务。 |
| `8080eccd6b` | deng_xiaoping_chronology_1904_1974_upper PDF 181 | 0 | — | 内容为1938年2月活动，未涉及必要事实中的具体任务。 |
| `6f3db4a1a4` | deng_xiaoping_chronology_1904_1974_upper PDF 229 | 0 | — | 内容为1938年7月活动，未涉及必要事实中的具体任务。 |
| `23d28ba8aa` | deng_xiaoping_chronology_1904_1974_upper PDF 215 | 0 | — | 内容为1938年5月活动，未涉及必要事实中的具体任务。 |
| `b50b90ecdd` | deng_xiaoping_chronology_1904_1974_upper PDF 188 | 0 | — | 内容为1938年2月活动，未涉及必要事实中的具体任务。 |
| `c608b7a9b5` | deng_xiaoping_chronology_1904_1974_upper PDF 198 | 0 | — | 内容为1938年3月活动，但未提及开辟冀西根据地或与张贻祥谈话，不直接支持west_base。 |

#### `dev_intersection_mao_zhou_1949`

问题：毛泽东与周恩来在1949年有哪些有共同出席的会议？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `647408cddd` | zhou_enlai_chronology_1949_1976 PDF 429 | 0 | — | 内容涉及1949年6月下旬至7月初，无毛泽东与周恩来共同出席的会议记录。 |
| `d44e2b000c` | deng_xiaoping_chronology_1904_1974_middle PDF 199 | 0 | — | 内容为邓小平年谱，涉及政协会议和开国大典，但未提及毛泽东与周恩来共同出席的具体会议。 |
| `0b36040e82` | zhou_enlai_chronology_1949_1976 PDF 445 | 0 | — | 内容为1950年1月，时间不符。 |
| `32e3967719` | zhou_enlai_chronology_1949_1976 PDF 418 | 0 | — | 内容为1949年1月31日，时间不符。 |
| `e24b37c977` | zhou_enlai_chronology_1949_1976 PDF 434 | 0 | — | 内容为1949年9月18日至22日，未提及毛泽东与周恩来共同出席的会议。 |
| `9481413cf9` | mao_zedong_chronology_volume_4 PDF 54 | 0 | — | 内容为1949年11月25日，时间不符。 |
| `ea66074c16` | cpc_history_volume_2 PDF 380 | 0 | — | 内容为注释和参考文献，无具体会议记录。 |

#### `holdout_intersection_negative`

问题：刘伯承和邓小平是否都担任过八路军第一二九师师长？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `1399c64077` | deng_xiaoping_chronology_1904_1974_upper PDF 180 | 1 | — | 涉及一二九师和邓小平，但未明确提及邓小平任政治委员，仅部分背景。 |
| `a17207bedc` | deng_xiaoping_chronology_1904_1974_upper PDF 484 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `dd2779ed9b` | deng_xiaoping_chronology_1904_1974_upper PDF 212 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `0a30e3f3be` | deng_xiaoping_chronology_1904_1974_upper PDF 190 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `af6552f684` | deng_xiaoping_chronology_1904_1974_upper PDF 213 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `3bfb3e1eb2` | deng_xiaoping_chronology_1904_1974_upper PDF 208 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `3a2ceb584d` | deng_xiaoping_chronology_1904_1974_upper PDF 363 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `a148b5224b` | deng_xiaoping_chronology_1904_1974_upper PDF 494 | 1 | — | 涉及刘伯承、邓小平和一二九师，但未提及职务任命，仅背景。 |
| `acff31c9c8` | deng_xiaoping_chronology_1904_1974_lower PDF 612 | 0 | — | 内容为1967年关于邓小平的谈话，与一二九师职务无关。 |

#### `holdout_intersection_positive`

问题：刘伯承和邓小平有哪些共同指挥的战役？

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `b0d3840ec1` | deng_xiaoping_chronology_1904_1974_upper PDF 591 | 1 | — | 原文涉及刘伯承、邓小平在1945年11月的共同活动，但未提及任何必要战役，仅提供背景。 |
| `30496aced1` | deng_xiaoping_chronology_1904_1974_middle PDF 8 | 1 | — | 原文涉及1947年1月刘伯承、邓小平分别指挥豫皖边战役，但未提及任何必要战役，仅部分相关。 |
| `25d184d06e` | deng_xiaoping_chronology_1904_1974_upper PDF 588 | 1 | — | 原文涉及1945年11月平汉战役结束及高树勋起义，未提及必要战役。 |
| `6b09aaf208` | deng_xiaoping_chronology_1904_1974_middle PDF 75 | 0 | — | 原文涉及1948年2月大别山游击战部署，与必要战役无关。 |
| `6129d1799e` | deng_xiaoping_chronology_1904_1974_middle PDF 14 | 0 | — | 原文涉及1947年2-3月休整及指示，未提及必要战役。 |
| `6b4c088915` | deng_xiaoping_chronology_1904_1974_middle PDF 99 | 0 | — | 原文涉及1948年6月襄樊作战部署，与必要战役无关。 |
| `e01e4e8f25` | deng_xiaoping_chronology_1904_1974_middle PDF 26 | 0 | — | 原文涉及1947年6-7月鲁西南战役，与必要战役无关。 |
| `ff20fa65ac` | deng_xiaoping_chronology_1904_1974_upper PDF 259 | 0 | — | 原文涉及1939年3月刘伯承、邓小平活动，但未提及任何必要战役。 |

#### `dev_constraint_history_isolation`

问题：详细介绍淮海战役。

| 候选 | 文献/页 | rel | groups | 理由 |
|---|---|---:|---|---|
| `3fb3143019` | deng_xiaoping_chronology_1904_1974_lower PDF 658 | 0 | — | 内容为1973年邓小平视察武钢，仅提及淮海战役时间长度作比喻，无战役细节。 |
| `689a591944` | mao_selected_works_combined PDF 787 | 0 | — | 为注释内容，涉及淮海战役结果设想，但无直接支持必要事实的具体信息。 |
| `8714cf4e70` | mao_selected_works_combined PDF 797 | 1 | — | 提及淮海战役中起义和投诚事件，与战役相关但未直接支持任何必要事实。 |
| `fa9669315e` | cpc_history_volume_1 PDF 965 | 2 | battle_stage_three_time, battle_stage_three_result | 直接支持第三阶段总攻和结束：1949年1月6日总攻，10日全歼邱李兵团，俘杜聿明。 |
| `f080419eab` | mao_zedong_chronology_volume_3 PDF 355 | 1 | — | 涉及淮海战役发起时间和作战目标，但未直接支持必要事实中的具体日期或方针。 |

