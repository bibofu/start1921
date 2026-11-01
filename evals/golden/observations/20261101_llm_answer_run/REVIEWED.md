# 2026-11-01 答案与过程复核结果（A01–A12）

- 复核人：`user_in_current_chat`
- 复核依据：用户确认回答与引用无错误；必要事实仍按逐条完整性判断，未把“引用正确”等同于“所有必要事实都已写出”
- 复核包：`data/reports/golden12_llm_20261101/reviews/`
- 导入结果：`data/reports/golden12_llm_20261101/reviewed/`
- 正式评分：`data/reports/golden12_llm_20261101/report_approved.json`

## 总览

| 题 | covered | partial | missing | process | 维度失败 |
|---|---:|---:|---:|---|---|
| `dev_exact_mao_thought_party_constitution` | 1 | 1 | 0 | pass | — |
| `holdout_exact_founding_ceremony` | 1 | 0 | 1 | pass | — |
| `dev_semantic_double_hundred` | 0 | 3 | 0 | pass | — |
| `holdout_semantic_angang_constitution` | 4 | 0 | 0 | pass | — |
| `dev_multi_long_march_meetings` | 3 | 1 | 11 | fail | time_constraint |
| `holdout_multi_two_bombs_satellite` | 5 | 0 | 1 | pass | — |
| `dev_intersection_zhu_peng_command` | 2 | 0 | 0 | fail | — |
| `holdout_intersection_mao_zhu_jinggangshan` | 2 | 1 | 0 | pass | — |
| `dev_constraint_korean_war_decision` | 2 | 1 | 1 | pass | — |
| `holdout_constraint_nanchang_uprising_background` | 4 | 0 | 0 | pass | — |
| `dev_refusal_marriage_law_concubinage` | — | — | — | pass | — |
| `holdout_refusal_un_seat_timing` | — | — | — | pass | — |

合计：45 个必要事实中 **covered 24 / partial 7 / missing 14**。

## 正式指标

| 指标 | 值 |
|---|---:|
| required_fact_recall | 0.5333（24/45） |
| citation_support | 1.0000 |
| source_constraint | 1.0000 |
| time_constraint | 0.9091（10/11 适用题） |
| routing | 1.0000 |
| safe_refusal | 1.0000 |
| scope_explanation | 1.0000 |
| answer_pass | 0.4167（5/12） |

过程复核：**10 pass / 2 fail**。

## 主要发现

1. **A05 `dev_multi_long_march_meetings`**
   - 15 个必要事实中 covered 3、partial 1、missing 11；
   - 答案把 1935 年 12 月瓦窑堡会议和 1936 年 10 月会议纳入“长征期间”，`time_constraint=fail`；
   - query plan 的时间窗是 1934—1936，未收窄到长征结束（1935 年 10 月），`process=fail`。
   - 这是本批最重要的召回/时间边界问题。

2. **A07 `dev_intersection_zhu_peng_command`**
   - 答案正确：朱德总指挥、彭德怀副总指挥；
   - 但 query planner 返回 `invalid_plan` 并回退，执行计划没有 `search_queries`，`process=fail`；
   - 说明“答案对”不等于“过程对”。

3. **A02 `holdout_exact_founding_ceremony`**
   - 时间地点正确；但没有写“毛泽东在天安门城楼宣告”，`founding_declaration` 为 missing。

4. **A03 `dev_semantic_double_hundred`**
   - 三个必要事实均为 partial：答案说明了自由讨论等理由，但没有完整写出苏联学术批评/教条主义背景、官方“繁荣发展”表述，以及 4 月 28 日提出节点。

5. **A06 `holdout_multi_two_bombs_satellite`**
   - 5/6 covered；缺 1965 年突破氢弹关键技术这一节点，答案 limitations 也明确承认未覆盖。

6. **A09 `dev_constraint_korean_war_decision`**
   - 10 月 8 日命令、10 月 19 日入朝 covered；
   - 缺 10 月 2 日长电/电稿被搁置；10 月 4—5 日只写到“讨论”，未明确写“作出出兵决定”。

7. **A08 `holdout_intersection_mao_zhu_jinggangshan`**
   - 红四军、朱德军长/毛泽东党代表 covered；
   - 会师事实 partial，未写朱德、陈毅率南昌起义余部和湘南起义农军。

8. **A10 `holdout_constraint_nanchang_uprising_background`**
   - 4/4 covered，`source_constraint=pass`，是本批最完整的约束题。

9. **A11 / A12 拒答题**
   - `safe_refusal`、`scope_explanation`、`citation_support`、`routing` 全部 pass。

## 结论

- 回答与引用没有发现错误，但**事实完整性不足**，尤其 A05、A03、A09、A02、A06。
- 排序/召回指标与答案指标现在都可以计算；Golden v1.2 的题、池、候选标签、答案/过程复核均已完成。
- 下一步是合并 Golden v1.2，并同步更新 `golden_dataset.json`、`DATASET.md`、`test_golden_dataset.py` 的 20 题硬编码和 `ranking_pools.json`。
