# 查询理解基线：LLM 规划器

| 指标 | 结果 |
|---|---:|
| 题数 | 30 |
| 意图准确率（精确） | 46.7% |
| 意图准确率（事实族合并） | 93.3% |
| 路由准确率 | 56.7% |
| Mention Precision | 94.4% |
| Mention Recall | 85.0% |
| Mention F1 | 89.5% |
| 时间精确匹配 | 85.0%（20 题） |
| 澄清 Precision | 0.0% |
| 澄清 Recall | 0.0% |

## 逐题

| 题 | 意图 | 路由 | 缺失 mention | 多余 mention | 时间 |
|---|---|---|---|---|---|
| `qu_dev_fact_deng_1954` | event_overview（应为 timeline） | deep | — | 国务院、国防委员会 | OK |
| `qu_dev_fact_deng_school_1926` | event_overview（应为 general） | deep | — | — | OK |
| `qu_dev_congress_first` | event_overview（应为 general） | deep（应为 fast_fact） | — | — | — |
| `qu_dev_congress_short_seven` | event_overview（应为 general） | deep（应为 fast_fact） | — | — | — |
| `qu_dev_alias_mao_runzhi` | event_overview（应为 general） | deep（应为 fast_fact） | — | — | OK |
| `qu_dev_group_liudeng` | intersection | fast_fact（应为 deep） | 刘伯承、邓小平 | — | OK |
| `qu_dev_keyword_dump` | event_overview（应为 general） | deep（应为 clarify） | 解放战争 | — | OK |
| `qu_dev_comparison_meetings` | comparison | deep | — | — | — |
| `qu_dev_multihop_zunyi` | causal_analysis | deep | — | — | None / 应为 {'start': 1937, 'end': 1945, 'precision': 'period'} |
| `qu_dev_observation_snow` | viewpoint（应为 observation） | deep | — | — | — |
| `qu_dev_viewpoint_persistent` | viewpoint | deep | 抗日战争 | — | — |
| `qu_dev_timeline_zhou_1956` | timeline | fast_fact | — | — | OK |
| `qu_dev_intersection_maozhou` | intersection | fast_fact（应为 deep） | — | — | OK |
| `qu_dev_intersection_negative` | event_overview（应为 intersection） | deep | — | 中国人民政治协商会议 | OK |
| `qu_dev_source_deng_1973` | event_overview（应为 timeline） | deep | — | — | {'start': 1904, 'end': 1974, 'precision': 'year'} / 应为 {'start': 1973, 'end': 1973, 'precision': 'month'} |
| `qu_dev_month_place_deng_1949` | event_overview（应为 general） | deep | — | — | OK |
| `qu_dev_refusal_2024` | out_of_scope | deep（应为 fast_fact） | — | — | OK |
| `qu_dev_followup_zhou_1957` | timeline | fast_fact（应为 deep） | — | — | OK |
| `qu_dev_followup_deng_1953` | timeline | fast_fact（应为 deep） | — | — | OK |
| `qu_dev_alias_xiaoping` | event_overview（应为 timeline） | deep（应为 fast_fact） | 邓小平 | — | OK |
| `qu_dev_yenan_rectification` | event_overview（应为 general） | deep | — | — | — |
| `qu_dev_event_chongqing` | event_overview（应为 general） | deep | 抗日战争 | — | — |
| `qu_dev_place_taihang` | general | deep | — | — | — |
| `qu_dev_document_persistent` | viewpoint | deep | — | — | — |
| `qu_hold_multi3_mao_liu_zhou` | intersection | fast_fact（应为 clarify） | — | — | OK |
| `qu_hold_keyword_dump_longmarch` | event_overview（应为 general） | deep（应为 clarify） | — | — | OK |
| `qu_hold_out_of_range_xinhai` | out_of_scope | deep（应为 fast_fact） | — | — | — |
| `qu_hold_comparison_parties` | comparison | deep | 中国共产党、中国国民党、抗日战争 | — | None / 应为 {'start': 1937, 'end': 1945, 'precision': 'period'} |
| `qu_hold_negation` | event_overview（应为 general） | deep | — | — | OK |
| `qu_hold_source_month` | event_overview（应为 general） | deep | — | — | OK |
