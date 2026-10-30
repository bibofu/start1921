# 实体链接 shadow 报告（含 LLM 候选）

只检测和锚定，不改变检索。实体索引 v1 覆盖人物、文献、会议、事件、地点、组织和组合简称；LLM 只在未覆盖 span 上从索引内提名。

| 指标 | 词典 + 模糊 | 再加 LLM |
|---|---:|---:|
| Precision | 100.0% | 100.0% |
| Recall | 98.4% | 98.4% |
| F1 | 99.2% | 99.2% |
| 查询臂校验通过 | 112 / 112 | — |
| LLM 调用 / 状态 | 5 | {'used': 5} |
| LLM token | — | {'prompt_tokens': 17086, 'completion_tokens': 95, 'total_tokens': 17181} |

## 逐题

| 题 | LLM 状态 | 词典漏检 | 加 LLM 后漏检 | LLM 候选 |
|---|---|---|---|---|
| `qu_dev_fact_deng_1954` | skipped | — | — | — |
| `qu_dev_fact_deng_school_1926` | skipped | — | — | — |
| `qu_dev_congress_first` | used | — | — | — |
| `qu_dev_congress_short_seven` | used | — | — | — |
| `qu_dev_alias_mao_runzhi` | skipped | — | — | — |
| `qu_dev_group_liudeng` | skipped | — | — | — |
| `qu_dev_keyword_dump` | skipped | — | — | — |
| `qu_dev_comparison_meetings` | used | — | — | — |
| `qu_dev_multihop_zunyi` | skipped | — | — | — |
| `qu_dev_observation_snow` | used | — | — | — |
| `qu_dev_viewpoint_persistent` | skipped | — | — | — |
| `qu_dev_timeline_zhou_1956` | skipped | — | — | — |
| `qu_dev_intersection_maozhou` | skipped | — | — | — |
| `qu_dev_intersection_negative` | skipped | — | — | — |
| `qu_dev_source_deng_1973` | skipped | — | — | — |
| `qu_dev_month_place_deng_1949` | skipped | — | — | — |
| `qu_dev_refusal_2024` | skipped | 习近平 | 习近平 | — |
| `qu_dev_followup_zhou_1957` | skipped | — | — | — |
| `qu_dev_followup_deng_1953` | skipped | — | — | — |
| `qu_dev_alias_xiaoping` | skipped | — | — | — |
| `qu_dev_yenan_rectification` | skipped | — | — | — |
| `qu_dev_event_chongqing` | skipped | — | — | — |
| `qu_dev_place_taihang` | skipped | — | — | — |
| `qu_dev_document_persistent` | skipped | — | — | — |
| `qu_hold_multi3_mao_liu_zhou` | skipped | — | — | — |
| `qu_hold_keyword_dump_longmarch` | skipped | — | — | — |
| `qu_hold_out_of_range_xinhai` | skipped | — | — | — |
| `qu_hold_comparison_parties` | used | — | — | 两党→国共 |
| `qu_hold_negation` | skipped | — | — | — |
| `qu_hold_source_month` | skipped | — | — | — |
