# 13题开发集与实际检索对照（2026-09-23）

本文是保留的13题历史执行基线。2026-10-05已补齐20题开发预标注及分批复核准备，见 [DEVELOPMENT_ANNOTATION_PROGRESS.md](DEVELOPMENT_ANNOTATION_PROGRESS.md)；新增7题没有新采集成绩，不能混入本文分母。

本轮已完成开发集扩充、固定池nDCG、显式最终答案评分，以及13题的两次真实本地检索运行。**人工批准仍为0；新增七题尚未执行真实LLM问答，30题Golden没有完成。** 本轮没有修改生产Top-K、embedding、重排或回答策略。

## 当前资产

| 项目 | 当前状态 |
| --- | --- |
| 设计清单 | 30题：20开发、10保留；10道保留题仍禁止运行和调参 |
| 可执行开发集 | 13题：12可答、1拒答；原六题定义保留，新增七题 |
| 标注 | 43个必要事实、43个证据组、196条候选判断；全部Agent暂定 |
| 冻结排序池 | 12个池，按题累计124个候选单位，跨题去重120段原文 |
| 人工批准 | 0题；所有正式指标不可评，不填0分 |
| 本轮采集 | 13题×Top-5/Top-20，两次均无外部LLM请求，无检索分支降级 |
| 真实模型答案 | 仍为此前获授权的六题；本轮重算其显式评审，没有重新调用模型 |

主数据为 [development_v2.json](development_v2.json)，最新池为 [ranking_pools_v2.json](ranking_pools_v2.json)，机器可核对汇总为 [development_summary.json](development_summary.json)。原六题 `pilot_annotations.json`、原v1十二题和历史报告保留。

新增问题覆盖周恩来1954年职务、邓小平1954年任职、毛泽东调查研究观点、《矛盾论》主要矛盾、一大问题的语义改写、1949年3月北平活动、周恩来1954—1956年主要经历。周恩来1954题在复核中补齐政务院到国务院、政协副主席到主席的年内变化，以及书记处书记，避免用年末职务代表全年。

新增源页由Agent核对文本、PDF图像和当前PDF实际SHA；这不构成人工审批。开放题的必要事实是明确列出的最低覆盖框架，不能称为穷尽全部历史观点或经历。

## 实际Top-K对照

两次独立重新采集，组件 `candidate_k=30`，仅 `top_k=5→20`；生产回答参数 `answer_top_k=10` 固定。源代码SHA、题集、语料、索引以及关键词/向量分支的有序候选一致。比较器确认本次组件Top-K对照可归因；并非截取同次结果假冒两次运行。

以下均为12道可答题的Agent暂定分数，拒答不进入分母：

| 指标 | Top-5运行 | Top-20运行 | 含义 |
| --- | ---: | ---: | --- |
| 最终返回列表的必要证据组Recall，按题宏平均 | 58.13% | 71.83% | +13.69个百分点 |
| 汇总已覆盖证据组/全部必要组，微平均 | 20/43（46.51%） | 26/43（60.47%） | 补回6个已标定证据组 |
| Precision@5 | 0.7000 | 0.7000 | 前五位相关比例未变 |
| MRR@5 | 0.9167 | 0.9167 | 首个相关候选位置未改善 |
| 固定池nDCG@5 | 0.7315 | 0.7315 | 前五位分级排序质量未改善 |

这证明扩大K补回部分已标定证据，**不能证明答案质量改善，也不能据此直接把生产默认K改成20**。本轮原始问题组件与生产问答是两条独立测量路径；离线摘录答案没有最终语义评审，答案指标为N/A。

Top-20运行的最终列表逐题结果：

| 题目 | 组Recall@5 | 组Recall@20 | P@5 | MRR@5 | 池nDCG@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 邓小平1952任命 | 1.000 | 1.000 | .600 | 1.000 | .633 |
| 邓小平1962农业观点 | .667 | .667 | .800 | 1.000 | .922 |
| 遵义军事领导三阶段 | .750 | 1.000 | .800 | 1.000 | .604 |
| 1949政协主席/副主席 | .500 | 1.000 | 1.000 | 1.000 | .636 |
| 限定下卷的1973年3月决定 | 1.000 | 1.000 | .600 | 1.000 | .868 |
| 周恩来1954主要职务 | .500 | .500 | 1.000 | 1.000 | .921 |
| 邓小平1954任职 | 1.000 | 1.000 | .600 | 1.000 | .563 |
| 毛泽东1949年3月北平活动 | .250 | .750 | .200 | 1.000 | 1.000 |
| 周恩来1954—1956经历 | .143 | .286 | 1.000 | 1.000 | .851 |
| 调查研究观点 | .500 | .750 | 1.000 | 1.000 | .857 |
| 《矛盾论》主要矛盾 | .667 | .667 | .800 | 1.000 | .922 |
| 党的头一次全国大会 | .000 | .000 | .000 | .000 | .000 |
| 2024范围拒答 | N/A | N/A | N/A | N/A | N/A |

三类失败可以据此区分：

- **一大题**：关键词30候选中覆盖2/5组，向量30候选0/5；融合到去重后仍有2/5，最终Top-20为0/5。已有部分相关候选排得太后，同时语义召回有缺口；不宜把全部责任归给embedding。记录为 [BC-029](../../badCase.md)。
- **跨年经历题**：两分支并集只有2/7组，Top-20仍为2/7。仅扩最终K无法补足尚未召回的主题。
- **月份地点题**：前5仅一条相关材料，池nDCG却为1，因为小池中唯一已标正例居首；必要组Recall仅1/4。nDCG和MRR高不能替代多证据Recall。

较大K仍有标注缺口。Top-20报告中P@10和池nDCG@10仅3题可评，P@20和池nDCG@20为0题可评；MRR@20=1仅覆盖11题，一大题因未知候选排在首个已知相关项之前而不可评。**不能把不同有效题集的均值变化当作提升。** 比较器拒绝分母不一致的差值，完整报告保存逐题N/A原因。

## 固定池和最终答案评分口径

初始池v1是关键词/向量/最终排序各前5并集，一大题另加入3个独立核对的真实正例，仅进入评价池，未插入检索结果。独立Top-5运行在1973题返回了一条池外1933年上卷材料，评分器因此正确拒绝该题nDCG。该候选在原标签里已经核对为0；v2将其纳入冻结池，未新造标签，并用同一v2重算两端。v1文件保留审计。

nDCG采用 `gain=2^rel−1`、`discount=log2(rank+1)`，以整个固定池的唯一候选形成理想排序；重复候选只首次计增益，短返回不缩小理想分母。全池缺标签、池外返回、身份过期、零正例理想池均N/A。每项携带池成员、等级和公式指纹，比较时必须一致。**固定小池不是全语料相关证据全集**；新模型或更大K产生新候选，须扩充盲审池，再用同一新版本重算所有配置。

[answer_reviews_v1.json](answer_reviews_v1.json) 将上一轮六题真实答案的逐事实评审规范化。它绑定完整capture、题目定义以及答案和引用的SHA；事实ID和实际引用ID必须匹配。摘录必须是实际回答的原文，不能用后处理拼接句假装逐字引用。

最终答案评分汇总明确标签，不自动判断语义：必要事实covered计完整，partial不折算半分，unknown保持不可评；引用支持、来源/时间限制、路由、安全拒答、范围解释分别评分。整体有确定失败即未通过；无失败但有未知适用维度时为N/A。路由仅两题有明确失败标签，不能把0/2当作全系统路由准确率。

| 六题真实答案重算 | Agent暂定结果 |
| --- | --- |
| 必要事实完整覆盖 | 7/12；另2个部分覆盖、3个缺失 |
| 引用支持 | 3/5；摘录有出处和回答切题分别判断 |
| 明确时间约束 | 2/4；遵义来源日期冲突未知，不纳入此分母 |
| 整体通过 | 2/6：1952任命、政协职务区分 |
| 安全拒答 | 1/1；范围解释0/1 |
| 人工正式评分 | 全部N/A |

真实历史回答、出处审计及故障分析仍见 [LIVE_EVALUATION.md](LIVE_EVALUATION.md)。本轮没有重新生成这些答案。录制器新增未来HTTP成功响应的实际content和允许的usage字段，可用于区分原始Planner输出与规则后处理；不保存隐藏推理或请求凭证，错误响应体不落盘。新响应录制通过模拟HTTP测试，本轮没有新增真实调用，不能补回历史遗漏的原始响应。

## 复核与接下来的一步

本地盲审包为 `data/reports/eval_expansion_20260923/review/review.html`，含13题和按题累计805个实际候选，隐藏分支、排名及Agent标签。完整包不同于124成员的固定小池；独立源文正例还可在排序池文件中核对。HTML未做浏览器视觉验收，行为由既有前端测试验证；最终答案评审是独立JSON，不宣称该候选界面已支持答案打分。

人工优先确认：开放式调查研究/跨年经历的必要事实边界、周恩来全年职务沿革、月份地点的跨页推断、遵义“三月中旬/下旬”来源冲突，以及0/1/2相关程度。Agent已做原文定位和预标注，人工应作裁定与批准，不必从零寻找全部出处。

2026-09-23，用户认可全部30道题的选题，并明确要求：**进行评测集设计时不要修改Agent**。此确认针对题目设计，不等于已复核并批准原文、事实答案和相关性标签。当前仅完善题集、标注、评测脚本及报告；Agent的规划、检索、重排、上下文、生成逻辑和生产配置保持固定。发现的问题记录为待修复事项，撤销此前“先修1973题Agent问题”的推进安排。

当前阶段是“选题完成、评测方法已跑通、金标内容制作中”。下一步按以下顺序推进：

1. 补齐剩余17题的原文证据、必要事实、拒答边界及逐阶段判据：先7道开发题，再独立核验10道保留题。
2. 为代表题补齐Top-10/20候选分级，扩大可计算Precision/nDCG的范围；补充多轮输入、查询理解/路由、上下文与答案的评测侧支持。现有采集器仅支持development，尚需受控的保留集验收入口，不能直接解除保留题隔离。
3. 分批提交人工复核，裁定开放题范围、来源冲突和候选等级，并审计开发/保留集共享证据，冻结30题及标注版本。
4. 用固定Agent完成开发基线和保留集独立验收，保存逐题、逐阶段质量及耗时/Token；保留集不循环用于调参。真实模型采集与本地检索运行分别报告。

达到目标的标准：30题均有可追溯、经人工复核的标注；整集能实际计算Recall、Precision、MRR等指标，并在约定的多个K上有代表性可评用例；最终答案与执行阶段都能评估；开发/保留隔离、版本指纹和可复现基线齐全。不是要求每题覆盖每项指标。embedding/rerank改动及Agent缺陷修复留到评测集冻结后的独立任务；当前比较器尚不能自动证明这些改动的单变量隔离。

工作量粗估（尚未测得剩余17题的实际标注速率）：原文与预标约8–16小时，扩池、阶段判据和隔离审计约6–12小时，全量基线、答案预审和报告约4–8小时；合计约18–36小时制作与验证工作。人工复核另约8–16小时，可分批交错进行。按每天8小时且复核及时衔接，保守估计约4–7个工作日达到正式Golden；重大来源争议或人工反馈等待会延长日历时间。13/30表示预标题数，不能当作整体Golden完成百分比。

## 复现与校验

```powershell
# 两次独立本地采集；默认不调用LLM。
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot collect --dataset evals/golden/development_v2.json --candidate-k 30 --top-k 5 --answer-top-k 10 --run-name development_13_top5 --output data/reports/eval_expansion_20260923/top5_capture.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot collect --dataset evals/golden/development_v2.json --candidate-k 30 --top-k 20 --answer-top-k 10 --run-name development_13_top20 --output data/reports/eval_expansion_20260923/top20_capture.json
# 分别评分，再比较。
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset evals/golden/development_v2.json --capture data/reports/eval_expansion_20260923/top5_capture.json --ranking-pools evals/golden/ranking_pools_v2.json --output data/reports/eval_expansion_20260923/top5_report.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset evals/golden/development_v2.json --capture data/reports/eval_expansion_20260923/top20_capture.json --ranking-pools evals/golden/ranking_pools_v2.json --output data/reports/eval_expansion_20260923/top20_report.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot compare data/reports/eval_expansion_20260923/top5_report.json data/reports/eval_expansion_20260923/top20_report.json --output data/reports/eval_expansion_20260923/topk_comparison.json
# 对匹配的历史六题真实capture评分；不重新调用模型。
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset data/reports/eval_pilot_v2/live_annotations.json --capture data/reports/eval_pilot_v2/live_capture.json --ranking-pools evals/golden/ranking_pools_v2.json --assessments evals/golden/answer_reviews_v1.json --output data/reports/eval_expansion_20260923/live_rescored_v2.json
```

评测器代码提交 `87acede`，基础数据提交 `908923a`。两次新capture的应用源码SHA为 `504e358698e63e73f38ca6e831a9c70160e3c931fdb7b78a2169eba60c37d8a4`，分片SHA为 `707b1a75b6df82e7cf9fcab9ade1d9b071abbf4b7bea78ee4644e8282acd30e6`。采集记录的Git dirty为true（文档待提交和原有未跟踪tmp），未伪称干净工作树；两端实际应用源码SHA一致。完整文件及规范化JSON校验和见汇总。

`scripts/check.ps1`：Ruff、mypy、576项Python测试和3项前端测试全部通过。另验证当前PDF哈希、全部原文锚点、池身份/封印、30题设计对应关系、保留题隔离及人工门禁。Top-5/20组件检索累计分别23.91/25.37秒，本地问答累计23.41/24.58秒；均是单次运行记录，不用来推断延迟分布或线上成本。
