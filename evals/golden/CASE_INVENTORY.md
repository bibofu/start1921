# 20 题逐题原文与状态清单（golden_dataset，2026-10-29）

本清单直接从 `golden_dataset.json` 生成。它是按用户 2026-10-29 裁定删除 9 题并两次改写交集题后的当前唯一工作集；旧 v3–v6 标注、协议、29 题集及其清单已清理。

## 总量

| 项目 | 数值 |
|---|---:|
| 开发题 / 保留题 | 15 / 5 |
| 可答 / 拒答 | 18 / 2 |
| 必要事实 / 证据组 | 98 / 104 |
| 有候选标签的题 | 18（182 条候选判断） |
| 有固定池的题 | 18 |
| 题目定义已批准 / 待审 | 20 / 0 |

## 本次删除与改写

删除 9 题：

- `holdout_exact_decision`
- `pilot_semantic_deng_1962_agriculture`
- `pilot_multievidence_zunyi_leadership`
- `holdout_multi_sources`
- `pilot_negative_cppcc_1949`
- `pilot_constraint_deng_1973_march`
- `holdout_constraint_source_month`
- `dev_refusal_source_year`
- `holdout_refusal_insufficient`

改写 2 题：

- `dev_intersection_mao_zhou_1949`：2026-10-29 按用户裁定扩为 7 次会议（新增 7月1日、7月9日、9月8日、12月1日）；参考答案明确不声称穷尽。
- `holdout_intersection_positive`：2026-10-29 按用户裁定收窄为 1948.11–1949.12 的淮海、渡江、进军西南三项。

## 状态口径

- `approved`：仅题目定义/来源/必要事实/回答边界已人工批准；不包含候选标签、排序池或答案。
- `pending`：题目定义仍待人工复核。
- `R`：必要证据组 Recall@K，仅对可答题有分母。
- `P/MRR/nDCG`：只有存在候选标签和固定池时暂定可评；当前 18 道可答题、K≤5 稳定。
- `Fact/Cit`：旧 13 题真实答案只有 Agent 评审；其余题没有可评真实答案。
- 正式：题目与候选标签均已人工批准（182 条）；nDCG 仍需固定池口径批准，Fact/Cit 仍无人工答案复核。
- `Agent校验` 记录的是预标注时的程序/图像核对，不是人工批准；`human_approval=False` 表示该锚点尚未获人工批准。

## 建议检查顺序

1. 先看 15 道已批准的开发题，确认题目定义、来源、事实和边界没有被后续版本悄悄改动。
2. 开发题定义已全部批准，可直接核对事实、锚点和固定池覆盖。
3. 最后看 5 道保留题；定义均已批准，重点看保留集缺约束题和拒答题的覆盖风险。
4. 所有标为 `OCR` 的锚点都需要对照 PDF 原页图像；`文本层` 锚点也建议抽查原页。
5. 2 道拒答题没有正向 R/P 分母，重点看拒答边界、范围说明和是否编造。

## 20 题速览

| # | 题 | 类别 | 分层 | 可答性 | 事实/组 | 候选标签/池 | 题目状态 | 当前可评 |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | `dev_exact_deng_1954` | exact_fact | development | answerable | 2 / 2 | 9 / 9 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 2 | `dev_exact_zhou_1954` | exact_fact | development | answerable | 6 / 6 | 9 / 9 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 3 | `dev_exact_zunyi_election` | exact_fact | development | answerable | 1 / 1 | 11 / 11 | approved | R, P/MRR/nDCG(小池) |
| 4 | `pilot_exact_deng_1952_appointment` | exact_fact | development | answerable | 1 / 1 | 9 / 9 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 5 | `holdout_exact_date` | exact_fact | holdout | answerable | 2 / 2 | 6 / 6 | approved | R, P/MRR/nDCG(小池) |
| 6 | `dev_semantic_contradiction` | semantic_retrieval | development | answerable | 3 / 3 | 12 / 12 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 7 | `dev_semantic_first_congress` | semantic_retrieval | development | answerable | 5 / 5 | 13 / 13 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 8 | `dev_semantic_investigation` | semantic_retrieval | development | answerable | 4 / 4 | 14 / 14 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 9 | `holdout_semantic_observation` | semantic_retrieval | holdout | answerable | 5 / 5 | 11 / 11 | approved | R, P/MRR/nDCG(小池) |
| 10 | `dev_multi_mao_hunan` | multi_evidence | development | answerable | 14 / 14 | 11 / 11 | approved | R, P/MRR/nDCG(小池) |
| 11 | `dev_multi_meetings` | multi_evidence | development | answerable | 12 / 15 | 11 / 11 | approved | R, P/MRR/nDCG(小池) |
| 12 | `dev_multi_zhou_periods` | multi_evidence | development | answerable | 7 / 7 | 10 / 10 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 13 | `holdout_multi_period` | multi_evidence | holdout | answerable | 3 / 3 | 9 / 9 | approved | R, P/MRR/nDCG(小池) |
| 14 | `dev_intersection_mao_zhou_1949` | intersection_hard_negative | development | answerable | 14 / 14 | 9 / 9 | approved | R, P/MRR/nDCG(小池) |
| 15 | `holdout_intersection_negative` | intersection_hard_negative | holdout | answerable | 2 / 2 | 11 / 11 | approved | R, P/MRR/nDCG(小池) |
| 16 | `holdout_intersection_positive` | intersection_hard_negative | holdout | answerable | 3 / 4 | 10 / 10 | approved | R, P/MRR/nDCG(小池) |
| 17 | `dev_constraint_history_isolation` | constraints_routing | development | answerable | 10 / 12 | 8 / 8 | approved | R, P/MRR/nDCG(小池) |
| 18 | `dev_constraint_month_place` | constraints_routing | development | answerable | 4 / 4 | 9 / 9 | approved | R, P/MRR/nDCG(小池), Fact/Cit(旧Agent) |
| 19 | `dev_refusal_einstein` | refusal_boundary | development | unanswerable | 0 / 0 | 0 / — | approved | Ref/Scope(无复核答案) |
| 20 | `pilot_refusal_out_of_scope_2024` | refusal_boundary | development | unanswerable | 0 / 0 | 0 / — | approved | Ref/Scope(旧Agent) |

## 精确事实/日期/职务

### 1. `dev_exact_deng_1954`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`exact_fact`；可答性：`answerable`；主题组：`deng_central_appointments_1952_1954`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：1954年9月，邓小平在国务院和国防委员会分别担任什么职务？
- 参考答案：1954年9月，邓小平在国务院任副总理，在中华人民共和国国防委员会任副主席。两者属于不同机构，不能混成国防部长或国防委员会主席。

**必要事实**

- `deng_vice_premier`（必要）：邓小平担任国务院副总理。
  - 证据组：`deng_vice_premier_1954`
- `deng_defense_vice_chair`（必要）：邓小平担任国防委员会副主席。
  - 证据组：`deng_defense_vice_chair_1954`

**证据组与原文**

- `deng_vice_premier_1954`：1954年9月邓小平任国务院副总理。
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 552 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：二十八日下午，会议根据周恩来总理的提名，通过国务院组成人员人选，陈云、林彪、彭德怀、邓小平、邓子恢、贺龙、陈毅、乌兰夫、李富春、李先念为副总理。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
  - `zhou_enlai_chronology_1949_1976` PDF 第 629 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：二十八日，会议根据周恩来的提名，通过国务院组成人员人选，陈云、林彪、彭德怀、邓小平、邓子恢、贺龙、陈毅、乌兰夫、李富春、李先念等十人为副总理，周恩来兼任外交部部长。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `deng_defense_vice_chair_1954`：1954年9月邓小平任国防委员会副主席。
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 552 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：根据毛泽东提名，通过中华人民共和国国防委员会副主席和委员的人选。邓小平任国防委员会副主席。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review

**禁止结论**

- 邓小平任国务院总理。（原因：原文总理是周恩来。）
- 邓小平任国防委员会主席或国防部部长。（原因：本页明确为国防委员会副主席；主席是毛泽东。）

**复核提示**

- Agent核验原文与PDF图像，人工待复核。
- 必要事实仅考机构与职务绑定，不要求模型从二十八日/任命令日期间推断日级差异。
- 邓年谱PDF552和周年谱PDF629直接支持副总理，可视为同一事实的替代证据。

### 2. `dev_exact_zhou_1954`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`exact_fact`；可答性：`answerable`；主题组：`zhou_work_1954_1956`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-11T16:57:42+08:00`
- 复核备注：用户认可全年职务变化范围与跨年履历脚注结合当年条目的证据；3A收窄为年初仍任政务院总理，9月任国务院总理由3D独立评分。总理到月、政协主席到12月25日的现有精度保留；1956年副主席仅为防错边界。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：周恩来在1954年担任哪些主要职务？
- 参考答案：应按年内变化说明：1954年初周恩来仍任中央人民政府政务院总理，兼任外交部部长；9月政府机构改组后任国务院总理，并继续兼任外交部部长。在全国政协，先任副主席，12月25日当选第二届全国委员会主席。党内主要职务包括中共中央书记处书记；中央副主席是1956年9月的后续任职，不能提前到1954年。本答案覆盖这些经源文核实的主要职务及变化，不声称列尽全部兼职。

**必要事实**

- `zhou_premier_before_september`（必要）：1954年初周恩来仍任中央人民政府政务院总理。
  - 证据组：`zhou_roles_before_1954_changes` + `zhou_government_work_jan1954`
- `zhou_party_secretariat`（必要）：1954年周恩来的党内主要职务包括中共中央书记处书记；中共中央副主席是1956年9月的后续变化。
  - 证据组：`zhou_roles_before_1954_changes`
- `zhou_cppcc_before_december`（必要）：1954年12月当选政协第二届全国委员会主席以前，周恩来担任全国政协副主席。
  - 证据组：`zhou_roles_before_1954_changes` + `zhou_cppcc_1954`
- `zhou_premier`（必要）：1954年9月周恩来被决定为国务院总理。
  - 证据组：`zhou_premier_1954`
- `zhou_foreign_minister`（必要）：周恩来兼任外交部部长。
  - 证据组：`zhou_foreign_minister_1954`
- `zhou_cppcc`（必要）：1954年12月25日当选政协第二届全国委员会主席。
  - 证据组：`zhou_cppcc_1954`

**证据组与原文**

- `zhou_roles_before_1954_changes`：职务沿革注列明周恩来原任书记处书记、政务院总理兼外长、全国政协副主席，并注明1956年9月/1954年12月任职变化。须结合当年条目，不把1953年页眉当1954年活动日期。
  - `mao_zedong_chronology_volume_5` PDF 第 7 页（SHA `ba83874b716e334221fc1105f85530900883ec9430e36a13105ab5886eb22830`；OCR）
    - 原文：周，指周恩来，当时任中共中央书记处书记（1956年9月任中央副主席）、政务院总理兼外交部部长、全国政协副主席（1954年12月任主席）。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:55:09.706508+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_government_work_jan1954`：1954年1月14日主持政务院会议，将职务沿革中的政务院任职落实到题目年份；单凭主持会议不能独立推断正式任命。
  - `zhou_enlai_chronology_1949_1976` PDF 第 597 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：【1954年1月14日】△主持政务院第二百零二次政务会议。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:55:09.706508+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_government_transition_sep1954`：政务院于1954年9月改为国务院的制度名称时间说明。注[1]解释机关更名，不将邓小平副总理职务转绑周恩来。
  - `mao_zedong_chronology_volume_5` PDF 第 7 页（SHA `ba83874b716e334221fc1105f85530900883ec9430e36a13105ab5886eb22830`；OCR）
    - 原文：政务院（1954年9月改为国务院，下同）副总理。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:55:09.706508+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_premier_1954`：1954年9月由一届全国人大决定周恩来任国务院总理。
  - `zhou_enlai_chronology_1949_1976` PDF 第 629 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：会议根据毛泽东主席的提名，决定以周恩来为国务院总理。二十八日，会议根据周恩来的提名，通过国务院组成人员人选，陈云、林彪、彭德怀、邓小平、邓子恢、贺龙、陈毅、乌兰夫、李富春、李先念等十人为副总理，周恩来兼任外交部部长。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_foreign_minister_1954`：1954年9月周恩来继续兼任外交部部长。
  - `zhou_enlai_chronology_1949_1976` PDF 第 629 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：乌兰夫、李富春、李先念等十人为副总理，周恩来兼任外交部部长。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_cppcc_1954`：1954年12月25日当选政协第二届全国委员会主席。
  - `zhou_enlai_chronology_1949_1976` PDF 第 638 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：二十五日，作《中国人民政治协商会议第二届全国委员会第一次全体会议宣言（草案）》的修改情况的说明。同日，当选为政协第二届全国委员会主席。会议通过《中国人民政治协商会议章程》。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review

**禁止结论**

- 1954年全年担任全国政协主席。（原因：政协第二届全国委员会主席任职发生在12月25日，不能倒推全年。）
- 周恩来1954年任全国人大常委会委员长。（原因：所列委员长为刘少奇，须正确绑定人物。）
- 1954年周恩来当选中共中央副主席。（原因：本题原页没有支持该说法，1956年的当选不能前移到1954年。）
- 1954年全年都担任国务院总理。（原因：政务院至1954年9月才改为国务院，年初仍为政务院总理。）

**复核提示**

- 2026-10-11用户明确认可全年职务范围与原文证据，批准题干、必要事实及边界；3A仅考年初政务院总理，9月国务院总理由3D独立评分，不以年末职务代替全年。
- 毛泽东年谱第五卷PDF7（印刷第2页）正文页眉为1953年1月，使用的是跨年职务沿革脚注：注[1]明确政务院1954年9月改为国务院（下同）；注[2]明确周恩来职务并注明全国政协1954年12月、中央副主席1956年9月的后续变化。已放大核对原页图像。
- 3A年初政务院任职采用两组AND：沿革脚注身份+周年谱PDF597的1954年1月14日政务院会议。9月机关更名说明保留为题级时间边界证据；PDF629新任总理支持3D，不再重复要求进入3A。
- 全国政协副主席到主席的转换由沿革脚注与PDF638的1954年12月25日当选记录共同支持。书记处书记有明确职务沿革原文，不把1956年中央副主席倒推到1954年。
- PDF629开头续接PDF628的1954年9月15日至28日一届全国人大条目；已核对PDF628图像的日期衔接。
- 用户已认可主要职务最低范围及沿革脚注解释；允许补充其他准确且有据的主要职务，不要求列尽临时代表团身份和兼职。日期精度保持国务院总理到1954年9月、政协主席到1954年12月25日。
- 原9条候选没有新增源页，相关性与supported_groups维持逐段原判；不得将尚未召回的新增证据算成已有候选命中。固定排序池暂不变。

### 3. `dev_exact_zunyi_election`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`exact_fact`；可答性：`answerable`；主题组：`zunyi_lushan_comparison_component`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：11 条（{'human_review': 11}）；固定池：11 个成员（basis=agent_review）
- 问题：遵义会议选举毛泽东担任什么党内职务？
- 参考答案：遵义会议选举毛泽东为中央政治局常委。依据《中国共产党历史》第一卷 PDF 第483页。

**必要事实**

- `elected_standing_member`（必要）：遵义会议选举毛泽东为中央政治局常委。
  - 证据组：`zunyi_election`

**证据组与原文**

- `zunyi_election`：会议本身选举的党内职务
  - `cpc_history_volume_1` PDF 第 483 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：遵义会议改组了中央领导机构，选举毛泽东为中央政治局常委；
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.

**禁止结论**

- 遵义会议选举毛泽东为总书记或中央主席。（原因：本题直接记载为政治局常委；领导地位的历史评价不能替换正式职务。）
- 遵义会议当场选举毛泽东为新三人团团长。（原因：不能把会后3月军事领导调整移到遵义会议；本页及续页记周恩来为新三人团团长。）

**复核提示**

- 仅评价会议直接选举职务，不要求回答会后2月、3月的组织调整。
- 与既有遵义三阶段题、遵义/庐山比较题属于同一开发主题组，不能当作独立主题或迁入保留集。

### 4. `pilot_exact_deng_1952_appointment`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`exact_fact`；可答性：`answerable`；主题组：`deng_central_appointments_1952_1954`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：1952年8月7日，邓小平被任命为什么职务？
- 参考答案：邓小平被任命为政务院副总理。依据《邓小平年谱（1904—1974）》中卷 PDF 第420页。

**必要事实**

- `appointed_vice_premier`（必要）：1952年8月7日，中央人民政府任命邓小平为政务院副总理。
  - 证据组：`appointment`

**证据组与原文**

- `appointment`：1952年8月7日的直接任命记载
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 420 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：8月7日中央人民政府任命邓小平为政务院副总理。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-22
    - 校验方法：Read extracted/OCR text and the complete rendered PDF page; not human review.

**禁止结论**

- 1952年8月7日被任命为国务院副总理（原因：该日原文机构是政务院，不能用1954年后的机构名称替换。）

**复核提示**

- 已核对PDF物理页420与印刷页1065。页眉为1952年7月，但目标条目明确为8月7日，不能用页眉月份覆盖条目日期。
- 精确事实题；同页7月调政务院工作不是8月7日任命的替代证据。

### 5. `holdout_exact_date`

- 文件：`golden_dataset.json`
- 分层：`holdout`；类别：`exact_fact`；可答性：`answerable`；主题组：`holdout_deng_moscow_study_1926`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：6 条（{'human_review': 6}）；固定池：6 个成员（basis=agent_review）
- 问题：《邓小平年谱》记载邓小平1926年在哪些学校学习？
- 参考答案：先入莫斯科东方劳动者共产主义大学，不久转入莫斯科中山大学（《邓小平年谱》上卷 PDF 第33页）。

**必要事实**

- `oriental_university`（必要）：邓小平1926年1月到达莫斯科后，先入莫斯科东方劳动者共产主义大学学习。
  - 证据组：`oriental_university`
- `sun_yat_sen_university`（必要）：不久转入莫斯科中山大学。
  - 证据组：`sun_yat_sen_university`

**证据组与原文**

- `oriental_university`：1926年1月到莫斯科后先入的学校
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 33 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：先入莫斯科东方劳动者共产主义大学学习
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `sun_yat_sen_university`：不久转入的学校
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 33 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：不久转入莫斯科中山大学
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.

**禁止结论**

- 邓小平1926年在法国里昂中法大学学习（原因：年谱记载1926年1月已到莫斯科；里昂中法大学属于此前留法时期材料，不是1926年的学校。）

**复核提示**

- OCR页PDF33（页内印刷页26）明确写“1月中旬到达莫斯科。先入莫斯科东方劳动者共产主义大学学习，不久转入莫斯科中山大学”。
- 需人工核对原页图像；本条为确定性事实题，不建议使用LLM judge。

## 语义改写/观点

### 6. `dev_semantic_contradiction`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`semantic_retrieval`；可答性：`answerable`；主题组：`mao_contradiction`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-11T17:17:35+08:00`
- 复核备注：认可三项最低事实、篇目硬约束、版本适用性与主要矛盾/主要方面防错边界；明确允许《矛盾论》中其他准确例证替代侵略战争例。
- 候选标签：12 条（{'human_review': 12}）；固定池：12 个成员（basis=agent_review）
- 问题：毛泽东在《矛盾论》中怎样分析主要矛盾？
- 参考答案：《矛盾论》认为，复杂过程存在多种矛盾，其中有一种起领导、决定作用，规定或影响其余矛盾。因此不能平均看待诸矛盾，要着力找出和抓住主要矛盾。同时要具体分析阶段和条件：在帝国主义侵略战争中，帝国主义与被侵略国家的矛盾成为主要矛盾，国内阶级矛盾暂居次要地位；其他条件下主次地位会变化。主要矛盾还应与一个矛盾内部的主要方面区分。依据《毛泽东选集》合订本PDF196—198页。上述侵略战争仅为参考例证，用户允许以《矛盾论》中其他准确例证说明条件变化导致主次地位变化；不要求照抄该例。

**必要事实**

- `definition`（必要）：复杂事物有多种矛盾，其中主要矛盾起领导、决定作用，规定或影响其他矛盾。
  - 证据组：`principal_role`
- `method`（必要）：分析时不能平均看待所有矛盾，应找出并着重抓住主要矛盾。
  - 证据组：`find_and_prioritize_principal`
- `conditional_priority`（必要）：主要与次要矛盾的地位随具体条件和发展阶段改变，并用《矛盾论》中准确的例证说明这种变化；帝国主义侵略战争例可由本文其他准确例证替代。
  - 证据组：`changing_conditions_change_priority`

**证据组与原文**

- `principal_role`：复杂过程中主要矛盾规定或影响其他矛盾
  - `mao_selected_works_combined` PDF 第 196 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：在复杂的事物的发展过程中，有许多的矛盾存在，其中必有一种是主要的矛盾，由于它的存在和发展规定或影响着其他矛盾的存在和发展。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `find_and_prioritize_principal`：区分主次，着力找出和抓住主要矛盾
  - `mao_selected_works_combined` PDF 第 197 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：因此，研究任何过程，如果是存在着两个以上矛盾的复杂过程的话，就要用全力找出它的主要矛盾。捉住了这个主要矛盾，一切问题就迎刃而解了。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `changing_conditions_change_priority`：主次地位取决于具体阶段和条件，以侵略战争与非战争压迫作比较
  - `mao_selected_works_combined` PDF 第 197 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：这时，帝国主义和这种国家之间的矛盾成为主要的矛盾，而这种国家内部各阶级的一切矛盾（包括封建制度和人民大众之间这个主要矛盾在内），便都暂时地降到次要和服从的地位。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.

**禁止结论**

- 主要矛盾永远不变。（原因：原文以不同条件的中国社会说明矛盾地位的变化。）
- 主要矛盾就是矛盾的主要方面，两者完全相同。（原因：PDF196—198页将两种情形分别分析：多个矛盾间的主次与一个矛盾双方的主次。）
- 1950年代国内主要矛盾的具体判断就是《矛盾论》1937年原文的判断。（原因：必须区分篇目与不同时期的具体政治判断。）

**复核提示**

- 题干的硬来源约束是《矛盾论》篇目本身，不是独占本地合订文件版本；目录命中、其他文章或后来讲话不能替代本文论证，可靠其他版本的同文可用于支持。
- 用户认可三项最低事实，并允许《矛盾论》中其他准确例证替代侵略战争例。必须说明具体条件变化怎样导致主次地位变化；仅泛提各阶段都有主要矛盾不能满计。现有changing_conditions_change_priority锚点仍是已标注的侵略战争段落，固定锚点Recall不代表所有合格例证的穷尽覆盖，不能用于否定另有原文支持的正确答案。
- 主要矛盾与矛盾主要方面的区分用于防止错误扩展；当前3个必要事实分母不额外要求完整展开主要方面学说。
- 2026-10-11用户批准本题题干、原文、三项必要事实及回答边界；本批不批准候选相关性、排序池或历史答案，不自动重判原有候选。新例证的答案与交付引用须逐项核验。
- 候选0=不支持问题的对象/限定，1=相关背景或不完整支持，2=直接支持至少一个必要事实；supported_groups只列完整支持的必要组。
- Precision与MRR的相关阈值为grade>=1；nDCG使用0/1/2分级且仅对声明、冻结并充分判定的小池有效，不代表全语料穷尽相关性。
- 本地《毛泽东选集》为民间整合版，用户认可其作为本轮证据基准。使用实际PDF物理页，不误称官方单卷页码。其他例证须核验其《矛盾论》篇目身份、原文与引用支持；新增候选/锚点另行标注，不因用户认可替代原则而自动生成相关性标签。

### 7. `dev_semantic_first_congress`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`semantic_retrieval`；可答性：`answerable`；主题组：`party_foundation_1921`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：13 条（{'human_review': 13}）；固定池：13 个成员（basis=agent_review）
- 问题：党的头一次全国大会讲了些什么、形成了哪些决定？
- 参考答案：这里的'头一次全国大会'指1921年中国共产党第一次全国代表大会。会议听取各地党、团组织情况，讨论党纲和实际工作计划。主要决定包括：通过党的纲领，确定党名及纲领目标；规定统一组织和严格纪律；把集中领导工人运动、组织工会和教育工人作为工作重点；通过当前实际工作决议，提出维护无产阶级利益的独立政策；暂设中央局，选举陈独秀为书记，张国焘负责组织、李达负责宣传。依据《中国共产党历史》第一卷PDF120—122页。

**必要事实**

- `programme`（必要）：一大讨论并通过党的纲领，确定名称为中国共产党，以推翻资产阶级政权、承认无产阶级专政、消灭资本家私有制等为纲领内容，并提出联合共产国际。
  - 证据组：`programme_and_name`
- `discipline`（必要）：党纲还规定全党建立统一组织和严格纪律。
  - 证据组：`organization_discipline`
- `workers`（必要）：大会要求集中力量领导工人运动，首先组织工会和教育工人。
  - 证据组：`worker_movement_priority`
- `independence`（必要）：当前实际工作的决议提出维护无产阶级利益的独立政策，当时不与其他党派建立联系。
  - 证据组：`independent_policy`
- `leadership`（必要）：大会暂设中央局，由陈独秀、张国焘、李达组成，陈独秀任书记，张国焘负责组织、李达负责宣传。
  - 证据组：`central_bureau_election`

**证据组与原文**

- `programme_and_name`：通过党的纲领、确定名称和根本目标
  - `cpc_history_volume_1` PDF 第 121 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：党的一大通过的中国共产党纲领，确定党的名称为“中国共产党”，规定党的纲领是：革命军队必须与无产阶级一起推翻资本家阶级的政权；承认无产阶级专政，直到阶级斗争结束，即直到消灭社会的阶级区分；消灭资本家私有制，没收机器、土地、厂房和半成品等生产资料，归社会公有；联合共产国际。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `organization_discipline`：党纲含有统一组织和严格纪律要求
  - `cpc_history_volume_1` PDF 第 121 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：党纲还规定，在全党建立统一的组织和严格的纪律
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `worker_movement_priority`：集中领导工人运动，首先组织工会和教育工人
  - `cpc_history_volume_1` PDF 第 121 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：同纲领规定的奋斗目标相适应，大会要求党集中力量领导工人运动，首先是组织工会和教育工人。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `independent_policy`：当前实际工作决议与维护无产阶级利益的独立政策
  - `cpc_history_volume_1` PDF 第 122 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：大会决定，在反对军阀官僚的斗争中，在争取言论、出版、集会自由的斗争中，党应采取独立的政策以维护无产阶级的利益，不同其他党派建立任何联系。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `central_bureau_election`：暂设中央局，陈独秀任书记及成员分工
  - `cpc_history_volume_1` PDF 第 122 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：党的一大考虑到党员数量少和地方组织尚不健全的情况，决定暂不成立中央执行委员会，只设立中央局作为中央的临时领导机构。大会选举陈独秀、张国焘、李达组成中央局，选举陈独秀担任书记，张国焘负责组织工作，李达负责宣传工作。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.

**禁止结论**

- 一大制定了1954年宪法。（原因：这是第一届全国人民代表大会第一次会议的内容，非党的一大。）
- 一大确立共产党员以个人身份加入国民党的政策。（原因：不得把1923年党三大的决策移到1921年一大。）
- 一大选举毛泽东为中央局书记，或者选出正式中央执行委员会。（原因：来源记载陈独秀任书记，且当时暂不成立中央执行委员会。）

**复核提示**

- 语义改写测试：'党的头一次全国大会'应识别为中国共产党第一次全国代表大会，不能混入苏维埃一大、全国人大、团代会或党的其他届次。
- 必要组为纲领、组织纪律、工运重点、独立政策、中央局五项；开会时间地点和转移嘉兴属于可补充背景，不在当前必要事实分母内。
- PDF121页抽取文本在'严格的纪律'后出现'也方组织'连字错误；原图实际为'地方组织必须接受中央的监督和指导'。锚点避开损坏部分，未静默改写OCR后假装精确匹配。
- 原问题三分支前5并集10条均为其他会议或无关片段，没有必要原文；此处仍独立保留121—122页金标。若固定池全为0，nDCG因IDCG为0不可评，不能假定为有效零分。
- 来源经启用目录、实际PDF SHA-256、抽取页和原图核对；本文件均为Agent暂定标注，未经人工批准。
- 候选0=不支持问题的对象/限定，1=相关背景或不完整支持，2=直接支持至少一个必要事实；supported_groups只列完整支持的必要组。
- Precision与MRR的相关阈值为grade>=1；nDCG使用0/1/2分级且仅对声明、冻结并充分判定的小池有效，不代表全语料穷尽相关性。
- 为避免固定池缺少正例导致IDCG=0，独立原文核验找到的PDF121—122页3个现有chunk另纳入固定池。它们不出现在本轮真实运行排名中；当前前5全不相关仍应如实保留。

### 8. `dev_semantic_investigation`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`semantic_retrieval`；可答性：`answerable`；主题组：`mao_investigation`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-11T17:17:35+08:00`
- 复核备注：认可四项最低观点、本地版本适用性和其他可靠来源可支持；亲身调查不等于每个点本人包办，反本本主义不等于反理论。
- 候选标签：14 条（{'human_review': 14}）；固定池：14 个成员（basis=agent_review）
- 问题：毛泽东关于调查研究有哪些观点？
- 参考答案：可概括至少四个核心观点：先调查实际情况再发言、形成结论或决定；学习理论必须联系中国实际，反对本本主义；领导者要亲身深入调查，不能只靠书面报告；向群众和有经验的干部学习，通过调查会和讨论取得情况。主要依据《反对本本主义》（1930年，合订本PDF81—85页）及《〈农村调查〉的序言和跋》（1941年，PDF467页）。这是核心观点的最低覆盖集，不是全部相关论述的穷尽清单。

**必要事实**

- `evidence_before_conclusion`（必要）：先了解问题的实际情况再形成结论和政策，不能未调查就凭想象发言或决策。
  - 证据组：`investigate_before_concluding`
- `oppose_book_worship`（必要）：要学习马克思主义理论，但必须同中国实际相结合，反对脱离实际的本本主义。
  - 证据组：`theory_with_actual_conditions`
- `leaders_investigate`（必要）：领导者应亲身深入实际调查，不能把阅读书面报告当作实际调查的替代。
  - 证据组：`personal_in_depth_investigation`
- `learn_by_discussion`（必要）：要向有经验的群众和干部学习，通过调查会、讨论了解真实情况。
  - 证据组：`learn_from_people_through_discussion`

**证据组与原文**

- `investigate_before_concluding`：先调查再作结论、决定；没有调查没有发言权
  - `mao_selected_works_combined` PDF 第 81 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：一切结论产生于调查情况的末尾，而不是在它的先头。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `theory_with_actual_conditions`：学习理论与中国实际结合，反对脱离实际的本本主义
  - `mao_selected_works_combined` PDF 第 82 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：马克思主义的“本本”是要学习的，但是必须同我国的实际情况相结合。我们需要“本本”，但是一定要纠正脱离实际情况的本本主义。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `personal_in_depth_investigation`：领导者必须亲自深入实际调查，不能只靠书面报告
  - `mao_selected_works_combined` PDF 第 85 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：一定都要亲身从事社会经济的实际调查，不能单靠书面报告，因为二者是两回事。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.
- `learn_from_people_through_discussion`：向有经验的群众/干部学习，用调查会讨论取得情况
  - `mao_selected_works_combined` PDF 第 467 页（SHA `e4ce0e3f2d452429be2d050b7bfab8147ede25c0ebb7fbf91595718c558cd9ae`；文本层）
    - 原文：开调查会，是最简单易行又最忠实可靠的方法，我用这个方法得了很大的益处，这是比较什么大学还要高明的学校。到会的人，应是真正有经验的中级和下级的干部，或老百姓。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-09-23
    - 校验方法：Actual PDF SHA-256 checked; read full extracted page and rendered physical PDF page. Agent review only.

**禁止结论**

- 毛泽东主张不需要学习理论，只要调查就够了。（原因：《反对本本主义》明确说马克思主义的本本是要学习的，但须联系实际。）
- 先定结论再找材料证明即可。（原因：原文要求结论产生于调查之后。）

**复核提示**

- 开放观点题：4个必要组只定义核心观点最低覆盖集，不穷尽毛泽东各时期的全部调查研究论述；有证据的其他观点不因未列在此处而判错。
- 以两个真实篇目为独立证据基准，而非以本轮检索返回结果反向选择金标。其他启用文献对同一观点的可靠记录可作为替代支持，题干未限制只能用选集。
- 1930年关于亲身调查的要求不等于每个调查点都只能由本人包办；1961年讲话明确可亲自调查若干单位，同时组织和指导调查班子，不应制造矛盾。
- 2026-10-11用户认可题干、四项最低观点、原文证据及回答边界；原页已由Agent核验，候选分级和排序池仍为原Agent预标，未获本批人工批准。
- 候选0=不支持问题的对象/限定，1=相关背景或不完整支持，2=直接支持至少一个必要事实；supported_groups只列完整支持的必要组。
- Precision与MRR的相关阈值为grade>=1；nDCG使用0/1/2分级且仅对声明、冻结并充分判定的小池有效，不代表全语料穷尽相关性。
- 本地《毛泽东选集》在目录中标注为民间整合版，包含不同来源系列；用户认可其作为本轮证据基准。引用使用实际PDF物理页，不能误称为官方单卷页码；其他启用文献的可靠记录仍可支持本题。

### 9. `holdout_semantic_observation`

- 文件：`golden_dataset.json`
- 分层：`holdout`；类别：`semantic_retrieval`；可答性：`answerable`；主题组：`holdout_snow_red_army_schools`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：11 条（{'human_review': 11}）；固定池：11 个成员（basis=agent_review）
- 问题：斯诺在《西行漫记》中怎样描述红军学校的学习和训练安排？
- 参考答案：斯诺记红军大学有四个分部、八百名学员，第一分部约二百名营团师级干部，受四个月高级军政训练；第二、三分部六个月，第四分部训练工兵、骑兵、炮兵；课程分政治和军事两类；文娱时间有球类、读书和俱乐部学习。

**必要事实**

- `red_university_size`（必要）：红军大学共有四个分部、八百名学员，第一分部约二百名学员。
  - 证据组：`red_university_size`
- `first_division_training`（必要）：第一分部学员多为营、团、师级指挥员或政委，接受高级军政训练，为期四个月。
  - 证据组：`first_division_training`
- `other_divisions`（必要）：第二、三分部上课六个月；第四分部主要训练工兵、骑兵干部和炮兵部队。
  - 证据组：`other_divisions`
- `curriculum`（必要）：课程分为政治课程和军事课程；政治课程包括政治知识、中国革命问题、政治经济学、党的建设等，军事课程包括抗日战争的战略问题、运动战、游击战术等。
  - 证据组：`curriculum`
- `recreation`（可选）：文娱时间学员打篮球、网球、乒乓球，读书报或在俱乐部学习。
  - 证据组：`recreation`

**证据组与原文**

- `red_university_size`：红军大学的规模和分部
  - `red_star_over_china` PDF 第 143 页（SHA `d289729c3301f2937dd4206996985ce7e00755738c283b7251e7c0ef8e0335bf`；OCR）
    - 原文：这是红军大学的第一分部，有二百名左右学员。红大一共有四个分部，八百名学员
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `first_division_training`：第一分部的学员来源和训练期限
  - `red_star_over_china` PDF 第 145 页（SHA `d289729c3301f2937dd4206996985ce7e00755738c283b7251e7c0ef8e0335bf`；OCR）
    - 原文：第一分部的学员大部分是红军中的营、团、师级指挥员或政委，接受高级军政训练。为期四个月
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `other_divisions`：第二、三分部和第四分部的训练安排
  - `red_star_over_china` PDF 第 145 页（SHA `d289729c3301f2937dd4206996985ce7e00755738c283b7251e7c0ef8e0335bf`；OCR）
    - 原文：第二分部和第三分部上课六个月。第四分部主要“训练工兵、骑兵干部、炮兵部队”
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `curriculum`：政治课程和军事课程
  - `red_star_over_china` PDF 第 146 页（SHA `d289729c3301f2937dd4206996985ce7e00755738c283b7251e7c0ef8e0335bf`；OCR）
    - 原文：政治课程有：政治知识、中国革命问题、政治经济学、党的建设、共和国的策略问题、列宁主义、民主主义的历史基础、日本的政治社会状况。军事课程有：抗日战争的战略问题、运动战、抗日战争中的游击战术的发展
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `recreation`：文娱时间和学习活动
  - `red_star_over_china` PDF 第 143 页（SHA `d289729c3301f2937dd4206996985ce7e00755738c283b7251e7c0ef8e0335bf`；OCR）
    - 原文：有的学员在两个球场上打篮球；有的在保安城外一条黄河支流旁边草地上的一个网球场上打网球。有的在打乒乓球，有的在写东西，读新到的书报，或者在他们简单的“俱乐部”中学习
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.

**禁止结论**

- 红军大学只有一个分部，学员都是普通士兵（原因：原文为四个分部、八百名学员；第一分部多为营、团、师级指挥员或政委。）

**复核提示**

- 这是开放语义题，允许同义改写和有据扩展；最低事实是四个分部/规模、第一分部训练、其他分部、课程。
- “学习安排”可包括文娱活动，但列为可选事实，不作为必要覆盖。
- 均为OCR页，需人工核对原页图像。

## 多证据/跨期/比较

### 10. `dev_multi_mao_hunan`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`multi_evidence`；可答性：`answerable`；主题组：`mao_hunan_1921_1926`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：11 条（{'human_review': 11}）；固定池：11 个成员（basis=agent_review）
- 问题：逐年梳理毛泽东1921—1926年在湖南的活动。
- 参考答案：以下按年份列出已核实的主要活动，属于可复核的最低覆盖清单，不代表这六年全部活动。
1921年：8月中旬回长沙，同何叔衡创办湖南自修大学，任指导主任并负实际领导责任；10月10日在长沙建立中国共产党湖南支部，任支部书记。（《毛泽东年谱》第1卷，PDF第95、97页）
1922年：5月底中共湘区执行委员会成立，任书记，区委设在长沙清水塘；10月初在清水塘同任树德等研究泥木工人罢工，认为时机成熟，10月6日长沙泥木工人举行罢工。（同书，PDF第104、110页）
1923年：4月离长沙赴上海到中央工作前，在长沙向李维汉移交湘区委工作，介绍全区工作与组织情况；9月16日回到长沙，按中央决定并受林伯渠委托，在湖南筹建国民党组织。（同书，PDF第121、126页）
1924年：12月因过劳患病，经中央同意回湘疗养，年底偕杨开慧等回到湖南。这是本轮明确核实的该年湖南行止，不能因为这一条较少就写成全年未在湖南活动。（同书，PDF第138页）
1925年：2月6日到韶山，养病同时走访农家、开展社会调查；3月以毛福轩等为骨干组织秘密农协；4月通过杨开慧、李耿侯等发动教师创办农民夜校；6月中旬发展党员、成立中共韶山支部，委派毛福轩为书记；8月组织农民开展平粜阻禁谷米斗争，争取平价售粮并阻止外运。（同书，PDF第139—141、143页）
1926年：12月17日由汉口到长沙，参加湖南全省第一次农民代表大会并商讨起草决议案；12月20日出席湖南全省第一次工人、农民代表大会联合欢迎大会，作《工农商学联合的问题》演说，强调农民问题是国民革命的中心问题。（同书，PDF第183页）
地点以活动实际发生地判断。在上海或广州参加大会、在江西安源开展活动，不能仅因与湖南有关就计入湖南活动；1926年底准备调查的记载也不能改写为当年已经完成1927年的湖南五县考察。

**必要事实**

- `y1921_self_study_university`（必要）：1921年8月中旬回到长沙，同何叔衡创办湖南自修大学，任指导主任并负实际领导责任。
  - 证据组：`y1921_self_study_university`
- `y1921_hunan_branch`（必要）：1921年10月10日在长沙建立中国共产党湖南支部，任支部书记。
  - 证据组：`y1921_hunan_branch`
- `y1922_xiang_committee`（必要）：1922年5月底中共湘区执行委员会成立，毛泽东任书记，区委机关设在长沙清水塘。
  - 证据组：`y1922_xiang_committee`
- `y1922_changsha_carpenters_strike`（必要）：1922年10月初在长沙清水塘同任树德等研究泥木工人罢工，认为时机成熟；长沙泥木工人于10月6日罢工。
  - 证据组：`y1922_changsha_carpenters_strike`
- `y1923_handover_in_changsha`（必要）：1923年4月离长沙赴上海到中央工作前，在长沙向李维汉移交湘区委工作，并介绍全区工作和组织情况。
  - 证据组：`y1923_handover_in_changsha`
- `y1923_return_build_kmt`（必要）：1923年9月16日回到长沙，遵照中共中央决定并受林伯渠委托，在湖南筹建国民党组织。
  - 证据组：`y1923_return_build_kmt`
- `y1924_return_for_convalescence`（必要）：1924年12月因过劳患病，经中央同意回湘疗养，年底偕杨开慧等回到湖南。
  - 证据组：`y1924_return_for_convalescence`
- `y1925_shaoshan_inquiry`（必要）：1925年2月6日同杨开慧携子女到韶山，回韶山后一边养病一边走访农家开展社会调查。
  - 证据组：`y1925_shaoshan_inquiry`
- `y1925_secret_peasant_associations`（必要）：1925年3月以毛福轩等为骨干，在韶山一带组织秘密农协，发展会员并召集骨干讨论农民斗争。
  - 证据组：`y1925_secret_peasant_associations`
- `y1925_peasant_night_schools`（必要）：1925年4月通过杨开慧、李耿侯等发动进步教师，在韶山一带创办农民夜校。
  - 证据组：`y1925_peasant_night_schools`
- `y1925_shaoshan_party_branch`（必要）：1925年6月中旬发展党员并成立中共韶山支部，委派毛福轩为党支部书记。
  - 证据组：`y1925_shaoshan_party_branch`
- `y1925_fair_price_grain_campaign`（必要）：1925年8月在韶山组织农民开展平粜阻禁谷米斗争，发动农民迫使地主平价售粮并阻止其外运。
  - 证据组：`y1925_fair_price_grain_campaign`
- `y1926_hunan_peasant_congress`（必要）：1926年12月17日由汉口到长沙，参加湖南全省第一次农民代表大会，并同湖南同志商讨起草决议案。
  - 证据组：`y1926_hunan_peasant_congress`
- `y1926_workers_peasants_welcome_speech`（必要）：1926年12月20日出席湖南全省第一次工人、农民代表大会联合欢迎大会，作《工农商学联合的问题》演说，强调农民问题是国民革命的中心问题。
  - 证据组：`y1926_workers_peasants_welcome_speech`

**证据组与原文**

- `y1921_self_study_university`：1921年8月中旬回到长沙，同何叔衡创办湖南自修大学，任指导主任并负实际领导责任。
  - `mao_zedong_chronology_volume_1` PDF 第 95 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：8月中旬回到长沙，住船山学社。在文化书社和清水塘同何叔衡、易礼容多次商量在湖南成立共产党支部的问题。同旬和何叔衡创办湖南自修大学。自修大学是在船山学社董事会总理仇鳌和社长贺民范支持下，利用船山学社社址和经费创办的。贺民范为首任校长，毛泽东任指导主任，负实际领导责任。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1921_hunan_branch`：1921年10月10日在长沙建立中国共产党湖南支部，任支部书记。
  - `mao_zedong_chronology_volume_1` PDF 第 97 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：10月10日在长沙建立中国共产党湖南支部，任支部书记，成员有何叔衡、易礼容等。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1922_xiang_committee`：1922年5月底中共湘区执行委员会成立，毛泽东任书记，区委机关设在长沙清水塘。
  - `mao_zedong_chronology_volume_1` PDF 第 104 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：5月底中共湘区执行委员会成立。毛泽东任书记，何叔衡、易礼容、李立三等为委员。区委机关设在长沙清水塘二十二号。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1922_changsha_carpenters_strike`：1922年10月初在长沙清水塘同任树德等研究泥木工人罢工，认为时机成熟；长沙泥木工人于10月6日罢工。
  - `mao_zedong_chronology_volume_1` PDF 第 110 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：10月初在清水塘住处同泥木工会主任任树德等研究泥木工人罢工问题。认为罢工时机已完全成熟，可以提出罢工口号。五日，泥木工会委员会连夜召集会议，一致赞同毛泽东的意见。10月6日长沙泥木工人全体罢工。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1923_handover_in_changsha`：1923年4月离长沙赴上海到中央工作前，在长沙向李维汉移交湘区委工作，并介绍全区工作和组织情况。
  - `mao_zedong_chronology_volume_1` PDF 第 121 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：同月离长沙去上海，到中共中央工作。行前向继任中共湘区委书记的李维汉移交工作，把领导工人运动、农民运动和社会主义青年团的具体工作，分别交给郭亮、夏曦等。在清水塘湘区委召开的两次会议上，向李维汉介绍全区工作情况和组织情况。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1923_return_build_kmt`：1923年9月16日回到长沙，遵照中共中央决定并受林伯渠委托，在湖南筹建国民党组织。
  - `mao_zedong_chronology_volume_1` PDF 第 126 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：9月16日遵照中共中央的决定并受国民党本部总务部副部长林伯渠的委托，回到长沙，在湖南筹建国民党组织。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1924_return_for_convalescence`：1924年12月因过劳患病，经中央同意回湘疗养，年底偕杨开慧等回到湖南。
  - `mao_zedong_chronology_volume_1` PDF 第 138 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：12月因工作过于劳累患病。经中共中央同意，回湘疗养。年底，偕杨开慧等回到湖南。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1925_shaoshan_inquiry`：1925年2月6日同杨开慧携子女到韶山，回韶山后一边养病一边走访农家开展社会调查。
  - `mao_zedong_chronology_volume_1` PDF 第 139 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；OCR）
    - 原文：2月6日和杨开慧携毛岸英、毛岸青到韶山，并带回一百多斤重的书籍。回韶山后，一边养病一边作些社会调查。到朋友、同学、亲戚和左邻右舍农家走访，或邀请亲友到韶山南岸家中，谈家常、讲时事。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1925_secret_peasant_associations`：1925年3月以毛福轩等为骨干，在韶山一带组织秘密农协，发展会员并召集骨干讨论农民斗争。
  - `mao_zedong_chronology_volume_1` PDF 第 140 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：3月以毛福轩、毛新枚、钟志申、庞叔侃、李耿侯等为骨干组织秘密农协，并通过他们发展会员。不久，韶山一带出现一些秘密农民协会组织。毛泽东经常召集农协骨干开会，讲述土豪劣绅如何压迫、剥削农民，农民应当怎样向土豪劣绅开展斗争等。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1925_peasant_night_schools`：1925年4月通过杨开慧、李耿侯等发动进步教师，在韶山一带创办农民夜校。
  - `mao_zedong_chronology_volume_1` PDF 第 140 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：4月通过杨开慧、李耿侯等发动进步教师，利用原来的公立学校、族校、祠堂等，在韶山一带创办农民夜校。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1925_shaoshan_party_branch`：1925年6月中旬发展党员并成立中共韶山支部，委派毛福轩为党支部书记。
  - `mao_zedong_chronology_volume_1` PDF 第 141 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：6月中旬中共韶山特别支部成立。经过几个月的培养和了解，毛泽东同毛福轩介绍毛新枚、李耿侯、钟志申、庞叔侃等加入中国共产党。一天，在毛泽东家中阁楼上秘密举行新党员入党仪式，并成立中共韶山支部。委派毛福轩为党支部书记。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1925_fair_price_grain_campaign`：1925年8月在韶山组织农民开展平粜阻禁谷米斗争，发动农民迫使地主平价售粮并阻止其外运。
  - `mao_zedong_chronology_volume_1` PDF 第 143 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：8月组织农民开展“平祟阻禁“谷米斗争。本年韶山一带遭受大旱，田地龟裂，禾苗枯黄。正值青黄不接民食奇缺时节，地主乘机围积居奇，高抬谷价。毛泽东召集党支部和农协骨干开会，决定发动农民，迫使地主开仓平祟，派钟志申、庞叔侃同土豪、上七都团防局长成胥生交涉。成不肯，且把谷子偷运到银田镇，准备运往湘潭等地高价出售。毛泽东要毛福轩、毛新枚等率领农民数百人，携带锄头、扁担、萝筐，夜奔银田，阻其出境。成胥生见人多势众，被迫将谷子平价卖给农民。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1926_hunan_peasant_congress`：1926年12月17日由汉口到长沙，参加湖南全省第一次农民代表大会，并同湖南同志商讨起草决议案。
  - `mao_zedong_chronology_volume_1` PDF 第 183 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：12月17日由汉口到长沙，参加湖南全省第一次农民代表大会，并准备考察湖南农民运动情况。大会期间，曾同湖南的同志商讨起草各种决议案
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.
- `y1926_workers_peasants_welcome_speech`：1926年12月20日出席湖南全省第一次工人、农民代表大会联合欢迎大会，作《工农商学联合的问题》演说，强调农民问题是国民革命的中心问题。
  - `mao_zedong_chronology_volume_1` PDF 第 183 页（SHA `47fe85f4b19b77943c395fd8664a98e881fd49212bc6ea217c27bff700eac3e6`；文本层）
    - 原文：12月20日出席湖南全省第一次工人代表大会和第一次农民代表大会联合举行的欢迎大会(2)。在欢迎会上作《工农商学联合的问题》演说，指出：“国民革命是各阶级联合革命，但有一个中心问题。国民革命的中心问题，就是农民问题，一切都要靠农民问题的解决。”
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Agent read the complete rendered PDF page and checked the dated entry against page text; not human review.

**禁止结论**

- 1924年没有在湖南活动，或全年都在上海、广州。（原因：PDF138有年底回湖南的肯定记载；检索未找到不能推成无活动。）
- 1924年12月已经开展1925年韶山农民运动，或已在1924年2月6日回韶山。（原因：PDF138只到年底回湖南；PDF139—143所载韶山行程及农民运动属于1925年。）
- 在上海、嘉兴参加中共一大，在广州参加中共三大或国民党一大属于在湖南开展的活动。（原因：参会地点与代表地区或活动议题必须区分；湖南代表不等于活动在湖南。）
- 江西安源的活动可直接算作湖南当地活动。（原因：湘区组织管辖及往返湖南不改变安源实际所在地；须分开醴陵、长沙等湖南段。）
- 1926年没有回湖南，或已完成1927年1月开始的湖南农村实地考察。（原因：PDF183明确12月17日到长沙；PDF184的县域巡视是拟进行，PDF185明确1927年1月4日从长沙启程考察，不能提前为1926年已完成。）
- 12月28日报道列出的湖南十余县都已在1926年逐一实地考察。（原因：PDF184用语为拟于日内分赴，属于计划而非完成记录。）
- 毛泽东本人担任1925年成立的中共韶山支部书记。（原因：PDF141明确委派毛福轩为书记。）
- 本清单是1921—1926年在湖南全部活动，未列出的日期可判为没有活动。（原因：本版建议的是最低覆盖集，不是闭世界全量事件表；附加活动要另核证据。）

**复核提示**

- 本次核验得到六年均有肯定证据；1924年只要求年底回湘疗养这一项，1926年有12月长沙大会活动。六年不能任意留空，也不要求编造每月完整行程。
- 本版建议的最低覆盖（待人工裁定）：1921/1922/1923各2事实、1924为1事实、1925为5事实、1926为2事实，总14事实/14证据组。事实微平均与按年宏平均须分开，不能把本清单称为全量活动召回分母。
- 1925年保留社会调查、秘密农协、农民夜校、韶山党组织、平粜阻禁五项，分别代表调查、群众组织、教育、政党组织和经济斗争，不把同一行动的多场会议拆成多个事实。雪耻会、安化访问、长沙汇报等可作有据补充，不抬高本版分母。
- PDF138页眉为1924年11月，但页面最后条目明确12月与年底；月份判定以条目为准。PDF121的同月在1923年4月段，PDF126的目标条目明确9月16日，不能由8月页眉覆盖。
- PDF143提取文本把平粜识别为平祟，原图已核为平粜；quote按remove_whitespace_only保留原提取字符及引号，事实和参考答案使用经原图确认的术语。不会改写语料或伪称OCR已修复。
- PDF110脚注对泥木罢工宣言有一说是经毛泽东看过后发出的，故最低必要事实不要求断言其独自起草宣言。
- 额外原图核验PDF144可支持1925年8月底在长沙报告韶山农运，PDF184可支持1926年12月底开办短训班并延续1927年1月初；二者属允许有据补充的活动，不进入本版固定14事实分母。
- 边界原图PDF185明确1927年1月4日从长沙启程到湖南农村考察；此页用于排除跨年错误，不是1921—1926的正面召回目标。
- 需要阶段性诊断：六年拆解与地点约束、逐年必要组召回、重排保留、真实生成上下文覆盖、逐年最终事实/引用；本轮无新运行，不声称已测或已通过。
- 未建立本题充分分级的候选池。检索Precision/MRR/nDCG保持待候选标注状态；不得把湖南关键词附近的所有候选自动判相关，也不得把池外项判0。

### 11. `dev_multi_meetings`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`multi_evidence`；可答性：`answerable`；主题组：`zunyi_lushan_comparison_component`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：11 条（{'human_review': 11}）；固定池：11 个成员（basis=agent_review）
- 问题：比较遵义会议和1959年庐山会议各自讨论的核心问题、会议进程和后续影响。
- 参考答案：遵义会议是1935年1月15—17日召开的中央政治局扩大会议，集中纠正军事指挥和战略战术错误，处理迫切的军事与组织问题。多数与会者反对博古的总结报告，赞同毛泽东等人的意见；会议指定张闻天起草决议，委托常委审查，然后发支部讨论。组织上选举毛泽东为中央政治局常委、取消原三人团，仍由朱德、周恩来指挥军事，周恩来负党内对指挥军事下最后决心的责任。该书评价会议在危急关头挽救了党、红军和中国革命（《中国共产党历史》第一卷 PDF 481—484页）。1959年庐山会议包括中央政治局扩大会议和八届八中全会，初意是继续纠正大跃进以来的左倾错误。彭德怀的信在肯定成绩的同时提出工作问题和总结教训，其信于7月16日印发讨论，并引出对信件性质的争论，会议延长。7月23日毛泽东讲话后，会议主题转向反右；8月2—16日八届八中全会接续召开，形成反右倾及将彭德怀等认定为反党集团的决议（第二卷 PDF 526、529—530、533—535页；反党集团是当时会议的错误认定，不能作为对彭德怀等人的事实背书）。会后继续批判彭德怀等人，并在全党开展反右倾斗争；这打断了纠左进程，使大跃进和人民公社化中已暴露的左倾错误重新发展，又破坏党内民主，使个人崇拜、个人专断倾向进一步发展，打击了向党反映实际情况、提出批评意见的同志（第二卷 PDF 538、540页）。前者纠正军事领导错误并产生挽救危局的作用，后者从纠左转为反右，给经济工作与党内民主造成严重后果；比较时须把两个会议各自的议题、进程和影响分别挂靠证据。

**必要事实**

- `zunyi_date`（必要）：遵义会议是1935年1月15日至17日召开的中央政治局扩大会议。
  - 证据组：`zunyi_date`
- `zunyi_core`（必要）：遵义会议集中纠正军事指挥和战略战术错误，解决迫切的军事与组织问题。
  - 证据组：`zunyi_core`
- `zunyi_process`（必要）：多数与会者反对博古的总结报告、赞同毛泽东等意见；会议指定张闻天起草决议，交常委审查并发支部讨论。
  - 证据组：`zunyi_process`
- `zunyi_organization`（必要）：会议选举毛泽东为政治局常委、取消原三人团，仍由朱德和周恩来指挥军事，周恩来负党内最后决心责任。
  - 证据组：`zunyi_organization`
- `zunyi_influence`（必要）：该书评价遵义会议在危急关头挽救了党、红军和中国革命。
  - 证据组：`zunyi_influence`
- `lushan_initial`（必要）：1959年庐山会议包括政治局扩大会议和八届八中全会，初衷是继续纠正大跃进以来的左倾错误。
  - 证据组：`lushan_initial`
- `lushan_letter`（必要）：彭德怀的信在肯定成绩的同时提出工作问题和总结教训；7月16日印发讨论并引出对信件性质的争论，会议延长。
  - 证据组：`lushan_letter_content` + `lushan_letter_discussion`
- `lushan_turn`（必要）：7月23日毛泽东讲话后，会议主题由纠左转为反右。
  - 证据组：`lushan_turn_date` + `lushan_turn`
- `lushan_plenum`（必要）：8月2日至16日八届八中全会接续召开，形成反右倾及将彭德怀等认定为反党集团的决议。
  - 证据组：`lushan_plenum_date` + `lushan_plenum_decisions`
- `lushan_party_campaign`（必要）：庐山会议后继续批判彭德怀等人，并在全党开展反右倾斗争。
  - 证据组：`lushan_party_campaign`
- `lushan_economic_effect`（必要）：反右倾打断纠左进程，使大跃进和人民公社化中已暴露的左倾错误重新发展。
  - 证据组：`lushan_economic_effect`
- `lushan_democratic_effect`（必要）：反右倾破坏党内民主，发展个人崇拜、个人专断倾向，打击提出批评意见的同志。
  - 证据组：`lushan_democratic_effect`

**证据组与原文**

- `zunyi_date`：遵义会议时间与会议性质
  - `cpc_history_volume_1` PDF 第 481 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：1935年1月15日至17日，中央政治局在遵义召开扩大会议（即遵义会议）。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `zunyi_core`：核心议题及讨论边界
  - `cpc_history_volume_1` PDF 第 484 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：遵义会议明确地回答了红军的战略战术方面的是非问题，指出博古、李德军事指挥上的错误，同时改变中央的领导特别是军事领导，解决了党内所面临的最迫切的组织问题和军事问题，
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `zunyi_process`：发言分歧和决议形成程序
  - `cpc_history_volume_1` PDF 第 482 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：周恩来、朱德、刘少奇等多数与会同志相继发言，不同意博古的总结报告，同意毛泽东、张闻天、王稼祥提出的提纲和意见。只有个别人在发言中为博古、李德的错误辩解。李德坚决不接受批评。会议最后指定张闻天起草决议，委托常委审查，然后发到支部讨论。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `zunyi_organization`：会议直接组织决定
  - `cpc_history_volume_1` PDF 第 483 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：遵义会议改组了中央领导机构，选举毛泽东为中央政治局常委；决定常委中再进行适当的分工；取消在长征前成立的“三人团”，仍由最高军事首长朱德、周恩来为军事指挥者，而周恩来是党内委托的对于指挥军事下最后决心的负责者。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `zunyi_influence`：遵义会议历史影响
  - `cpc_history_volume_1` PDF 第 484 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：这次会议，在极端危急的历史关头，挽救了党，挽救了红军，挽救了中国革命。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_initial`：庐山会议构成与初衷
  - `cpc_history_volume_2` PDF 第 526 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：1959年七八月间举行的中央政治局扩大会议和八届八中全会（合称庐山会议），原意是进一步纠正“大跃进”运动以来“左”的错误。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_letter_content`：彭德怀信的内容，不把信写成全面否定大跃进
  - `cpc_history_volume_2` PDF 第 529 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：这封三千字的长信分为两个部分：一是“1958年大跃进的成绩是肯定无疑的”；二是“如何总结工作中的经验教训”。在肯定总路线、“大跃进”和人民公社化运动成绩的前提下，信中着重指出1958年以来工作中的问题，
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_letter_discussion`：7月16日印发讨论及会议延长
  - `cpc_history_volume_2` PDF 第 530 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：7月16日，毛泽东以“彭德怀同志的意见书”这样一个标题，批示将信印发给与会者讨论。毛泽东在中央政治局常委的范围内提出，要“评论这封信的性质”。根据毛泽东的意见，中央政治局常委决定延长会议时间。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_turn_date`：7月23日讲话的日期和主体
  - `cpc_history_volume_2` PDF 第 533 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：7月23日，毛泽东在大会上发表长篇讲话。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_turn`：讲话之后会议议题的逆转
  - `cpc_history_volume_2` PDF 第 534 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：这个讲话使会议气氛骤然紧张，形势急转直下。会议主题由纠“左”变为反右。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_plenum_date`：八届八中全会接续政治局扩大会议
  - `cpc_history_volume_2` PDF 第 534 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：8月2日至16日，党的八届八中全会在庐山召开。此次全会是接续中央政治局扩大会议举行的。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_plenum_decisions`：全会形成错误批判的决议
  - `cpc_history_volume_2` PDF 第 535 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：全会最后通过会议公报和《为保卫党的总路线、反对右倾机会主义而斗争》、《关于开展增产节约运动的决议》、《关于以彭德怀同志为首的反党集团的错误的决议》、《关于撤销黄克诚同志中央书记处书记的决定》四个文件，认定彭、黄、张、周结成“右倾机会主义反党集团”，
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_party_campaign`：会后全党反右倾
  - `cpc_history_volume_2` PDF 第 538 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：庐山会议后，在继续揭发批判彭德怀等人的同时，全党范围内开展了一场声势浩大的“反右倾”斗争。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_economic_effect`：经济影响是纠左中断和错误重新发展
  - `cpc_history_volume_2` PDF 第 540 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：在经济方面，它打断了第一次郑州会议以来纠“左”的进程，使“大跃进”和人民公社化运动中许多已经暴露出来、有待纠正的“左”倾错误重新发展起来。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `lushan_democratic_effect`：党内民主及言路受损
  - `cpc_history_volume_2` PDF 第 540 页（SHA `85d4304f4dab786cb88414700520754dd8b00150e8d24d7717346acc7b9a0b5e`；文本层）
    - 原文：在组织方面，“反右倾”斗争严重破坏了党内民主生活，使个人崇拜和个人专断的不良倾向在党内进一步发展。一大批敢于实事求是地向党反映实际情况、提出批评意见的同志受到打击。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.

**禁止结论**

- 遵义会议全面解决了全部政治路线问题。（原因：第484页明确说没有全面讨论政治路线问题。）
- 庐山会议自始至终只有反右、没有前期纠左。（原因：第526页明确记载初衷，第534页记载逆转。）
- 1959年庐山会议完成了纠左、纠正了大跃进错误。（原因：第540页记载纠左被中断，不能抹去后续严重影响。）
- 彭德怀等实际组成了里通外国的反党集团。（原因：这是当时批判中的错误认定，叙述会议决定须作明确归属，不能作为历史事实背书。）
- 同一段遵义会议引文可以证明庐山会议的过程或影响。（原因：两会议的人物、年代、动作必须绑定各自证据。）

**复核提示**

- 开放比较题；12个必要事实是两会议×核心问题/进程/影响的最低覆盖，不是会议全部事实。允许有证据的补充，但不能以篇幅替代覆盖。
- 3月新三人团的具体旬别不进入此题必要事实；原三阶段题存在跨来源中旬/下旬差异，另留人工裁定记录。
- 庐山后果补到PDF第540页，不能仅凭第536页章节标题“严重后果”声称已经证成具体经济和组织后果。
- 复合事实的两个证据组是AND；单页只给出日期或跨页指示词“这个讲话”时，不足以独立证明完整因果时间链。

### 12. `dev_multi_zhou_periods`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`multi_evidence`；可答性：`answerable`；主题组：`zhou_work_1954_1956`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-11T17:17:35+08:00`
- 复核备注：认可六项代表活动加综合、非排他主题归纳及年月精度；5E收紧为知识分子中的绝大部分，不能推及全体。
- 候选标签：10 条（{'human_review': 10}）；固定池：10 个成员（basis=agent_review）
- 问题：按时间和主题梳理周恩来从1954年至1956年的主要经历，并说明这三年工作重点的变化。
- 参考答案：以经过标注的代表性活动梳理：1954年4月率团赴日内瓦会议，9月任国务院总理兼外交部长，12月任全国政协主席，体现和平外交和国家制度建设并行。1955年4月参加万隆亚非会议、倡导求同存异；6月向人大常委会说明一五计划草案，外交团结与国内建设计划同时推进。1956年1月作知识分子问题报告，指出知识分子中的绝大部分已经是工人阶级的一部分，强调发挥其社会主义建设作用；6月针对急躁冒进提出压缩开支与基本建设、综合平衡，反映人才动员和建设节奏调整的重要性。上述是三年主要主题的最低覆盖框架，不是所有活动清单；外交、统战、经济工作贯穿期间，不能说某年完全停止外交或只做一种工作。

**必要事实**

- `zhou_1954_geneva`（必要）：1954年4月率中国代表团赴日内瓦会议，开展国际和平外交。
  - 证据组：`zhou_1954_geneva`
- `zhou_1954_government`（必要）：1954年9月任国务院总理并兼任外交部长，12月当选全国政协主席。
  - 证据组：`zhou_1954_government` + `zhou_1954_cppcc`
- `zhou_1955_bandung`（必要）：1955年4月在万隆亚非会议上倡导求同存异，争取团结合作。
  - 证据组：`zhou_1955_bandung`
- `zhou_1955_plan`（必要）：1955年6月向全国人大常委会说明第一个五年计划草案，参与推进建设计划。
  - 证据组：`zhou_1955_first_plan`
- `zhou_1956_intellectuals`（必要）：1956年1月作知识分子问题报告，强调知识分子中的绝大部分已经是工人阶级的一部分，并发挥其建设作用。
  - 证据组：`zhou_1956_intellectuals`
- `zhou_1956_balance`（必要）：1956年6月针对经济建设急躁冒进提出压缩支出、基建，主张在综合平衡中稳步前进。
  - 证据组：`zhou_1956_balance`
- `zhou_synthesis`（必要）：按这些代表性活动，可概括1954年和平外交与国家制度建设、1955年亚非团结与一五建设推进、1956年知识人才动员与经济综合平衡；不是各年排他的唯一工作重点。
  - 证据组：`zhou_1954_geneva` + `zhou_1954_government` + `zhou_1955_bandung` + `zhou_1955_first_plan` + `zhou_1956_intellectuals` + `zhou_1956_balance`

**证据组与原文**

- `zhou_1954_geneva`：1954年4月以首席代表身份率中国代表团赴日内瓦会议。
  - `zhou_enlai_chronology_1949_1976` PDF 第 604 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：【1954年4月20日】△率领中国代表团飞离北京赴瑞士参加日内瓦会议，夜宿新西伯利亚，次日下午飞抵莫斯科。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1954_government`：1954年9月任国务院总理并兼外交部长。
  - `zhou_enlai_chronology_1949_1976` PDF 第 629 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：会议根据毛泽东主席的提名，决定以周恩来为国务院总理。二十八日，会议根据周恩来的提名，通过国务院组成人员人选，陈云、林彪、彭德怀、邓小平、邓子恢、贺龙、陈毅、乌兰夫、李富春、李先念等十人为副总理，周恩来兼任外交部部长。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1954_cppcc`：1954年12月当选政协第二届全国委员会主席，统战工作继续。
  - `zhou_enlai_chronology_1949_1976` PDF 第 638 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：二十五日，作《中国人民政治协商会议第二届全国委员会第一次全体会议宣言（草案）》的修改情况的说明。同日，当选为政协第二届全国委员会主席。会议通过《中国人民政治协商会议章程》。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1955_bandung`：1955年4月参加亚非会议并提出求同存异。
  - `zhou_enlai_chronology_1949_1976` PDF 第 653 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：补充发言强调：中国代表团参加会议的目的，“是来求团结而不是来吵架的”，“是来求同而不是来立异的”，“我们的会议应该求同而存异”。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1955_first_plan`：1955年6月27日向人大常委会说明一五计划草案。
  - `zhou_enlai_chronology_1949_1976` PDF 第 664 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：【1955年6月27日】△出席第一届全国人大常委会第十七次会议，对将要提请第一届全国人民代表大会第二次会议审定的《发展国民经济的第一个五年计划（草案）》，作了说明。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1956_intellectuals`：1956年1月作知识分子问题报告，强调发挥知识分子作用。
  - `zhou_enlai_chronology_1949_1976` PDF 第 687 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：【1956年1月14日－20日】△出席中共中央召开关于知识分子问题的会议。十四日，作《关于知识分子问题的报告》。《报告》中说：“我国的知识界的面貌在过去六年来已经发生了根本的变化。”知识分子中的“绝大部分已经成为国家工作人员，已经为社会主义服务，已经是工人阶级的一部分”。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `zhou_1956_balance`：1956年6月批评急躁冒进，提出削减支出压缩基建，推动综合平衡。
  - `zhou_enlai_chronology_1949_1976` PDF 第 708 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
    - 原文：【1956年6月4日】△出席中共中央会议。在讨论《关于一九五五年国家决算和一九五六年国家预算的报告（初稿）》时，代表国务院介绍半年来经济建设急躁冒进所带来的种种矛盾和不平衡问题，提出继续削减财政支出、压缩基本建设投资的意见。据此，会议提出了既反保守又反冒进，即在综合平衡中稳步前进的经济建设方针。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review

**禁止结论**

- 1955年参加日内瓦会议、1954年参加万隆会议。（原因：核心会议年份颠倒。）
- 1956年以后才首次担任国务院总理。（原因：1954年9月的任职已由源页直接支持。）
- 三年工作从外交完全转向经济，1956年不再参与外交。（原因：主题归纳不能推出排他性替代，年谱仍有大量1956年外交活动。）
- 1953年或1958年的活动属于1954至1956年的经历。（原因：超出题目限定时间；回溯提及不能直接算成当期活动。）

**复核提示**

- 2026-10-11用户批准本题题干、原文、必要事实及回答边界；本题为开发集，和1954任职题共享证据，不可拆到独立验收集。
- 用户认可7个必要证据组、6项代表活动和1项跨年综合作为最低覆盖，不要求穷尽。知识分子事实保留“绝大部分”限定；本题按年月要求，第一批职务题的日级要求不迁移到本题。
- 综合重点变化属于基于所列活动的归纳，不按唯一措辞匹配，也不允许把各年工作写成排他性替代。
- 1954日内瓦以实际率团出发为锚点；1955万隆quote来自该年4月19日条目（同页日期可复核）；知识分子报告为1956年1月14日。
- 相关性2=直接支持所标必要活动；1=时间内真实活动或相关准备/回溯背景但不足以完成必要事实；0=年份不符且仅一般人物共现。

### 13. `holdout_multi_period`

- 文件：`golden_dataset.json`
- 分层：`holdout`；类别：`multi_evidence`；可答性：`answerable`；主题组：`holdout_deng_1938_tasks`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：邓小平在1938年承担了哪些主要工作任务？
- 参考答案：1938年1月任一二九师政治委员；3月就开辟冀西根据地提出建立军分区；10月就冀南反“扫荡”准备提出建议。

**必要事实**

- `d129_commissar`（必要）：1938年1月5日，邓小平接替张浩任八路军第一二九师政治委员。
  - 证据组：`d129_commissar`
- `west_base`（必要）：1938年3月，邓小平就开辟冀西根据地同张贻祥谈话，提出准备在冀西建立军分区。
  - 证据组：`west_base`
- `jinan_counter`（必要）：1938年10月15日，邓小平致电徐向前、宋任穷等，对冀南反“扫荡”准备工作提出建议。
  - 证据组：`jinan_counter`

**证据组与原文**

- `d129_commissar`：1938年1月任一二九师政治委员
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 174 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：邓小平接替张浩任一二九师政治委员
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `west_base`：1938年3月开辟冀西根据地
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 191 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：3月4日就开辟冀西根据地问题，同张贻祥谈话，向他介绍冀西的情况，提出准备在冀西建立军分区
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `jinan_counter`：1938年10月冀南反“扫荡”准备
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 240 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：10月15日鉴于日军即将大举“扫荡”华北，致电徐向前、宋任穷并告左权、刘伯承，对冀南反“扫荡”的准备工作提出四点建议
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.

**禁止结论**

- 1938年邓小平任一二九师师长（原因：1938年1月他接替张浩任政治委员；师长是刘伯承。）

**复核提示**

- 人工裁定改为单一年份任务题；只取三项代表性任务，不声称穷尽1938年全部工作。
- OCR页，需人工核对原页图像。

## 人物交集/困难负例

### 14. `dev_intersection_mao_zhou_1949`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`intersection_hard_negative`；可答性：`answerable`；主题组：`mao_zhou_meetings_1949`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T20:19:39+08:00`
- 复核备注：用户 2026-10-29 要求把 1949 年共同出席的政治局会议纳入本题；据此加入 7 次有原文列名的政治局会议，共 14 项。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：毛泽东与周恩来在1949年有哪些有共同出席的会议？
- 参考答案：可据原文列出以下十四项，清单以年谱明确记载为限、不声称穷尽1949年全年：①6月7日会见陈嘉庚（毛3 PDF521）；②7月1日纪念中国共产党成立二十八周年大会（毛3 PDF531）；③7月9日全国铁路职工临时代表会议等集会（毛3 PDF536）；④9月8日会见和宴请程潜（毛3 PDF572）；⑤9月25日国旗国徽国歌纪年国都协商座谈会（毛3 PDF585）；⑥10月24日接见绥远军区负责人和傅作义（毛4 PDF32）；⑦10月26日中共中央政治局会议（毛4 PDF35）；⑧11月2日政治局会议（PDF41）；⑨11月9日政治局会议（PDF45）；⑩11月25日政治局会议（PDF54）；⑪11月28日政治局会议（PDF56）；⑫12月1日政治局会议（PDF59）；⑬12月1日同十二位民主人士座谈（PDF58）；⑭12月4日政治局会议（PDF60）。共同出席必须逐条得到直接支持；政治局会议以原文列名“周恩来……出席”为准。

**必要事实**

- `joint_meeting_0607`（必要）：1949年6月7日，毛泽东同刘少奇、周恩来在香山双清别墅会见陈嘉庚，谈中外局势等问题。
  - 证据组：`joint_meeting_0607`
- `joint_meeting_0701`（必要）：1949年7月1日，毛泽东同朱德、周恩来等出席中共中央华北局、北平市委在先农坛运动场召开的纪念中国共产党成立二十八周年大会。
  - 证据组：`joint_meeting_0701`
- `joint_meeting_0709`（必要）：1949年7月9日，毛泽东同朱德、周恩来出席全国铁路职工临时代表会议暨全国机务会议全体代表和铁道部、铁道兵团、平津铁路管理局部分工作人员在中南海怀仁堂的集会。
  - 证据组：`joint_meeting_0709`
- `joint_meeting_0908`（必要）：1949年9月8日，毛泽东在中南海会见和宴请程潜，朱德、刘少奇、周恩来等参加会见和宴会。
  - 证据组：`joint_meeting_0908`
- `joint_consultation_0925`（必要）：1949年9月25日晚，毛泽东在中南海召集关于国旗、国徽、国歌、纪年、国都问题的协商座谈会，周恩来明确列为出席者。
  - 证据组：`joint_consultation_0925`
- `joint_meeting_1024`（必要）：1949年10月24日，毛泽东在中南海菊香书屋接见绥远军区负责人和傅作义，谈起义部队的团结改造及与非党人士长期合作，周恩来参加。
  - 证据组：`joint_meeting_1024`
- `politburo_19491026`（必要）：1949年10月26日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻列席。
  - 证据组：`politburo_19491026`
- `politburo_19491102`（必要）：1949年11月2日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻列席。
  - 证据组：`politburo_19491102`
- `politburo_19491109`（必要）：1949年11月9日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、彭真、林伯渠出席，薄一波、聂荣臻列席。
  - 证据组：`politburo_19491109`
- `politburo_19491125`（必要）：1949年11月25日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、彭真、董必武、林伯渠出席，饶漱石、李富春、薄一波、聂荣臻列席。
  - 证据组：`politburo_19491125`
- `politburo_19491128`（必要）：1949年11月28日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、董必武、林伯渠出席，薄一波、聂荣臻、李富春、饶漱石列席。
  - 证据组：`politburo_19491128`
- `politburo_19491201`（必要）：1949年12月1日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻、饶漱石、李富春、邓子恢、安子文列席。
  - 证据组：`politburo_19491201`
- `joint_meeting_1201`（必要）：1949年12月1日，毛泽东同张澜、李济深、郭沫若、黄炎培、沈钧儒等十二位民主人士座谈，磋商毛泽东访问苏联时签订中苏条约事宜，朱德、周恩来、林伯渠参加。
  - 证据组：`joint_meeting_1201`
- `politburo_19491204`（必要）：1949年12月4日，毛泽东主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻、李富春、饶漱石、邓子恢列席。
  - 证据组：`politburo_19491204`

**证据组与原文**

- `joint_meeting_0607`：1949年6月7日会见陈嘉庚，周恩来参加
  - `mao_zedong_chronology_volume_3` PDF 第 521 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：6月7日和刘少奇、周恩来在香山双清别墅会见陈嘉庚，就中外局势等问题进行交谈。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `joint_meeting_0701`：1949年7月1日纪念中国共产党成立二十八周年大会，周恩来出席
  - `mao_zedong_chronology_volume_3` PDF 第 531 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：7月1日和朱德、周恩来等出席中共中央华北局、北平市委在先农坛运动场召开的纪念中国共产党成立二十八周年大会。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `joint_meeting_0709`：1949年7月9日全国铁路职工临时代表会议等集会，周恩来出席
  - `mao_zedong_chronology_volume_3` PDF 第 536 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：和朱德、周恩来出席全国铁路职工临时代表会议暨全国机务会议全体代表和铁道部、铁道兵团、平津铁路管理局部分工作人员在中南海怀仁堂的集会。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `joint_meeting_0908`：1949年9月8日会见和宴请程潜，周恩来参加
  - `mao_zedong_chronology_volume_3` PDF 第 572 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：八日，毛泽东在中南海会见和宴请程潜，朱德、刘少奇、周恩来等参加会见和宴会。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `joint_consultation_0925`：1949年9月25日晚国旗国徽国歌纪年国都协商座谈会，周恩来出席
  - `mao_zedong_chronology_volume_3` PDF 第 585 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：9月25日出席中国人民政协全体会议。会议继续听取各党派、团体代表发言。会上，毛泽东接受北平市妇女和儿童代表献花。同日晚上，在中南海召集关千国旗、国徽、国歌、纪年、国都问题协商座谈会。出席座谈会的有周恩来、郭沫若、沈雁冰、黄炎培、陈嘉庚、张奚若、马叙伦、田汉、徐悲鸿、李立三、洪深、艾青、马寅初、梁思成、马思聪、吕骥、贺绿汀等。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `joint_meeting_1024`：1949年10月24日接见绥远军区负责人和傅作义，周恩来参加
  - `mao_zedong_chronology_volume_4` PDF 第 32 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：10月24日在中南海菊香书屋接见绥远军区负责人高克林、姚桔、裴周玉(1)和傅作义，谈对绥远起义部队的团结改造以及同非党人士长期合作问题。周恩来、薄一波、聂荣臻参加。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `politburo_19491026`：1949年10月26日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 35 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：同日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真(1)、董必武、林伯渠出席，薄一波、聂荣臻列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `politburo_19491102`：1949年11月2日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 41 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：11月2日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `politburo_19491109`：1949年11月9日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 45 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：11月9日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、彭真、林伯渠出席，薄一波、聂荣臻列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `politburo_19491125`：1949年11月25日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 54 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：11月25日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、彭真、董必武、林伯渠出席，饶漱石、李富春(1)、薄一波、聂荣臻列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `politburo_19491128`：1949年11月28日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 56 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：11月28日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、董必武、林伯渠出席，薄一波、聂荣臻、李富春、饶漱石列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `politburo_19491201`：1949年12月1日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 59 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：同日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻、饶漱石、李富春、邓子恢、安子文列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.
- `joint_meeting_1201`：1949年12月1日同十二位民主人士座谈，周恩来参加
  - `mao_zedong_chronology_volume_4` PDF 第 58 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：12月1日同张澜、李济深、郭沫若、黄炎培、沈钧儒等十二位民主人士座谈，磋商毛泽东访问苏联时签订中苏条约事宜，朱德、周恩来、林伯渠参加。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `politburo_19491204`：1949年12月4日 中共中央政治局会议，周恩来出席
  - `mao_zedong_chronology_volume_4` PDF 第 60 页（SHA `fc9d8eb877991db15f55d3862fc949d4732b3e0bf5cf7d71fdfa4de2228b3113`；文本层）
    - 原文：12月4日主持召开中共中央政治局会议，刘少奇、朱德、周恩来、陈云、彭真、董必武、林伯渠出席，薄一波、聂荣臻、李富春、饶漱石、邓子恢列席。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; date taken from the chronology entry context; PDF image review is still pending human confirmation.

**禁止结论**

- 仅据毛3 PDF476 的代表名单和谈判基础说明，断言毛泽东是1949年4月1日国共和谈中共代表团成员，并和周恩来共同出席该日谈判。（原因：代表名单不能证明毛泽东本人出席了该日谈判，属于邻近条目串用。）
- 仅据毛3 PDF521，或跨用6月7日的参与名单，断言周恩来参加了1949年6月8日毛泽东会见傅作义。（原因：6月8日条目没有列周恩来，6月7日的名单不能移植到次日。）
- 以上十四项就是毛泽东与周恩来1949年共同出席的全部会议。（原因：年谱仍可能记载其他会议；本题只冻结可逐条核验的十四项，不声称穷尽。）

**复核提示**

- 人工裁定改为“共同出席的会议”，因此删除了共同致电宋庆龄和共同离开西柏坡两条非会议事件。
- 开放题最低覆盖为三个可核验的共同会见/座谈会，不是全年会议清单；额外有效会议允许补充，不以未标注直接判负。
- 6月7日/6月8日及3月26日代表团说明仍是困难负例线索，不是历史否定；其他新直接证据须待核。
- 尚未生成真实候选池或候选相关性标签；Precision/MRR/nDCG 待下一步标注。
- 2026-10-29 用户复核认为原答案不完整；按用户选择的改法重写事实、证据组和参考答案，待再次送审。
- 2026-10-29 按用户要求加入 7 次政治局会议（10/26、11/2、11/9、11/25、11/28、12/1、12/4）。

### 15. `holdout_intersection_negative`

- 文件：`golden_dataset.json`
- 分层：`holdout`；类别：`intersection_hard_negative`；可答性：`answerable`；主题组：`holdout_liu_deng_129_roles`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：11 条（{'human_review': 11}）；固定池：11 个成员（basis=agent_review）
- 问题：刘伯承和邓小平是否都担任过八路军第一二九师师长？
- 参考答案：不是。刘伯承任一二九师师长，邓小平任一二九师政治委员。

**必要事实**

- `liu_commander`（必要）：1937年9月一二九师改编时，刘伯承任师长。
  - 证据组：`liu_commander`
- `deng_commissar`（必要）：1938年1月，邓小平接替张浩任一二九师政治委员。
  - 证据组：`deng_commissar`

**证据组与原文**

- `liu_commander`：一二九师改编时的师长任命
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 158 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：以刘伯承为师长，徐向前为副师长，倪志亮为参谋长，张浩为师政训处主任
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `deng_commissar`：邓小平接任一二九师政治委员
  - `deng_xiaoping_chronology_1904_1974_upper` PDF 第 174 页（SHA `8208c6ed269f34191a0c8236d53ee6c1b037ae35290fbf0be8f6996333c97c12`；OCR）
    - 原文：邓小平接替张浩任一二九师政治委员
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.

**禁止结论**

- 刘伯承和邓小平都担任过一二九师师长（原因：刘伯承为师长，邓小平为政治委员；不能把政委写成师长。）

**复核提示**

- 这是角色绑定负例：两段原文分别证明两人的不同职务，不能因为同师共事就把职务合并。
- OCR页，需人工核对原页图像。

### 16. `holdout_intersection_positive`

- 文件：`golden_dataset.json`
- 分层：`holdout`；类别：`intersection_hard_negative`；可答性：`answerable`；主题组：`liu_deng_joint_campaigns`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:48:24+08:00`
- 复核备注：用户 2026-10-29 批准收窄到1948.11–1949.12三项后的题目定义。
- 候选标签：10 条（{'human_review': 10}）；固定池：10 个成员（basis=agent_review）
- 问题：1948年11月至1949年12月，刘伯承和邓小平共同指挥了哪些战略决战和战略进军？
- 参考答案：在1948年11月至1949年12月这一窗口内，可据原文列出：①淮海战役：总前委由刘伯承、陈毅、邓小平、粟裕、谭震林组成，刘伯承、陈毅、邓小平为常委，邓小平任书记（邓年谱中卷 PDF131）；②渡江战役（京沪杭战役）：1949年2月9日邓小平主持总前委扩大会议讨论渡江作战，并与刘伯承等联名致电中央军委；4月第二、第三野战军及地方部队百万余人强渡长江（PDF155、173）；③进军西南：1949年8月刘伯承、邓小平联名致信林彪等，安排二野进军西南的粮草保障（PDF189）。窗口外的邯长、上党、陇海、定陶等不属本题；本题只评估窗口内三项，不声称是两人全部共同指挥的战役。

**必要事实**

- `huaihai_command`（必要）：1948年11月6日至1949年1月10日，淮海战役由刘伯承、陈毅、邓小平、粟裕、谭震林组成的总前委统筹，刘伯承、陈毅、邓小平为常委，邓小平任书记。
  - 证据组：`huaihai_1948`
- `yangtze_1949`（必要）：1949年2月9日，邓小平主持总前委扩大会议讨论渡江作战，并与刘伯承等联名致电中央军委报告；4月，第二、第三野战军及地方部队百万余人强渡长江。
  - 证据组：`yangtze_planning_1949` + `yangtze_crossing_1949`
- `southwest_1949`（必要）：1949年8月，刘伯承、邓小平联名致信林彪等，请华中地区保障第二野战军进军西南的粮草供应。
  - 证据组：`southwest_1949`

**证据组与原文**

- `huaihai_1948`：淮海战役总前委组成与邓小平任书记
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 131 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：为统筹战役作战和地方支前事宜，中共中央军委决定由刘伯承、陈毅、邓小平、粟裕、谭震林组成总前敌委员会，由刘伯承、陈毅、邓小平为常委，临机处置一切。邓小平为总前委书记。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `yangtze_planning_1949`：总前委讨论渡江作战，邓小平与刘伯承等联名报告
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 155 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：2月9日在徐州主持召开总前委扩大会议，具体讨论关于渡江作战的八个问题。同日，和刘伯承、陈毅、粟裕、谭震林致电中共中央军委，报告会议讨论情况
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `yangtze_crossing_1949`：第二、第三野战军百万余人强渡长江
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 173 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：从夜晚起至二十一日，第二、第三野战军及地方部队共百万余人在东起江阴、西至九江东北湖口间五百余公里的战线上，分中、东、西三路强渡长江天堑，彻底摧毁国民党军构筑的长江防线。
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.
- `southwest_1949`：刘伯承、邓小平联名安排二野进军西南保障
  - `deng_xiaoping_chronology_1904_1974_middle` PDF 第 189 页（SHA `da2ffdcf984368e69d22ca43c02839d0afb573b94ea563d27d0df29e5b9937be`；OCR）
    - 原文：8月10日和刘伯承、张际春、李达致信林彪、邓子恢、萧克、赵尔陆（1〕：“二野此次奉命进军西南路经华中地区，关于粮食、柴草供应方面，请格外予以帮助
    - Agent校验：status=verified_against_page_text; verified_at=2026-10-29
    - 校验方法：Programmatic whitespace-only anchor check against the effective page text; PDF image review is still pending human confirmation.

**禁止结论**

- 刘伯承和邓小平在1948年11月至1949年12月只共同指挥了淮海战役。（原因：渡江战役和进军西南同样有原文支持，漏项即为错误。）
- 渡江战役由第三野战军单独指挥，刘伯承、邓小平未参加总前委。（原因：总前委由刘伯承、陈毅、邓小平、粟裕、谭震林组成，邓小平任书记。）
- 进军西南由贺龙单独指挥，第二野战军未参加。（原因：原文记载二野奉命进军西南，刘伯承、邓小平联名安排保障。）
- 淮海战役总前委书记是粟裕或陈毅。（原因：原文明确邓小平为总前委书记。）

**复核提示**

- 人工裁定改为“共同指挥的战役”；只纳入原文明确写共同指挥或“和刘伯承指挥……发起/开始”并点名战役的条目。
- 联名电报但未写指挥、仅共同署名或同页出现，不纳入本条最低覆盖。
- 这是代表性最低覆盖，不声称穷尽1949年前所有共同指挥战役；额外有效战役允许补充。
- OCR页，需人工核对原页图像。
- 2026-10-29 用户复核认为原答案不完整；按用户选择的改法重写事实、证据组和参考答案，待再次送审。

## 约束/路由/多轮

### 17. `dev_constraint_history_isolation`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`constraints_routing`；可答性：`answerable`；主题组：`huaihai_history_isolation`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：8 条（{'human_review': 8}）；固定池：8 个成员（basis=agent_review）
- 问题：详细介绍淮海战役。
- 参考答案：淮海战役以徐州为中心，战场东起海州、西至商丘、北起临城（今薛城）、南达淮河。参战解放军以华东、中原两支野战军及相关军区部队为主，共约60万人。粟裕提出举行战役的建议，中央军委接受建议，于10月11日明确第一阶段集中歼灭黄百韬兵团的方针。为统筹作战与地方支前，中央军委决定组成刘伯承、陈毅、邓小平、粟裕、谭震林五人总前委，邓小平任书记（《中国共产党历史》第一卷 PDF 963—965页）。第一阶段为11月6—22日，华东野战军在碾庄圩歼灭黄百韬兵团约10万人；第二阶段为11月23日至12月15日，中原野战军及华东野战军一部在双堆集歼灭黄维兵团约12万人；第三阶段为12月16日至1949年1月10日，1949年1月6日华东野战军发起对杜聿明部总攻，至10日歼灭邱清泉、李弥两个兵团约20万人，俘杜聿明，战役胜利结束（第965页）。全役历时66天，歼灭国民党军55.5万人，使长江以北华东、中原地区基本解放，使南京、上海直接受到解放军威胁，为渡江作战创造有利条件（第966页）。人民群众的支前对胜利具有重要作用，陈毅用人民群众用小车推出来的胜利概括其作用；该页三大战役的累计支前数字不能单算成淮海战役的统计（第969页）。这些是战役概述的最低覆盖，允许继续补充有可靠引用的内容。

**必要事实**

- `battle_geography`（必要）：淮海战役以徐州为中心，东起海州、西至商丘、北起临城、南达淮河。
  - 证据组：`battle_geography`
- `battle_forces`（必要）：参战解放军以华东、中原两支野战军及相关军区部队为主，共约60万人。
  - 证据组：`battle_forces_start` + `battle_forces_end`
- `battle_planning`（必要）：粟裕提出淮海战役建议，中央军委接受并于10月11日明确第一阶段集中歼灭黄百韬兵团的方针。
  - 证据组：`battle_planning`
- `battle_command`（必要）：总前委由刘伯承、陈毅、邓小平、粟裕、谭震林组成，邓小平任书记，统筹作战与支前。
  - 证据组：`battle_command`
- `battle_stage_one`（必要）：第一阶段为11月6日至22日，华东野战军在碾庄圩歼灭黄百韬兵团约10万人。
  - 证据组：`battle_stage_one`
- `battle_stage_two`（必要）：第二阶段为11月23日至12月15日，中原野战军及华东野战军一部在双堆集歼灭黄维兵团约12万人。
  - 证据组：`battle_stage_two`
- `battle_stage_three`（必要）：第三阶段为12月16日至1949年1月10日；1月6日总攻后歼灭邱清泉、李弥兵团、俘杜聿明，战役结束。
  - 证据组：`battle_stage_three_time` + `battle_stage_three_result`
- `battle_result`（必要）：战役历时66天，歼灭国民党军队55.5万人。
  - 证据组：`battle_result`
- `battle_impact`（必要）：胜利使长江以北华东、中原地区基本解放，使南京、上海直接受到威胁，为渡江作战创造条件。
  - 证据组：`battle_impact`
- `battle_civilian_support`（必要）：人民群众的支前对淮海战役胜利具有重要作用，陈毅用小车推出来的胜利概括这种支持。
  - 证据组：`battle_civilian_support`

**证据组与原文**

- `battle_geography`：淮海战役的战场范围
  - `cpc_history_volume_1` PDF 第 963 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：淮海战役是在以徐州为中心，东起海州、西至商丘、北起临城（今薛城）、南达淮河的广大地区进行的。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_forces_start`：参战力量跨页句的华东部分
  - `cpc_history_volume_1` PDF 第 963 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：参加这一战役的有华东、
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_forces_end`：参战力量跨页续句与总兵力
  - `cpc_history_volume_1` PDF 第 964 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：中原两支野战军和华东、中原两军区，以及晋冀鲁豫军区的部分部队共约60万人。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_planning`：最初作战建议与军委方针
  - `cpc_history_volume_1` PDF 第 964 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：华东野战军代司令员粟裕即向中央军委提出举行淮海战役的建议，主张进攻并歼灭淮阴、淮安和海州、连云港地区的国民党军队，为夺取徐州创造条件。中央军委接受这一建议，于10月11日发出《关于淮海战役的作战方针》的指示，指出战役第一阶段的重心是集中兵力歼灭国民党军刘峙集团右翼劲旅黄百韬兵团。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_command`：总前委及领导成员
  - `cpc_history_volume_1` PDF 第 965 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：为了统筹这一战役的作战和地方支前事宜，中央军委决定由刘伯承、陈毅、邓小平、粟裕、谭震林组成总前敌委员会，由刘伯承、陈毅、邓小平为常委，临机处置一切。邓小平为总前委书记。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_stage_one`：第一阶段的时间和主要作战结果
  - `cpc_history_volume_1` PDF 第 965 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：淮海战役于11月6日发起，至22日为战役的第一阶段。在这个阶段中，华东野战军在碾庄圩地区歼灭黄百韬兵团约10万人，击毙兵团司令官黄百韬。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_stage_two`：第二阶段的时间和主要作战结果
  - `cpc_history_volume_1` PDF 第 965 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：11月23日至12月15日，是淮海战役的第二阶段。在这个阶段中，中原野战军及华东野战军一部，在宿县西南的双堆集地区包围并歼灭自确山东援的黄维兵团约12万人，生俘兵团司令官黄维。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_stage_three_time`：第三阶段起止时间
  - `cpc_history_volume_1` PDF 第 965 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：12月16日至1949年1月10日，是淮海战役的第三阶段。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_stage_three_result`：第三阶段总攻和结束
  - `cpc_history_volume_1` PDF 第 965 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：1949年1月6日，华东野战军发起对杜聿明部的总攻，经四天激战，于10日全歼邱清泉、李弥两个兵团约20万人，俘杜聿明，击毙邱清泉，仅李弥等少数人逃脱。至此，淮海战役以大获全胜而结束。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_result`：战役历时和总战果
  - `cpc_history_volume_1` PDF 第 966 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：在战役中，人民解放军经过66天紧张艰苦的战斗，歼灭国民党军队55.5万人，其中包括国民党军队“五大主力”中的第五军和第十八军。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_impact`：战役战略影响
  - `cpc_history_volume_1` PDF 第 966 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：这一胜利，使长江以北的华东、中原地区基本上获得解放，使国民党反动统治的中心地带南京、上海直接暴露在人民解放军的铁拳面前，为解放军渡江作战创造了极为有利的条件。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.
- `battle_civilian_support`：群众支前的作用
  - `cpc_history_volume_1` PDF 第 969 页（SHA `717a24bcc6089f1cda30a6327f364dd450040e5120d9e25953a988a216758537`；文本层）
    - 原文：华东野战军司令员陈毅曾深情地说：“淮海战役的胜利，是人民群众用小车推出来的。”广大人民群众的支援，有力地保证了战略决战的胜利，充分显示了人民战争的巨大威力。
    - Agent校验：status=verified_against_page_text_and_pdf_image; verified_at=2026-10-05
    - 校验方法：Read complete extracted/OCR page, render with pdftoppm and inspect full page image; Agent source review, not human approval.

**禁止结论**

- 淮海战役主要由林彪和东北野战军指挥实施。（原因：华东、中原野战军和五人总前委有直接证据；不能将前轮主体或辽沈战役指挥关系移植到淮海。）
- 这里只介绍林彪在1930—1949年的职务，因本轮沿用上轮条件。（原因：本轮问题自包含且切换主题，不继承上轮人物/职务/时间过滤。）
- 880余万民工人次等第969页数字是淮海战役单独的支前统计。（原因：该页明确这些数字是三大战役累计，不能把总体统计错给单一战役。）
- 消灭55.5万人等于击毙55.5万人。（原因：原文用歼灭，不能缩窄为全部击毙。）

**复核提示**

- 此题必须按独立protocol运行有历史与无历史控制两臂；本case只承载共用的答案和证据标注。当前runner没有conversation_history接口，不能把单轮问答通过记作历史隔离通过。
- 前轮只有用户问题“林彪在1930—1949年相继担任哪些职务？”，不捏造助手历史回答。
- 10个必要事实是可复核的最低内容覆盖，不声称完整穷尽战役史。参考答案不是逐字匹配模板。
- 页963的华东与964的中原/数量属于同一句的AND证据；孤立964页不得独立声称完整支持双方参战部队。
- 战役发生在上轮时间区间内，因此仅凭答案年代无法检测时间条件泄漏；须检查plan/constraints trace是否继承1930—1949显式过滤，没有trace时该子项N/A。

### 18. `dev_constraint_month_place`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`constraints_routing`；可答性：`answerable`；主题组：`mao_zhou_cppcc_1949`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-11T17:17:35+08:00`
- 复核备注：认可四项最低覆盖、迁驻+后续复电作为地点组合证据、27/29日OR替代及月份/地点边界。
- 候选标签：9 条（{'human_review': 9}）；固定池：9 个成员（basis=agent_review）
- 问题：1949年3月毛泽东在北平有哪些活动？
- 参考答案：可核查的主要活动包括：3月25日到达北平清华园车站，转往颐和园；当日下午在西苑机场会见各界代表和民主人士、检阅部队，随后进驻香山双清别墅。在北平继续指挥军事工作，3月27日、29日批复同意4月15日发动渡江战斗。3月31日在香山与其他中央领导人接见并宴请第四野战军师以上干部。这是主要活动最低覆盖，不是该月逐日穷尽清单。

**必要事实**

- `mao_arrival`（必要）：3月25日凌晨到达北平清华园车站，转至颐和园，随后进驻香山双清别墅。
  - 证据组：`mao_arrive_beiping_march25`
- `mao_xiyuan`（必要）：3月25日下午在西苑机场会见各界代表及民主人士，并检阅部队。
  - 证据组：`mao_xiyuan_march25`
- `mao_command`（必要）：在北平期间继续指挥军事工作，3月27日/29日为中央军委起草复电，同意推迟到4月15日发动渡江战斗。
  - 证据组：`mao_arrive_beiping_march25` + `mao_yangtze_command_late_march`
- `mao_cadres`（必要）：3月31日与其他中央领导人在香山接见并宴请第四野战军师以上干部。
  - 证据组：`mao_xiangshan_march31`

**证据组与原文**

- `mao_arrive_beiping_march25`：3月25日抵清华园、去颐和园，后进驻香山。
  - `mao_zedong_chronology_volume_3` PDF 第 475 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：二十四日深夜在涿县换乘火车，二十五日凌晨到达北平清华园车站，改乘汽车至颐和园。下午五时，同刘少奇、朱德、周恩来、任弼时、林伯渠等在北平西苑机场同前来欢迎的各界代表及民主人士一千多人见面，并乘车检阅部队，随后进驻香山双清别墅。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `mao_xiyuan_march25`：3月25日在西苑机场会见欢迎者并检阅部队。
  - `mao_zedong_chronology_volume_3` PDF 第 475 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：下午五时，同刘少奇、朱德、周恩来、任弼时、林伯渠等在北平西苑机场同前来欢迎的各界代表及民主人士一千多人见面，并乘车检阅部队，随后进驻香山双清别墅。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `mao_yangtze_command_late_march`：入北平后3月27/29日批复渡江战斗拟于4月15日发动；同一决定的复电可替代。
  - `mao_zedong_chronology_volume_3` PDF 第 477 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：3月29日为中共中央军委起草致刘伯承、陈毅、邓小平，饶漱石，粟裕、谭震林电：同意你们推迟至四月十五日渡江。已定四月一日为我们和国民党开始谈判时间，四月十日左右结束，谈判成败要到那时才能清楚。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
  - `mao_zedong_chronology_volume_3` PDF 第 476 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：3月27日为中共中央军委起草复刘伯承、陈毅、邓小平、粟裕、谭震林电：＂宥申电(1)悉。同意你们十五日发起渡江战斗及对北岸敌人的处置。”
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review
- `mao_xiangshan_march31`：3月31日在香山接见并宴请第四野战军师以上干部。
  - `mao_zedong_chronology_volume_3` PDF 第 477 页（SHA `f0c76c272810d80a1ea93070b4393d276933bc07a63bb54ae815590b803a4468`；文本层）
    - 原文：3月31日和刘少奇、朱德、周恩来、任弼时、林伯渠、董必武等在香山接见并宴请第四野战军师以上干部。
    - Agent校验：reviewer=agent:eval_sources_exact; verified_at=2026-09-23T06:46:52.034231+00:00; pdf_visual_checked=True; human_approval=False
    - 校验方法：effective_page_text_quote_check_and_pdf_visual_review

**禁止结论**

- 毛泽东1949年3月23日已经在北平。（原因：23日离西柏坡、25日才到北平。）
- 3月24日在北平亲自参加妇女代表大会。（原因：毛年谱PDF476只载题词，且当时在保定，不支持现场参加。）
- 1949年3月在北平召开第一届全国政协会议或宣布新中国成立。（原因：分别是同年9月和10月，月份限制不符。）
- 1949年3月在北平主持七届二中全会。（原因：七届二中全会地点不在北平，不能把全年活动代替限定地点活动。）

**复核提示**

- 2026-10-11用户认可四项最低覆盖、3月/北平硬约束、迁驻与复电的组合地点证据，以及27日或29日的OR替代；本题定义获人工批准，候选分级和答案评审未获本批批准。
- 最低覆盖4组；其他3月25日以后且有可靠北平地点证据的真实活动可接受，不要求穷尽所有书信、电报。
- 3月27/29日军委复电的北平地点由PDF475迁驻时序结合后续年谱条目支持；单独复电片段未直写地点，因此必要事实引用需同时给迁驻证据，不能把收电人所在地当毛泽东所在地。
- 3月27和29日是对4月15日发动渡江战斗同一决定的复电，可作为该事实的OR替代；不能把一般军事活动都当该证据组命中。
- 月份/地点硬负例即使与同一人物相关，也按当前问题相关性0，不把时间相邻当事实支持。

## 拒答/材料不足

### 19. `dev_refusal_einstein`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`refusal_boundary`；可答性：`unanswerable`；主题组：`einstein_false_premise`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：0；固定池：无
- 问题：爱因斯坦在1925年担任了什么党内职务？
- 参考答案：当前本地文献没有可核实的证据支持爱因斯坦在1925年担任某项党内职务，因此我不能据此给出职务。题目也没有说明所指党派；如要继续查证，需要明确党派并提供相应史料。资料不足不等于已证明他在历史上从未参加任何党派或担任任何职务。

**拒答依据**

- 类型：`unsupported_premise_in_current_corpus`
- `requested_year`：1925
- `requested_entity`：爱因斯坦
- `unspecified_constraint`：题目未说明党派；不能擅自替换为中国共产党或其他特定组织。
- `meta_evidence_role`：支持资料边界和已查候选不匹配的解释，不作为可答历史事实的Recall分母。
- 项目依据：`REQUIREMENTS.md`（SHA `2b6fe88b1ef7fcf66fcc8797c2aaa0c054fa7f5c965f6053a97a03f1b20cde60`）
  - 规则：系统能够明确拒绝回答本地资料无法支持的问题
  - 规则：提示词和后置校验禁止模型把无来源常识写成核心事实
  - 规则：证据不足时返回 `insufficient_evidence`，不强行生成结论
- 本地检索审计：17 份文献，记录实际 PDF/页面/OCR 缓存哈希；详见 JSON。
- 元证据：`zhou_enlai_chronology_1949_1976` PDF 第 653 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
  - 原文：△接受西方记者的采访，谈对本月十八日逝世的物理学家阿尔伯特·爱因斯坦的评价：我对爱因斯坦的逝世极为悲痛。在他的一生中，他曾致力于把科学用于和平的事业。他一直是反法西斯的，是一位拥护和平的科学家，我代表中国人民表示哀悼。
  - Agent校验：status=source_text_and_pdf_image_verified; reviewer=Codex source review; human approval pending; verified_at=2026-10-05T14:30:38.722457+08:00
- 元证据：`zhou_enlai_chronology_1949_1976` PDF 第 1006 页（SHA `c8490c24ef0fab0449bec7aa797d0a270bee419b96ae2d248accda143a571ec1`；文本层）
  - 原文：△在机场等候阿里·萨布里时，同阿驻华大使伊马姆谈话，对大使关于以色列人很危险的看法，说：对人民不能这样说，人民总是好的。在他们的知识界里，还出现了一些伟大人物，例如马克思、爱因斯坦。这个民族的一部分受到外来的压迫，而另一部分又在压迫别人。
  - Agent校验：status=source_text_and_pdf_image_verified; reviewer=Codex source review; human approval pending; verified_at=2026-10-05T14:30:38.722457+08:00

**禁止结论**

- 编造爱因斯坦在1925年担任某党书记、委员或其他党内职务。（原因：当前本地证据不支持这一任职前提，不能接受前提后补造答案。）
- 爱因斯坦从未加入过任何党派，或1925年在任何组织都不可能有职务。（原因：本例只确认当前库不能支持所问职务，没有建立跨所有组织的历史否定证据。）
- 引用1955年的悼念评价或1963年的知识界举例作为1925年党内职务证据。（原因：两处本地命中均非1925年任职材料，属于姓名相关而命题不支持。）
- 因为1925年超出项目1921—1978范围而拒答。（原因：1925在项目时间范围内；拒答应依据缺乏可核实任职证据及党派未明确。）

**复核提示**

- 题库沿用原题；将‘错误前提’保守操作化为‘当前资料无法支持所问任职’，没有使用无来源常识断言其从未加入任何党派。
- 已实际校验17份PDF哈希，检索15112条effective page记录，并查看两个姓名命中原页；无需用这两页充当正向事实金标。
- 人工需裁定安全拒答+党派澄清的可接受表述。只要求澄清而不说明证据不足，不能直接视为完整通过。

### 20. `pilot_refusal_out_of_scope_2024`

- 文件：`golden_dataset.json`
- 分层：`development`；类别：`refusal_boundary`；可答性：`unanswerable`；主题组：`out_of_scope_2024`
- 人工复核：`approved`；reviewer=`user_in_current_chat`；time=`2026-10-29T19:18:23+08:00`
- 复核备注：用户在 2026-10-29 题目定义复核中批准该题的问题、必要事实、证据锚点与回答边界，未提出修改。
- 候选标签：0；固定池：无
- 问题：习近平在2024年考察了哪些地方？
- 参考答案：这个问题超出本项目1921—1978年的研究范围，当前资料库不能据此列出2024年的考察行程。

**拒答依据**

- 类型：`out_of_scope`
- `requested_year`：2024

**禁止结论**

- 给出具体2024年行程并配本地历史资料引用（原因：超出研究范围且历史资料不能支持当前行程。）

**复核提示**

- 依据项目研究范围作范围拒答；不是断言历史上没有这些活动，也不需要在本地史料中证明否定。
- 检索Recall/Precision/MRR/nDCG不适用；评估路由、范围说明、是否捏造行程以及是否滥用历史引用。

