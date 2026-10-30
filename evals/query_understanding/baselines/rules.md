# 查询理解基线：规则

| 指标 | 结果 |
|---|---:|
| 题数 | 30 |
| 意图准确率（精确） | 73.3% |
| 意图准确率（事实族合并） | 83.3% |
| 路由准确率 | 73.3% |
| Mention Precision | 96.3% |
| Mention Recall | 43.3% |
| Mention F1 | 59.8% |
| 时间精确匹配 | 90.0%（20 题） |
| 澄清 Precision | 0.0% |
| 澄清 Recall | 0.0% |

## 逐题

| 题 | 意图 | 路由 | 缺失 mention | 多余 mention | 时间 |
|---|---|---|---|---|---|
| `qu_dev_fact_deng_1954` | timeline | deep | — | — | OK |
| `qu_dev_fact_deng_school_1926` | general | deep | 邓小平年谱 | — | OK |
| `qu_dev_congress_first` | general | deep（应为 fast_fact） | — | — | — |
| `qu_dev_congress_short_seven` | general | deep（应为 fast_fact） | 中共七大 | — | — |
| `qu_dev_alias_mao_runzhi` | general | deep（应为 fast_fact） | — | — | OK |
| `qu_dev_group_liudeng` | intersection | deep | 刘伯承、邓小平 | — | OK |
| `qu_dev_keyword_dump` | general | deep（应为 clarify） | 中共七大、刘伯承、解放战争、邓小平 | — | OK |
| `qu_dev_comparison_meetings` | general（应为 comparison） | deep | 庐山会议、遵义会议 | — | — |
| `qu_dev_multihop_zunyi` | general（应为 causal_analysis） | deep | 抗日战争、遵义会议 | — | None / 应为 {'start': 1937, 'end': 1945, 'precision': 'period'} |
| `qu_dev_observation_snow` | observation | deep | 红军大学、西行漫记 | — | — |
| `qu_dev_viewpoint_persistent` | viewpoint | deep | 抗日战争、论持久战 | — | — |
| `qu_dev_timeline_zhou_1956` | timeline | fast_fact | — | — | OK |
| `qu_dev_intersection_maozhou` | intersection | deep | — | — | OK |
| `qu_dev_intersection_negative` | intersection | deep | — | — | OK |
| `qu_dev_source_deng_1973` | timeline | deep | 邓小平年谱 | — | OK |
| `qu_dev_month_place_deng_1949` | general | deep | — | — | OK |
| `qu_dev_refusal_2024` | general（应为 out_of_scope） | deep（应为 fast_fact） | 习近平 | — | OK |
| `qu_dev_followup_zhou_1957` | general（应为 timeline） | deep | 周恩来 | — | OK |
| `qu_dev_followup_deng_1953` | general（应为 timeline） | deep | 邓小平 | — | OK |
| `qu_dev_alias_xiaoping` | timeline | fast_fact | — | — | OK |
| `qu_dev_yenan_rectification` | general | deep | 延安整风 | — | — |
| `qu_dev_event_chongqing` | general | deep | 抗日战争、重庆谈判 | — | — |
| `qu_dev_place_taihang` | general | deep | 太行山 | — | — |
| `qu_dev_document_persistent` | viewpoint | deep | 毛泽东选集、论持久战 | 毛泽东 | — |
| `qu_hold_multi3_mao_liu_zhou` | intersection | deep（应为 clarify） | — | — | OK |
| `qu_hold_keyword_dump_longmarch` | general | deep（应为 clarify） | 遵义会议、长征 | — | OK |
| `qu_hold_out_of_range_xinhai` | general（应为 out_of_scope） | deep（应为 fast_fact） | 辛亥革命 | — | — |
| `qu_hold_comparison_parties` | viewpoint（应为 comparison） | deep | 中国共产党、中国国民党、抗日战争 | — | None / 应为 {'start': 1937, 'end': 1945, 'precision': 'period'} |
| `qu_hold_negation` | general | deep | — | — | OK |
| `qu_hold_source_month` | timeline（应为 general） | deep | 周恩来年谱、莫斯科 | — | OK |
