# Golden v2 设计与开发集进度

当前开发标注为 [development_annotations_v6.json](development_annotations_v6.json)，配套 [development_protocols_v6.json](development_protocols_v6.json)：**20道开发题，17道可答、3道拒答，85个必要事实、90个证据组**；截至2026-10-11，题目定义已批准8题、12题待审，候选等级与历史答案没有因此获批。2026-10-29 的 v6 只重绑两道拒答题引用的 `REQUIREMENTS.md` 哈希，恢复全量采集；不改变本题集定义。分批复核进度见 [DEVELOPMENT_ANNOTATION_PROGRESS.md](DEVELOPMENT_ANNOTATION_PROGRESS.md)，迁移说明见 [MIGRATION_V6.md](MIGRATION_V6.md)。

`reviewable-pilot-v5` 已支持20题协议及21个执行输入；v3的20题本地检索采集已完成，13题真实模型观察与新口径复核也已单独保留，入口见 [评测与比较流程](REPEATABLE_WORKFLOW.md) 和 [当前总览](README.md)。当前新采集仍需先处理冻结拒答依据与现有 `REQUIREMENTS.md` 哈希不一致的问题；协议可加载不等于原文锚点校验通过。10道保留题仍隔离，尚未完成30题正式Golden。

**以下文件说明和试点结果保留2026-09-23的13题基线口径**：43个必要事实/证据组、196条候选判断、12个固定池累计124成员。原13题、原v1和六题样板保持独立，该次执行结果见 [DEVELOPMENT_BASELINE.md](DEVELOPMENT_BASELINE.md)。新7题没有新增候选等级、真实模型回答或正式指标。

## 历史基线文件

- `development_v2.json`：13题历史开发集，保留原六题的定义及追加标签，新增七题。
- `ranking_pools_v2.json`：12个完全分级的固定小池；v1保留初始123成员，v2补入Top-5对照中一个已有标签的池外负例，绑定候选身份、来源SHA、选择策略与封印；暂定Agent口径。
- `answer_reviews_v1.json`：绑定上一轮六题真实采集及具体答案的逐事实/维度评审；提供可自动汇总的明确标签，不是自动语义裁判。
- `design_v2.json`：30 个可直接提问的问题，记录任务类型、来源范围、诊断目的、指标、数据划分及复核状态。
- `pilot_annotations.json`：6 个开发样板，含文件 SHA-256、PDF 物理页、原文短引、必要事实、证据组、禁止的结论与复核说明；已合入48条真实候选的 `agent_review` 暂定相关性标签。所有题的人工复核仍为pending，Agent判断不能冒充人工判断。
- `golden_questions.json`：原 12 题。本次不修改，历史 `reviewed=true` 不等于本次重新核对。

现有 Golden 12 题未引用已停用的 `lin_biao_chronology` 或 `deng_xiaoping_selected_works`。旧 47 题中有 10 题提及这两个来源，其中 8 题的证据页实际涉及停用来源；这些题不得原样迁入。新候选只使用目录中启用的来源，尤其补充新入库的邓小平年谱。

## 30 题配额与数据隔离

| 主诊断类型 | 总数 | 开发 | 保留 | 主要用途 |
|---|---:|---:|---:|---|
| 精确事实、日期、职务 | 6 | 4 | 2 | Recall、MRR；同名机构与相邻日期干扰 |
| 语义改写、观点概括 | 6 | 4 | 2 | embedding 语义召回增益 |
| 多证据、跨期、比较 | 6 | 4 | 2 | Top-K、分片与上下文覆盖 |
| 人物交集、困难候选与负例 | 4 | 2 | 2 | Precision、重排、主体与动作绑定 |
| 约束、路由、多轮 | 4 | 3 | 1 | 查询理解、硬约束和上下文选择 |
| 拒答、错误前提、材料不足 | 4 | 3 | 1 | 拒答与证据边界 |
| **合计** | **30** | **20** | **10** | 每题可适用多种指标 |

开发题优先继承旧题和 badCase 的诊断价值，同时加入新来源试点。保留题全部提供具体题干，但不预填未经核对的事实答案；`review_status=pending_source_review`、`run_allowed=false`、`tuning_allowed=false`，不进入本次运行器或调参流程。其正负性质、可答范围甚至是否保留该题，均需原文复核后决定。

划分单位是事件、篇目和共享证据组成的连通组，而不是随机题号。同一组只能处于一个 split。遵义单题、遵义军事领导三阶段题及遵义与庐山比较题归一个开发组；周恩来 1954 任职与 1954—1956 经历也同属开发组。保留候选预先选择不同主题，冻结前仍须对旧题库、badCase、开发题和真实证据页执行重叠审计；当前不声称已经证明完全独立。同义改写可以附属同一案例，但不能作为额外独立样本抬高题量。

## 六题先验证标注方法

| ID | 问题 | 已核对来源及诊断点 |
|---|---|---|
| `pilot_exact_deng_1952_appointment` | 1952年8月7日，邓小平被任命为什么职务？ | 邓年谱中卷 PDF 420；政务院不能写成国务院。页眉7月不能覆盖条目8月。 |
| `pilot_semantic_deng_1962_agriculture` | 1962年7月，邓小平怎样判断哪种农业生产组织形式更合适？ | 邓年谱下卷 PDF 384—386；以恢复生产、群众意愿、多样形式为命题，不能仅匹配“农业”或猫的比喻。 |
| `pilot_multievidence_zunyi_leadership` | 遵义会议、会后2月5日的常委分工和3月成立新“三人团”，分别怎样调整了中央军事领导？ | 党史一卷 PDF 483—484；三阶段与跨页续句不能混为一谈。 |
| `pilot_negative_cppcc_1949` | 毛泽东和周恩来在1949年10月9日是否共同当选为全国政协主席？请区分二人的职务。 | 毛年谱4卷 PDF 12—13；12页只有副主席名单开头，13页才有“当选为副主席”。 |
| `pilot_constraint_deng_1973_march` | 只依据《邓小平年谱（1904—1974）》下卷，1973年3月关于恢复邓小平职务和安排工作的决定分别是什么？ | 邓年谱下卷 PDF 644—645；限定来源，区别恢复职务与具体工作安排。 |
| `pilot_refusal_out_of_scope_2024` | 习近平在2024年考察了哪些地方？ | 依据项目1921—1978研究范围拒答；不编造行程，不使用历史引用支持2024年事实。 |

其中 3 题使用新邓年谱。Agent 已读取对应正文/OCR并核对 10 个 PDF 原图页面，实际计算 4 份原始 PDF 的 SHA-256，与提取记录一致。5 道可答题共 12 个必要事实、12 个证据组；拒答题没有历史证据目标，不计算 Recall、Precision、MRR、nDCG。图像检查是 Agent 核验，不是人工复核。

`quote` 只删除原提取/OCR文本中的空白，不擅自纠正其他字符。PDF物理页是稳定定位单位；印刷页仅辅助阅读。原图与 OCR 有争议时先交人工，不把机器修正后的文字伪称原文。

## v2试点实际实现的指标与分母

每个必要事实绑定一个或多个证据组。组间为 AND，组内替代原文为 OR；事实列出的多个 `evidence_group_ids` 也为 AND。例如政协题中的周恩来职务需要12页名单开头和13页续句，命中任意单页都不足以证明完整事实。

`pilot_metrics.py` 对每个阶段分别输出 `provisional` 与 `approved`。前者允许有记录的Agent暂定标签，只用于诊断；后者要求题目经人工批准并使用人工标签。当前13题均未获人工批准，正式指标保持不可评。

| 当前试点指标 | 分母和适用条件 |
|---|---|
| `required_group_recall@K` | 命中的必要证据组数 / 必要证据组总数；要求文件哈希有效，并命中完整原文锚点或具有有效支持组判断。一个组只计一次。 |
| `precision@K` | 前K位置中相关候选数 / **K**；0/1/2标签中 **>=1视为相关**。不足K的空位按0计；实际返回但未判断的候选是unknown，使该K的Precision不可评。重复相关位置仍计入分子，重复率另报。 |
| `mrr@K` | 单题为前K中首个相关候选（等级>=1）的倒数排名；首个已标相关项之前必须全部已判断，否则未知项可能改变排名，返回N/A。前K全已判且无相关项时为0。跨题同口径平均才是MRR。 |
| `annotated_mrr_lower_bound@K` | 仅按已标相关项计算的排名下界，与精确MRR分开保存，不能用来掩盖前方未标候选。 |
| `pool_ndcg@K` | 已实现固定池内 nDCG：gain=2^rel−1，折扣log2(rank+1)，整个池唯一候选生成理想排序。需全池有标签，前K候选均在池内，来源身份有效且IDCG>0，否则N/A；重复仅首位计增益。比较前核对池、等级与公式指纹。Agent暂定可算，人工正式仍待审。 |

拒答题没有检索相关性目标，全部检索质量指标不适用；不得把拒答题的召回、MRR或Precision当作0参与平均。最终回答使用显式逐事实评审和引用支持、来源/时间约束、路由、拒答及范围说明维度。事实covered计1，partial/missing/contradicted计0，unknown使对应事实Recall不可评；拒答没有事实分母。整体答案如有确定失败计0，无失败但存在未知项时N/A。程序汇总评审标签，不自动判断语义。当前有六题真实答案的Agent评审；新增七题尚无真实LLM答案评审，保持不可评。未实现的HitRate和更完整路由评分不宣称已完成。

如记录了真实模型调用，评分器可对实际生成请求的证据区计算组覆盖；摘要式上下文无法可靠映射原页时保留原文并明确不可按页评分。无LLM运行没有生成请求，不能把候选列表或最终引用列表冒充模型实际上下文。

同时保存有效分母、未标注数量和判断覆盖率。未标注是 unknown，不是0分。旧v1的页级命中只能作粗粒度诊断；本试点按原文/证据组评价，不能命中同页任何无关段落就拿满分。

候选相关性采用0/1/2：0不相关或不符合用户条件，1相关背景或部分支持，2直接支持必要事实。用 BM25、向量、融合及对比配置返回的候选合并去重，隐藏来自哪个配置，审核实际片段和必要的相邻原文。新配置返回未标候选时追加审核，再以统一更新后的标注重算双方；不能只给新配置改分母。

已为12道可答开发题完成Agent小池分级：5道原样板，加周恩来1954职务、邓小平1954任职、调查研究、矛盾论、首次党代会改写、月份地点约束、周恩来1954—1956经历。小池为关键词/向量/最终排序各前5并集；一大题额外加入3个独立核验的真实正例，仅用于评价分母，未插入检索结果。大K或新模型出现池外候选时需补盲审并重算所有配置；小池不是全语料相关证据全集。人工评审仍待办。

## 采集过程与实验顺序

固定题集、来源目录、文件和索引指纹后，分别保存原始问题、改写及路由、BM25/向量召回、融合、重排前后、最终上下文、答案与引用。每阶段保存候选位置和支持关系，用逐题损失定位是未召回、融合丢弃、重排下降还是上下文截断。尚未实施的阶段明确标为未执行，不制造重排结果。

先使用开发题跑不依赖最终生成的组件基线。评分器对同次运行列表计算K=1、3、5、10、20，这只是**同次排序前缀诊断**。真正比较配置Top-K时，应固定 `candidate_k` 后分别重新执行检索；生产覆盖策略本身受最终K影响，Top5运行不保证等于Top20运行的前5条，不能只截取代替实验。比较器核对两次分支候选的有序指纹；仅改变Top-K却候选不同或缺少可验证指纹时，不允许作单变量归因。

比较embedding时固定切分、候选量、融合与最终K；比较rerank时固定输入池与上下文预算，先观察MRR、Precision、必要组是否丢失及成本。nDCG当前可作固定小池内的Agent暂定诊断，结合必要证据Recall使用；人工批准后才用于正式验收。最后只对有证据改善的配置运行端到端，检查收益是否传到事实覆盖和引用支持。

正式报告保存代码提交、题集与标注版本、来源/索引指纹、模型、所有K值、随机性设置、逐题变化、阶段耗时及Token。30题规模下总分小涨不代表稳定泛化；必须展示退步题、主题分组结果和保留集结果。保留题完成审核冻结后才用于独立验收，不能循环看分数调参。

## 原六题试点流程（保留复现）

当前13题命令和评分参数见 [DEVELOPMENT_BASELINE.md](DEVELOPMENT_BASELINE.md)。下方保留六题历史命令；增加 `--ranking-pools evals/golden/ranking_pools_v2.json` 可计算池内nDCG。只有匹配的真实六题capture才能同时传 `--assessments evals/golden/answer_reviews_v1.json`。

在项目根目录运行下列模块命令。`collect` 默认不调用LLM，读取本地索引并记录真实检索阶段与本地降级答案。2026-09-22用户明确授权后，六题已执行真实Planner、检索反思和生成，见 [LIVE_EVALUATION.md](LIVE_EVALUATION.md)；本轮答案由Agent逐事实核查，没有额外调用外部语义裁判。启用 `--with-llm` 会向配置的外部模型服务发送问题及证据片段，不能把无LLM结果解释为端到端模型效果。

```powershell
# 分支候选固定30，分别真实运行最终Top20与Top5。
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot collect --dataset evals/golden/pilot_annotations.json --candidate-k 30 --top-k 20 --answer-top-k 10 --run-name pilot_top20 --output data/reports/pilot_top20_capture.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot collect --dataset evals/golden/pilot_annotations.json --candidate-k 30 --top-k 5 --answer-top-k 10 --run-name pilot_top5 --output data/reports/pilot_top5_capture.json

# 两次使用同一份最新标注重算，新增未知候选须先追加审核。
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset evals/golden/pilot_annotations.json --capture data/reports/pilot_top20_capture.json --output data/reports/pilot_top20_report.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset evals/golden/pilot_annotations.json --capture data/reports/pilot_top5_capture.json --output data/reports/pilot_top5_report.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot compare data/reports/pilot_top20_report.json data/reports/pilot_top5_report.json --output data/reports/pilot_topk_comparison.json
```

`--top-k`改变组件检索的最终数量，`--answer-top-k`是回答请求的独立参数；上述实验固定后者为10。`score`同时写JSON和同名Markdown，保留暂定/正式分数及N/A原因；当前 `compare` 比较暂定Agent口径，不能称为人工Golden验收。题干、证据定义、语料或评估分母变化时必须检查可比性。

本轮试点的 `attribution_safe` 只验证固定代码、相同有序分支候选的 Top-K 对照或重复基线；多变量改动、代码缺失或变化、候选变化和检索降级均不自动认定可归因。embedding/rerank 实验还需实现对应的单变量验证条件，当前可比较同口径指标，但不能借用这个试点标志证明因果隔离。

人工评审包隐藏候选来自哪个分支、原始排名和Agent预测，展示问题、候选全文及本地PDF链接。使用一个新输出目录，避免覆盖不可变评审包：

```powershell
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot_review build --dataset evals/golden/pilot_annotations.json --capture data/reports/pilot_top20_capture.json --output-dir data/reports/pilot_review_top20
```

打开生成的 `review.html`，由人工填写复核者，确认题干、证据、事实及拒答边界，逐项标相关性和真正支持的证据组，再导出 `review_decisions.json`。未判断选unknown，尚未完成的题保留pending。导入时指定实际下载文件路径：

```powershell
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot_review import --dataset evals/golden/pilot_annotations.json --capture data/reports/pilot_top20_capture.json --packet data/reports/pilot_review_top20/packet.json --decisions data/reports/pilot_review_top20/review_decisions.json --output data/reports/pilot_human_reviewed.json
.\.venv\Scripts\python.exe -m history_agent.evaluation.pilot score --dataset data/reports/pilot_human_reviewed.json --capture data/reports/pilot_top20_capture.json --output data/reports/pilot_human_reviewed_report.json
```

`import`验证题目、候选身份与包哈希，输出新数据集和审计记录，不覆盖原题集、capture或评审包。只接受人工明确作出的判断；没有确认的题和候选不会自动升级。若审核后修改题干、事实或证据定义，需要重新采集匹配的新capture，而不是复用不再对应的运行。

## 人工需要参与的部分

程序准备原页、短引、高亮、候选去重、建议相关性与评审表，并负责统计。人工确认四件事：原页/版本是否正确，原文支持到什么程度，候选对问题是否相关，歧义或争议如何裁定。所有30题的必要事实和回答边界需复核；至少12题的候选池需充分标注，复杂否定、跨页名单和来源冲突优先二次审核。审核者、时间、意见和修改原因必须留痕。

Agent 可提交预标注，但永远不能自动把 `human_review` 从pending改为已审核。每次实验无需重审稳定金标，只追加新候选与争议项。若原文无法支持问题，应缩小问法、重选题或明确资料不足，不能靠模型知识补成Golden。

## 进入正式v2的验收条件

1. 30题均有明确且经人工确认的答案边界、适用指标和来源依据；10道保留题完成原文核验与跨集泄漏审计。
2. 至少12题可实际计算Precision/nDCG；其余可答题能计算关键证据Recall/MRR，拒答题按边界维度评估。
3. 原文、PDF哈希、证据组、必要事实和候选等级具备复核记录；否定和人物/职务错配评分通过校准。
4. 使用固定Agent取得可稳定重复的开发基线与受控保留集验收；题集、协议及分母冻结后，再以独立任务完成只改K、embedding或rerank的可归因对比。这些Agent/harness实验不是题集制作的前置条件。
5. 新v2冻结后使用新版本报告，保留旧基线，不将标注口径变化包装成模型效果提升。
