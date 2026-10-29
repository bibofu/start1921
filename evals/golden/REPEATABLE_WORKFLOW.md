# 开发集可重复评测流程

2026-10-29 v6 更新：当前题目定义版本为 `development_annotations_v6.json`，必须配套显式指定 `development_protocols_v6.json`；前两批8题已批准、其余12题待审，详见 [第二批裁定记录](human_adjudications_v5.json)，其中继承了第一批v4裁定。v6 只重绑两道拒答题引用的 `REQUIREMENTS.md` 当前字节哈希，已通过 `validate_anchors` 并完成一次20题本地组件采集；详见 [v6迁移记录](MIGRATION_V6.md) 和 [v6本地基线](observations/20261029_v6_local/README.md)。任何新采集应使用新输出目录，并在全部采集/复核/评分步骤使用同一版本的标注和协议。不得将旧capture或答案评审改哈希绑定到 v6，也不因题目批准而自动批准候选或答案。

v3/v4/v5 仍绑定旧版 `REQUIREMENTS.md` 字节哈希，全量新采集会报 `project refusal basis changed`；这些版本只作为历史冻结资产保留，旧capture仍可按其绑定版本离线复核和评分。下面的 v3 命令与 `stable/` 路径是历史复现示例，不是当前入口。

本流程使用 `history_agent.evaluation.pilot`（`reviewable-pilot-v5` 运行器），仅涉及评测工具。v6 的20题按21个输入采集：淮海题的带历史主臂和无历史控制臂分开执行，仍只占1个独立题。所有默认标签和已有答案评审仍为 Agent 暂定判断，正式 Golden 成绩需独立满足人工批准门槛。

原 schema v2 标注包及其 `execution_status=annotation_only`、协议中的制作期状态保持原样，作为2026-10-05冻结资产。新评测入口校验整包、协议、逐题定义和输入绑定后执行；不会改低 schema、忽略历史或回写人工批准。当前新增接入不包含20题真实模型回答或新增7题的候选相关性标注。

## 1. 冻结输入并采集

每次实验选择新的目录，保存所用数据集、候选相关性标注、固定排序池和适用协议。固定题目、标注口径、模型及非实验参数；开发集用于调参，保留题用于独立验收。新候选没有标签时，Precision/MRR/nDCG 可能不可评，不得直接判为不相关。

```powershell
# 示例：新的本地检索采集，不调用模型。已有输出或 partial 输出会拒绝覆盖。
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot collect `
  --dataset evals/golden/development_annotations_v6.json `
  --protocols evals/golden/development_protocols_v6.json `
  --candidate-k 30 --top-k 20 --answer-top-k 10 `
  --run-name development20_v6_local_20261029 `
  --output data/reports/eval_development20_v6_20261029/capture.json
```

需要真实问答时显式加 `--with-llm`，会发送问题、史料与中间答案并产生服务用量。上述命令不带该参数，执行本地组件检索及无模型的摘录回答路径；已记录的检索阶段可以评分，但模型 Planner、生成上下文和真实模型成本保持 N/A，摘录答案仍须独立复核。不会为了补全报告自动调用模型。此前13题的外发范围不代表新增7题已经做过真实模型评测。

`capture.json` 记录应用源码指纹、Git 状态、PDF 文件身份、索引 manifest 与实际 artifact 校验、模型/提示词/参数和已执行阶段的轨迹。schema v2 另绑定原标注包、协议文件字节和规范化内容、每臂的原始 `question + history` 及其指纹。`cases` 保存20个主输入，`control_cases` 保存淮海无历史控制输入；输入缺失、重复、被替换或历史被删除均不能通过完整采集校验。

淮海主臂只传协议中已有的一条用户历史，不补造上一轮 Assistant 回答。两臂使用同一配置，组件检索仍以当前原问题为输入，不读取历史；因此相同组件结果不能证明历史隔离通过。隔离检查需要真实两臂的执行计划、约束、检索轨迹和回答。`source_scope` 标注也不会被评测器注入为 Agent 的额外检索过滤条件。

保留 capture 原件；评分不重新读取当前索引，不会重新调用 Agent。采集失败时 `.partial.json` 保留已完成的主输入及控制输入，但不是完整集报告，须使用新目录重新采集。

采集前后分别核对源码指纹；运行期间源码变化会令归因检查失败，应在代码固定后重新采集。修改评测工具期间产生的试跑与稳定版本的正式对照应使用不同目录。

## 2. 为本次 capture 生成复核包

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot prepare-reviews `
  --dataset evals/golden/development_annotations_v6.json `
  --capture data/reports/eval_development20_v6_20261029/capture.json `
  --protocols evals/golden/development_protocols_v6.json `
  --output-dir data/reports/eval_development20_v6_20261029/reviews
```

生成以下文件。复核目录必须不存在，以免覆盖正在进行的审查。

| 位置 | 内容 |
| --- | --- |
| `reviews/review_packet.json` | 20题的题目、证据、必要事实、本次答案及轨迹入口 |
| `reviews/answer_reviews.json`、`process_reviews.json` | 主输入的答案与过程复核；未生成答案时不虚构答案记录 |
| `reviews/controls/without_history_control/` | 淮海控制臂的独立答案、过程复核包 |
| `reviews/specialist_reviews.json` | 专门协议的逐项检查及淮海双臂隔离检查 |
| `reviews/index.html` | 离线答案复核工作台，逐题对照正文、交付引用、必要事实及过程 |
| `reviews/calibration.json` | 版本化开放题口径、原事实与证据追溯、边界示例 |
| `reviews/review_bundle.json` | 初始全量待审包；工作台导出的判断保留同一绑定 |

- 答案复核：逐事实覆盖和引用支持、来源/时间约束、路由、拒答、范围说明。引用中有事实而正文未回答，不能算正文完整覆盖。
- 过程复核：依协议检查实际执行计划与查询变体是否保留实体、意图和约束；原始 Planner 输出和实际执行计划分别留证。20题 schema v2 必须显式提供同一 `--protocols`；旧 schema v1 可省略并使用通用判据。
- 专门复核：淮海隔离有4项明确检查，不能仅从战役年份落在1930—1949期间推断没有旧时间过滤。湖南题按1921—1926六年分别报告，逐年事实/证据分母为2、2、2、1、5、2，同时保留14项事实微平均与6年宏平均，不能用1925年多项命中掩盖漏年。
- 所有模板初始 `unknown`，不自动打分或批准。明确判断须填写依据、复核人、带时区时间和理由。可先评分未审模板，结果按实际缺口显示 N/A。
- 复核绑定整份 capture、题目定义，以及答案/引用或执行计划快照。换一次 capture 就必须生成并审阅新包，不能修改哈希来复用旧判断。

### 在工作台填写与导入

打开 `index.html`，用题目搜索和“只看仍有待审项”定位。答案、交付引文与必要事实对照展示，允许选取回答原文后填入事实摘录。主输入与控制臂分开保存；过程、原始计划、生产证据和专项检查可按需展开。页面无外部依赖、不发送数据，不会调用模型。

可随时保存或导出草稿，继续时只接受同一 capture、校准版本和模板的草稿。复核依据默认未选择，不把填写姓名自动当成人工批准。完整覆盖、部分覆盖或存在矛盾须填写正文摘录；引用支持须选实际交付的引用编号。未审保持 `unknown`，不适用要解释，题目明确要求的维度不能用 N/A 跳过。开放题的具体口径见 [ANSWER_REVIEW_CALIBRATION.md](ANSWER_REVIEW_CALIBRATION.md)。

点击“导出复核包”后，把导出的 JSON 路径传给导入命令；输出目录必须是新目录。例如将下载文件放到本次运行目录并命名为 `review-bundle.json` 后：

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot import-reviews `
  --dataset evals/golden/development_annotations_v6.json `
  --capture data/reports/eval_development20_v6_20261029/capture.json `
  --protocols evals/golden/development_protocols_v6.json `
  --bundle data/reports/eval_development20_v6_20261029/review-bundle.json `
  --output-dir data/reports/eval_development20_v6_20261029/reviewed
```

导入端从命令行指定的原件重建模板，不读取导出包自带的路径。主输入、控制臂、事实、观察快照、分母和全部版本绑定通过检查后，才写入新目录并保存导入凭据；允许只完成部分判断，其余待审项仍须保留。不会覆盖原复核包或修改整题人工批准。之后评分将 `--reviews-dir` 指向新 `reviewed` 目录；未开始复核时可直接使用下面的初始 `reviews` 示例。

## 3. 离线生成统一报告

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/development_annotations_v6.json `
  --capture data/reports/eval_development20_v6_20261029/capture.json `
  --ranking-pools evals/golden/ranking_pools_v2.json `
  --reviews-dir data/reports/eval_development20_v6_20261029/reviews `
  --protocols evals/golden/development_protocols_v6.json `
  --k-values 1 3 5 10 20 `
  --output data/reports/eval_development20_v6_20261029/report.json
```

每次自动输出三份文件：

| 文件 | 用途 |
| --- | --- |
| `report.json` | 完整逐题、逐阶段、逐 K 指标及诊断，供比较器使用 |
| `report.summary.json` | 保留身份、聚合、过程、成本、逐题结论；省略大量重复候选诊断 |
| `report.md` | 便于查看的多 K 检索、答案、过程、成本与缺失原因摘要 |

暂定与人工批准结果分别保存。未提供答案/过程复核时，相应维度为 N/A。未映射的摘要上下文、缺失生产检索轨迹、缺失 usage 均不计零；成本同时报告完整总量和已知子集。HTTP 统计包含重试和失败；请求耗时之和可能有并发，不能冒充逐题 wall-clock 延时。

`--reviews-dir` 一次装入主输入、控制臂和专门复核文件，不能与 `--assessments`、`--process-reviews` 等单独复核路径同时使用。原有单独路径参数继续供旧13题回放使用。

20题报告的主 `cases` 和常规质量聚合只计20个独立题；`control_reports.without_history_control` 单列控制臂，`execution_accounting` 统计全部21次执行的耗时、调用与成本，避免漏记控制臂或把它作为第21题抬高质量分母。`specialist_assessment` 保存淮海配对诊断和湖南逐年结果。湖南年份证据命中、年份事实完整、每年事实Recall是不同指标；没有真实答案或明确复核时不会产生答案完整率。拒答元证据仅支持资料边界说明，不进入正向事实、Recall或排名分母。

新增7题尚无候选相关性分级及固定池；其必要证据Recall可算，Precision/MRR/nDCG按实际标签与池状态保留 N/A。其余题的新候选若超出现有标注，也遵守同一未知规则。

生产路径的多变体、多轮候选并集只计算关键证据覆盖，不能拼成 Precision/MRR/nDCG 排名。严格锚点和 span 身份会受到裁剪影响，因此阶段 Recall 下降不一定全部是语义丢失。最后一次摘要综合若不能还原原页，保持 N/A，同时报告可评子集及分母。

## 4. 用同版本评分器比较实验

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot compare `
  data/reports/control_a/report.json data/reports/control_b/report.json `
  --output data/reports/control_b/comparison.json
```

使用完整 `report.json`；摘要文件缺少完整阶段身份，不能作为归因材料。版本不同的旧报告，应先用同一评分器、同口径标签和各自绑定的复核重新离线评分，然后比较。

比较器区分三件事：

1. `compatible`：评分器版本、数据集、语料、K 集合和题目集合是否一致；协议采集还要求输入协议及主/控制臂身份一致，不能把不同历史条件当同一次实验。
2. `metrics` / `answer_metrics`：组件检索和答案指标的有效题目、事实分母、复核依据、nDCG 固定池是否一致，可比时才给 delta。查询理解、生产并集和成本在统一报告中按各自分母查看，当前比较器没有自动生成这些维度的 delta。
3. `attribution_safe`：除了配置只改变组件 `top_k`（或重复对照），还要求源码相同、逐题活跃分支相同、有序候选相同、实际使用的索引身份完整且跨运行一致。逐项核对 embedding、切分参数及版本、chunk/index artifact、build ID 和构建 commit。双方都说“校验成功”并不能证明双方使用同一份索引。

答案报告另记录 `answer_calibration_sha256`。两边校准包不同或只有一边使用新口径时，只禁止答案指标差值，不影响原本可比的检索指标；原因在 `answer_calibration_comparison` 中。旧13题未绑定新口径的直接评分入口继续保留，不批量改旧判断或分数。把旧答案放入新工作台时会生成空白复核，须按新口径重新判断。

索引身份缺失或变化时，仍可展示同口径指标差值，但归因为不安全；原因和差异见 `index_identity_comparison`。未参与的降级分支不冒充本次配置。当前支持的归因范围为 **component_retrieval**：组件 `top_k` 不控制实际生产问答的候选预算，不能据此解释答案波动。现有 `source_sha256` 也包含评测代码，评测代码变化会保守地阻止源码一致性归因。

## 2026-10-11 接入验证

上述 `stable/` 目录已实际完成本地采集、复核包生成、评分和同报告比较。20个主输入、1个控制输入均完成，采集前后及评分时源码指纹一致，索引身份校验通过，无检索降级。组件最终阶段关键证据 Recall@20 为60.88%（17道可答题宏平均），Precision@5 为70.00%（12道已有候选标注题）；未标候选不计作不相关。没有外部模型请求，答案及专项检查仍待复核，不能据此报告20题真实问答通过率。

评测相关测试共407项通过；最终控制臂复核包定位和源码变化检查另经14项定向回归通过，Ruff与8个相关源码文件的mypy检查通过。旧13题离线重算的检索与答案四组聚合结果与原报告完全一致。此轮只接入评测流程，未改Agent、冻结标注或人工批准状态。

## 2026-10-29 v6 接入验证

v6 只重绑两道拒答题的 `REQUIREMENTS.md` 哈希，`load_inputs` 与 `validate_anchors` 均通过；20个主输入、1个控制输入完成本地采集，采集前后源码指纹一致，无检索降级。组件最终阶段关键证据 Recall@20 为60.88%（17道可答题宏平均），正式口径 Recall@20 为60.9%（8道已批准题），Precision@5 为70.00%（12道已有候选标注题），MRR@5 0.9167、固定池 nDCG@5 0.7315；K=10/20 的 Precision/nDCG 仍因候选标注不足保持 N/A。没有外部模型请求。完整报告见 [v6本地基线](observations/20261029_v6_local/README.md)。

本次采集的 `index_attribution.attribution_safe=false`，原因是 Qdrant 服务集合没有独立可验证的 artifact manifest；关键词侧 manifest 已校验。即使组件排序与 v3 采集逐阶段相同，也不能据此单独归因 embedding/切分改动。

## 已有 13 题的离线复现（兼容入口）

2026-10-11答案工作台补充验证：501项评测相关测试通过；浏览器验收后的最终54项工作台、导入和报告定向回归通过，Ruff与9个相关源码文件的mypy通过。浏览器实际导出的20+1待审包已经过 `import-reviews` 和 `score --reviews-dir`，仍保持20题质量分母、21次执行与待审N/A；旧13题四组检索/答案聚合值完全不变。本轮没有新增模型调用，也没有自动填写新答案判断。

可直接打开本地 `data/reports/eval_answer_review_20261011/observed13_ready/index.html` 复核旧13题真实回答，或 `development20_ready/index.html` 查看20题本地摘录采集。两页都是新生成的空白复核，不会复制历史结论。页面内保存、导出后按上节导入；这些本地报告资产不提交到Git。

本地大 capture 位于 ignored `data/reports/eval_observation_20261005/live_capture.json`；远程仓库只保存紧凑观察记录。缺少该文件时不能靠紧凑答案记录重建全部调用和上下文，不得伪造 capture。

```powershell
.\.venv\Scripts\python.exe -B -m history_agent.evaluation.pilot score `
  --dataset evals/golden/observations/20261005/dataset.json `
  --capture data/reports/eval_observation_20261005/live_capture.json `
  --ranking-pools evals/golden/ranking_pools_v2.json `
  --assessments evals/golden/observations/20261005/answer_reviews.json `
  --process-reviews evals/golden/observations/20261005/process_reviews.json `
  --protocols evals/golden/development_protocols_v3.json `
  --output data/reports/eval_workflow_20261011/report.json
```

重算应保持：整题 3/13、事实 20/43、查询理解 11/13、生产召回并集 35/36（11题子集）、原文输入并集 22/43、最后上下文 14/30（9题子集；3题不可映射），44 次请求、115393 Token。此操作只重算已有观察，不代表新增一轮模型运行或人工批准。
