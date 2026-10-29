# v6 标注迁移记录（2026-10-29）

## 问题

v3/v4/v5 的 `dev_refusal_einstein` 和 `dev_refusal_source_year` 在 `refusal_basis.project_basis` 中绑定 `REQUIREMENTS.md` 的字节哈希：

```text
冻结值  ee2877459c53b49b...
实际值  2b6fe88b1ef7fcf6...
```

`pilot collect` 在 `validate_anchors` 阶段会报 `project refusal basis changed`。由于协议加载要求数据集恰好包含 20 道开发题，不能只跳过这两道拒答题，结果**整个 v5 数据集都无法新采集**，包括 17 道可答题。

## 迁移范围

v6 只做了一件事：把两道拒答题的项目依据哈希重绑到当前 `REQUIREMENTS.md`，并同步版本号、协议绑定和复核队列。迁移前已确认三条规则原文仍然存在：

- 系统能够明确拒绝回答本地资料无法支持的问题
- 提示词和后置校验禁止模型把无来源常识写成核心事实
- 证据不足时返回 `insufficient_evidence`，不强行生成结论

**未改变**：20 道题的题干、分类、可答性、85 个必要事实、90 个证据组、93 条正向锚点、196 条候选判断、12 个固定排序池、8 题人工批准状态、12 题待审状态、10 道保留题。

因此 v6 不是新的题目版本，也不产生新的 Golden 标签；它只是恢复了可执行性。v3/v4/v5 原文件保持不变，旧 capture 继续按其绑定版本离线复核。

当前依据：

| 项目 | 值 |
|---|---|
| `REQUIREMENTS.md` SHA-256 | `2b6fe88b1ef7fcf66fcc8797c2aaa0c054fa7f5c965f6053a97a03f1b20cde60` |
| v6 题集指纹 | `513b684429d8ba5bf069f9c0d4b3c94415224f2529e160992c2dacea05dfebee` |
| v6 协议文件 SHA-256 | `8aa9b7e9d09a985fb18799da78db57a79030460fb06405250bc26c4ee2f31e9a` |

## 验证

1. `load_inputs(development_annotations_v6.json, development_protocols_v6.json)` 通过：20 题、21 输入、85 事实、90 证据组、196 候选判断、8 批准/12 待审。
2. `validate_anchors` 对 17 份启用文献、93 条正向锚点、6 条拒答元锚点和当前 `REQUIREMENTS.md` 全部通过。
3. 完成一次 20 题本地采集（0 次模型调用）并评分：[v6 本地基线](observations/20261029_v6_local/README.md)。
4. 新增 `tests/test_pilot_v6_release.py`，校验版本绑定和“旧 v5 不被改写”；现有评测测试继续通过。

## v6 本地基线摘要

| 指标 | 结果 |
|---|---:|
| 暂定 Recall@20（17 道可答题） | 0.609 |
| 正式 Recall@20（8 道已批准题，仅冻结锚点） | 0.567 |
| 暂定 Precision@5（12 道有候选标签题） | 0.700 |
| 暂定 MRR@5 | 0.917 |
| 暂定固定池 nDCG@5 | 0.731 |
| 关键词 / 向量 / 融合 / 最终 Recall@20 | 0.649 / 0.441 / 0.663 / 0.609 |
| HTTP 调用 / Token | 0 / N/A |

正式口径的 Precision/MRR/nDCG 仍为 0 道可评，因为 196 条候选判断全部是 `agent_review`，没有人工标签。`index_attribution.attribution_safe=false`，原因是 Qdrant 服务集合没有独立可验证的 artifact manifest。

## 仍未完成

1. **12 道题题目定义待审**：[review_queue_v6.json](review_queue_v6.json)，batch 3–5；逐题事实、证据和重点争议见 [PENDING_REVIEW_V6.md](PENDING_REVIEW_V6.md)。
2. **5 道新可答题没有候选相关性标签**：`dev_exact_zunyi_election`、`dev_multi_meetings`、`dev_constraint_history_isolation`、`dev_multi_mao_hunan`、`dev_intersection_mao_zhou_1949`。
3. **固定池仍是 Top-5 并集**：K=10/20 的 Precision/nDCG 和 reranker 实验仍不可评。
4. **10 道保留题只有题干**，没有事实、证据或可执行标注。
5. **v6 没有真实模型基线**；下一次带 `--with-llm` 的运行需要单独确认外发范围和成本。
6. **索引归因**：若要支持 embedding/切分/rerank 的单变量归因，需要给 Qdrant 服务补充可验证的 artifact manifest 绑定。

## 不要做

- 不要直接修改 v3/v4/v5 的冻结哈希或跳过 `validate_anchors`。
- 不要把 v6 的 8 题批准解释为候选相关性、排序池或答案已批准。
- 不要用 v6 本地采集冒充真实模型成绩。
