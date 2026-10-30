# LLM 实体候选 shadow 报告

对照：词典+模糊匹配 vs 再叠加 LLM 候选。LLM 只能从实体索引中选择，不能新增实体。

| 指标 | 词典 | 词典 + LLM |
|---|---:|---:|
| Precision | 88.9% | 93.3% |
| Recall | 53.3% | 93.3% |
| F1 | 66.7% | 93.3% |

## 逐题

| 题 | LLM 状态 | 词典漏检 | 加 LLM 后漏检 | LLM 候选 |
|---|---|---|---|---|
| `cand_mao_typo` | used | 毛泽东 | — | 毛润芝→毛泽东 |
| `cand_liu_typo` | used | 刘伯承 | — | 刘伯成→刘伯承 |
| `cand_zhou_traditional` | used | 周恩来、重庆 | — | 周恩來→周恩来、重慶→重庆 |
| `cand_zhu_typo` | used | 朱德 | — | 朱徳→朱德 |
| `cand_peng_typo` | used | 彭德怀 | — | 彭徳怀→彭德怀 |
| `cand_yanan_variant` | used | 延安整风 | 延安整风 | — |
| `cand_control_taihang` | used | — | — | — |
| `cand_control_snow` | used | — | — | — |
