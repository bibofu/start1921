"""Build versioned, source-bound guidance for explicit answer review.

The packet is an aid for a reviewer, never a set of new historical labels or an
automatic judge. It leaves frozen facts, denominators and human approval intact.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from history_agent.evaluation.pilot_answers import AnswerReviews, fingerprint, validate_reviews
from history_agent.evaluation.pilot_models import case_definition

CALIBRATION_VERSION = "answer-calibration-v1"

# Case-specific interpretations apply only to the frozen definitions reviewed here.
_KNOWN_DEFINITIONS = {
    "pilot_exact_deng_1952_appointment": (
        "3973e913609efba37ad561d4a753be36976ac467ba4598e33aa1f8af64fd4610"
    ),
    "pilot_semantic_deng_1962_agriculture": (
        "14ee4ceb3fe07da3c2c73acfc8b6f233a1e9b2c3370fa80900ca1141fa36ac60"
    ),
    "pilot_multievidence_zunyi_leadership": (
        "a02140445fc026f1873bb2c11c87bdcd9b148520bebf3b148751cb82a6f3b6f4"
    ),
    "pilot_negative_cppcc_1949": (
        "3ff9d249470458f12008bc464bf74a5d706232a60e449beb6101aa31e0acb5eb"
    ),
    "pilot_constraint_deng_1973_march": (
        "2f81245c9f3f0d6a0f58c450bf5bfb4813a7facb153eb7de6788fd1973d24c82"
    ),
    "pilot_refusal_out_of_scope_2024": (
        "1765ab8de6b56a03324cfec02fa4c731fe50d6b75f7d5c26c357b6ba002acc6d"
    ),
    "dev_exact_zhou_1954": ("daf9f746054edc200ae299fb373120101f51f1ad9bc9a8f2cd49282a99b03bf7"),
    "dev_exact_deng_1954": ("a6ff956c61d2430bb935c2dd60e3827bb7cf148ec6de824bf09a0bc95491d7d1"),
    "dev_constraint_month_place": (
        "9402c8628342eb6fcf83862534f6dca894389ada01bdf967f4a38926cef68e59"
    ),
    "dev_multi_zhou_periods": ("e6d0fd1201a92535ce0a531a13dea1acd0299cbe7bf5ba05f30a5552bf85de7c"),
    "dev_semantic_investigation": (
        "7cff605430f492ad1adbdcb5ce9469c3dda43bf390eb4654fa3c59126210b3c1"
    ),
    "dev_semantic_contradiction": (
        "fa123047d99f5ddab5d157136989ef66a7a61613e3050c987440a5bfc942ae64"
    ),
    "dev_semantic_first_congress": (
        "f4401b3b06666ed4f049e9b5afbeff42587be747262f2fa264b8a4c06d29d53e"
    ),
    "dev_exact_zunyi_election": (
        "f7dbb53f85b52050e453551baed45c8cabc04e76658f69c8f71f7c3e03ac8176"
    ),
    "dev_multi_meetings": ("0f761e38390e116229fcc0ebbbb22b4dfd34daa3b2022302b04a9635b800eeb3"),
    "dev_constraint_history_isolation": (
        "6de4e1f9d0fba0fffe596805ef8e4d39ccc5a9f5472b538d7dbde67db3f6650e"
    ),
    "dev_multi_mao_hunan": ("628ab73f3dd7553525c345a1a87a4d50bfd08b319bd84494dc509e7d7db0c70c"),
    "dev_intersection_mao_zhou_1949": (
        "247693113e2170985c2f8dcb7e63807f33a39c99e6e20a70c013ad0cc0399aac"
    ),
    "dev_refusal_einstein": ("6ed2001f207c3f0ad8e3c39ee84c49e0b97f6e6a7661ce3630ac09c7aba5d552"),
    "dev_refusal_source_year": ("bb82e0909bd1471b9a13a608712b2391cbbc634a2e86b2c275152a720becf400"),
}

FACT_STATUSES = {
    "covered": {
        "label": "完整覆盖",
        "criterion": (
            "交付正文完整表达本条必要命题，允许同义改写、合并叙述和上下文明示"
            "的指代；人物、动作、时间、地点和限定关系不能变义。引用是否支持另"
            "判。"
        ),
        "score": 1,
    },
    "partial": {
        "label": "部分覆盖",
        "criterion": (
            "正文已表达本条的一部分，但仍缺必要语义、关系或限定；已知遗漏不能"
            "记 unknown，也不因部分有用就算完整覆盖。"
        ),
        "score": 0,
    },
    "missing": {
        "label": "未覆盖",
        "criterion": (
            "已检查完整交付正文，本条必要命题未被表达；只有引文、检索结果或未"
            "交付草稿中出现不算正文覆盖。"
        ),
        "score": 0,
    },
    "contradicted": {
        "label": "明确相矛盾",
        "criterion": (
            "正文明确断言与本条相冲突的事实或绑定关系；同一命题既有正确说法又"
            "有未消解的冲突说法也应指出冲突，不能仅挑正确句算 covered"
            "。"
        ),
        "score": 0,
    },
    "unknown": {
        "label": "尚不能裁定",
        "criterion": (
            "尚未复核，或材料、OCR、指代等歧义使复核者不能可靠裁定；说明待"
            "查内容，不能当作缺失或零分。"
        ),
        "score": None,
    },
}

SUPPORT_STATUSES = {
    "supported": {
        "label": "引用支持",
        "criterion": (
            "本条已表达的主张由实际交付引用支持，来源身份、原文真实性及主张蕴"
            "含均可核对；填写交付的证据 ID。"
        ),
    },
    "partial": {
        "label": "引用部分支持",
        "criterion": (
            "实际引用仅支持已表达主张的一部分，或缺少跨页/跨组的必要关系；列出已支持和未支持部分。"
        ),
    },
    "unsupported": {
        "label": "引用不支持",
        "criterion": (
            "已检查主张及引用，缺引用、无关引文、错误绑定或截断使其不能支持已"
            "表达主张；正确的金标原页不能补成已交付引用。"
        ),
    },
    "unknown": {
        "label": "引用尚不能裁定",
        "criterion": "尚未完成支持核验或无法可靠辨识交付片段/原图；不是已经证实无支持。",
    },
    "not_applicable": {
        "label": "无此支持对象",
        "criterion": (
            "正文没有表达本条主张时可用，并说明原因；不能用于逃避检查已表达但无引用的历史断言。"
        ),
    },
}

PRINCIPLES = [
    "本包是 Agent 整理的复核辅助判据，仍待人工核验，不是新历史标签、人工共识或整题批准。",
    (
        "以冻结 facts 为最低必要覆盖，reference_answ"
        "er 只供参考；不要求逐字复述、相同顺序、相同篇幅或未列入 fa"
        "cts 的扩展。"
    ),
    (
        "先判断正文表达了什么，再核对实际交付引用支持什么；引用中的内容不"
        "能替正文补答，正文正确也不保证引用支持。"
    ),
    (
        "必要事实 Recall 仍以 covered/固定必要事实数计算"
        "；partial、missing、contradicted 不计"
        " covered，任一必要事实 unknown 时完整 Reca"
        "ll 为 N/A。"
    ),
    "复合事实内的检查点用于解释同一个事实的判定，不拆成新分母，不设置部分分，也不提高通过阈值。",
    (
        "时间或主体若已由题目及答案结构明确绑定，无需每句重复；出现冲突、"
        "歧义、年代前移或机构替换时必须单独核对。"
    ),
    (
        "有据且正确的额外内容可接受，不扩大本版分母；额外事实断言仍需核查"
        "，错误或无依据扩展不能借最低事实齐全通过引用支持。"
    ),
    "判据或标注需要改变时应升版并对比较双方统一重审；本包不回写旧13题的判断与分数。",
    (
        "provisional 可包含明确署名的 Agent 复核；ap"
        "proved 仍同时需要整题人工批准及答案 human_revi"
        "ew，不因使用此包而自动满足。"
    ),
]

DIMENSION_GUIDANCE = {
    "citation_support": (
        "检查整个交付回答的事实断言，包括必要事实之外的扩展；对来源真实性"
        "及主张蕴含分别核验。有错误或无依据的事实扩展应 fail；尚未核"
        "查的断言应 unknown，不能只看必要事实就 pass。合理拒"
        "答没有正向历史断言时不强求虚构正向引用，已有引用也不得滥用。"
    ),
    "source_constraint": (
        "只有题干或绑定协议明确要求的来源才是硬限制；annotation"
        "_sources_not_exclusive 只是金标取材范围。"
        "硬限制下不得混入其他来源补答；未设硬限制且确无适用约束时填 no"
        "t_applicable 并解释。"
    ),
    "time_constraint": (
        "核对题目要求的年份、月份、日级条件及事件阶段。书名年代、页眉年代"
        "、收电人所在地均不能替代目标事件的时间地点；源书范围不足与项目时"
        "间越界须区分。"
    ),
    "routing": (
        "结合可观察的实际执行计划/路由判定是否保留问题与约束，允许等效路"
        "线；仅答案看起来正确不足以证明过程通过，缺少过程证据时 unkn"
        "own。"
    ),
    "safe_refusal": (
        "有证据可答时不能无理由整体拒答；拒答题不能编造活动/职务，资料不"
        "足不等于历史上没有该事实。对局部证据缺口可明确披露，不自动抹去已"
        "回答事实。"
    ),
    "scope_explanation": (
        "范围说明须针对实际限制，不能把开放题的最低清单宣称为穷尽全集；合"
        "理说明未覆盖子项可以保留，但不能抵消对应必要事实的遗漏。"
    ),
}

# These break down existing compound claims only. Their children are not scoring
# units, and they deliberately retain the frozen dates and subject relationships.
_FACT_PARTS: dict[str, list[str]] = {
    "meeting_membership": [
        "遵义会议选举毛泽东为中央政治局常委。",
        "取消原三人团；仍由朱德、周恩来指挥军事。",
        "周恩来负党内最后决心责任。",
    ],
    "march_group": [
        "新三人团成立于3月，由毛泽东、周恩来、王稼祥组成。",
        "周恩来任团长，负责指挥全军军事行动。",
    ],
    "restore_status": [
        "恢复邓小平党的组织生活和国务院副总理职务。",
        "由国务院分配适当工作。",
    ],
    "state_council_work": [
        "3月29日晚会议决定正式参加国务院业务组工作。",
        "以副总理身份参加外事活动。",
    ],
    "zhou_premier_before_september": [
        "1954年初仍任政务院总理。",
        "9月政府机构改组后转任国务院总理，保留职衔转换。",
    ],
    "zhou_party_secretariat": ["1954年任中共中央书记处书记；不得把1956年中央副主席职务前移。"],
    "zhou_cppcc_before_december": ["1954年12月当选全国政协主席以前任全国政协副主席。"],
    "mao_command": [
        "在北平期间继续指挥军事，3月27日/29日为中央军委起草复电。",
        "同意推迟到4月15日发动渡江战斗。",
    ],
    "zhou_1954_government": [
        "1954年9月任国务院总理并兼任外交部长。",
        "1954年12月当选全国政协主席。",
    ],
    "zhou_synthesis": [
        "归纳1954年和平外交与国家制度建设。",
        "归纳1955年亚非团结与一五建设推进。",
        "归纳1956年知识人才动员与经济综合平衡，表达跨年变化。",
    ],
    "oppose_book_worship": ["学习马克思主义理论并同中国实际相结合，反对脱离实际的本本主义。"],
    "learn_by_discussion": ["向有经验的群众和干部学习，通过调查会、讨论了解真实情况。"],
    "conditional_priority": [
        "主要与次要矛盾的地位随具体条件和发展阶段改变。",
        (
            "冻结命题所用例子为帝国主义侵略战争时民族矛盾上升、内部阶级矛盾暂"
            "居次要；只说有主要矛盾或只列对立双方不能表达这种主次转换。"
        ),
    ],
    "programme": [
        "一大讨论通过党纲，确定名称为中国共产党。",
        "纲领包括推翻资产阶级政权、承认无产阶级专政、消灭资本家私有制等内容。",
        "提出联合共产国际。",
    ],
    "leadership": [
        "暂设中央局，由陈独秀、张国焘、李达组成。",
        "陈独秀任书记、张国焘负责组织、李达负责宣传。",
    ],
    "zunyi_process": [
        "多数与会者反对博古总结报告、赞同毛泽东等意见。",
        "指定张闻天起草决议，交常委审查并发支部讨论。",
    ],
    "zunyi_organization": [
        "选举毛泽东为政治局常委，取消原三人团。",
        "仍由朱德和周恩来指挥军事，周恩来负党内最后决心责任。",
    ],
    "lushan_letter": [
        "彭德怀的信在肯定成绩同时提出工作问题和总结教训。",
        "7月16日印发讨论，引起对信件性质的争论，会议延长。",
    ],
    "lushan_plenum": [
        "8月2日至16日八届八中全会接续召开。",
        "形成反右倾及将彭德怀等认定为反党集团的决议。",
    ],
    "battle_forces": ["华东、中原两支野战军及相关军区部队为主，参战解放军共约60万人。"],
    "battle_command": [
        "总前委成员为刘伯承、陈毅、邓小平、粟裕、谭震林。",
        "邓小平任书记，统筹作战与支前。",
    ],
    "battle_stage_three": [
        "第三阶段为12月16日至1949年1月10日。",
        "1月6日总攻后歼灭邱清泉、李弥兵团、俘杜聿明，战役结束。",
    ],
}

_CASE_NOTES = {
    "pilot_multievidence_zunyi_leadership": [
        (
            "已采纳的限定裁定：3月成立、毛周王组成、周恩来团长及职责为必要事"
            "实；中旬/下旬不作硬性评分。此项裁定不等于整题获批。"
        ),
        "遵义会议、2月5日分工、3月新三人团必须分阶段；只漏旬别不判 partial。",
    ],
    "dev_exact_zhou_1954": [
        (
            "六条事实是本版主要职务的最低覆盖；年初和年末的机构、政协职务转换"
            "均需表达。其他有据职务可补充。"
        ),
        "不要求逐字写出反面提醒，但不得将国务院总理覆盖全年或将1956年中央副主席职务提前。",
    ],
    "dev_multi_zhou_periods": [
        "六类代表活动和一项跨年综合共七条；列表完整但无跨年主题归纳仍缺 zhou_synthesis。",
        "不要求固定标题；等义总结可以覆盖。各年主题是代表性归纳，不是排他的唯一工作。",
    ],
    "dev_semantic_investigation": [
        (
            "四项观点是最低覆盖；不要求照抄名言，有据的额外观点可以接受。反本"
            "本主义不能被改写为反对理论学习。"
        ),
        "亲身深入调查不等于每个调查点都必须由本人完成。",
    ],
    "dev_semantic_contradiction": [
        (
            "区分主要矛盾与矛盾的主要方面；必须表达条件变化导致主次地位变化，"
            "不能以仅有主要矛盾定义代替。"
        ),
        "保留冻结命题的条件/阶段与主次转换关系；不要求 reference_answer 的原句措辞。",
    ],
    "dev_multi_meetings": [
        "两次会议分别覆盖核心问题、进程、影响；可采用表格或其他结构。",
        "清单之外有据的比较角度不扣分；原文评价需要出处归属，不能将先后顺序自动升级为因果。",
    ],
    "dev_constraint_history_isolation": [
        "两臂均以当前淮海战役问题的同十项必要事实复核；控制臂不增加独立题数。",
        (
            "旧轮林彪实体和1930—1949职务条件不应污染当前问题；回答相"
            "似或都正确不能替代四项过程隔离检查。"
        ),
    ],
    "dev_multi_mao_hunan": [
        (
            "固定六年1921—1926，事实分母分别为2、2、2、1、5、2"
            "，总计14；1925年多项不能抵消漏1924或1926。"
        ),
        (
            "地点必须是湖南境内实际活动；上海、广州、江西安源活动可作背景但不"
            "计湖南事件；1927年考察不能前移。"
        ),
        (
            "有据新增活动可补充，不扩大本版最低清单；六年都已有正向证据，不能"
            "以未召回为由声称某年没有活动。"
        ),
    ],
    "dev_intersection_mao_zhou_1949": [
        "两人必须参与同一明确动作；同页共现、泛泛同时任职或单方活动不算共同动作。",
        "五件事是代表性最低覆盖，不是1949年全部交集；跨页主体、日期与动作关系须合读。",
    ],
    "dev_refusal_einstein": [
        "1925年在项目时间范围内，拒答依据是当前本地证据不能支持题设，不是时间越界。",
        "允许询问所指党派；不得编造职务，也不得将检索无结果说成历史上从无任职。",
    ],
    "dev_refusal_source_year": [
        "1975年在项目范围内，但指定1904—1974版年谱不能支持1975全年全部活动。",
        "书中提及1975或次年计划不等于系统记录全年；不能混入其他来源后声称只依据本书。",
    ],
}

_EXAMPLES = {
    "pilot_semantic_deng_1962_agriculture": [
        {
            "id": "equivalent_expression",
            "fact_id": "respect_preference",
            "answer_excerpt": "应尊重农民的意愿，让他们采用愿意采取的生产形式。",
            "expected_status": "covered",
            "expected_support_status": "unknown",
            "reason": (
                "同义表达保留群众意愿与形式选择关系；没有实际交付引用可供核验，支持仍 unknown。"
            ),
        },
        {
            "id": "related_but_incomplete",
            "fact_id": "respect_preference",
            "answer_excerpt": "群众的要求有道理，应认真研究。",
            "expected_status": "partial",
            "expected_support_status": "unknown",
            "reason": "已涉及群众意见，但尚未表达尊重其愿意采取的形式这一选择原则。",
        },
    ],
    "pilot_constraint_deng_1973_march": [
        {
            "id": "body_and_citation_separate",
            "fact_id": "restore_status",
            "answer_excerpt": "恢复邓小平党的组织生活和国务院副总理职务。",
            "expected_status": "partial",
            "expected_support_status": "supported",
            "scenario": "假设实际交付引文已核实支持这句话，并且包含由国务院分配适当工作的后句。",
            "reason": (
                "正文缺工作分配，事实仍 partial；引文支持已表达的部分可以"
                " supported，不能拿引用后句补正文。"
            ),
        },
        {
            "id": "citation_only_is_not_body",
            "fact_id": "attend_policy_discussion",
            "answer_excerpt": "",
            "expected_status": "missing",
            "expected_support_status": "not_applicable",
            "scenario": "完整正文没有重要政策问题列席政治局参加讨论；只有引用卡片含该句。",
            "reason": "正文无该命题，因此 missing；不能因引用卡片含有它而判 covered。",
        },
    ],
    "pilot_exact_deng_1952_appointment": [
        {
            "id": "institution_contradiction",
            "fact_id": "appointed_vice_premier",
            "answer_excerpt": "1952年8月7日任国务院副总理。",
            "expected_status": "contradicted",
            "expected_support_status": "unsupported",
            "scenario": "所交付的是本题已经核实的政务院任命原文。",
            "reason": "机构关系明确冲突，不是措辞差异；引文也不支持国务院任命断言。",
        },
    ],
    "pilot_multievidence_zunyi_leadership": [
        {
            "id": "accepted_month_scope",
            "fact_id": "march_group",
            "answer_excerpt": (
                "3月，毛泽东、周恩来、王稼祥组成新三人团，周恩来任团长，指挥全军军事行动。"
            ),
            "expected_status": "covered",
            "expected_support_status": "unknown",
            "reason": "完整表达已采纳的最低命题；没有旬别不扣分，实际引用支持仍需单独核验。",
        },
    ],
    "dev_semantic_contradiction": [
        {
            "id": "unknown_is_not_missing",
            "fact_id": "conditional_priority",
            "answer_excerpt": "主次地位随条件变化，但此处原文显示不完整。",
            "expected_status": "unknown",
            "expected_support_status": "unknown",
            "scenario": (
                "复核材料损坏，复核者无法读到完整交付正文与相关引用，尚不能确定完整表达或矛盾。"
            ),
            "reason": (
                "这里 unknown 来自复核证据不足；若已完整读完正文且确认仅"
                "表达一部分，应改判 partial。"
            ),
        },
    ],
}


def _fact_packet(
    case: dict[str, Any], fact: dict[str, Any], *, known_definition: bool
) -> dict[str, Any]:
    fact_id = fact["id"]
    groups = {group["id"]: group for group in case["evidence_groups"]}
    group_ids = fact["evidence_group_ids"]
    if not set(group_ids) <= set(groups):
        raise ValueError("calibration fact refers to an unknown evidence group")
    non_requirements = ["不要求参考答案的逐字措辞；检查点不成为新的计分单位。"]
    if known_definition and fact_id == "march_group":
        non_requirements.append("中旬/下旬不作硬性评分；只要求3月。")
    if known_definition and fact_id in {"zhou_party_secretariat", "zhou_synthesis"}:
        non_requirements.append(
            "正确表达必要命题即可，不要求逐字补写事实中的反面提醒；不得作相反断言。"
        )
    return {
        "fact_id": fact_id,
        "claim": fact["claim"],
        "required": fact.get("required", True),
        "criterion": (
            "按下列冻结命题检查完整语义；完整为 covered，已表达部分但"
            "缺必要内容为 partial，正文无命题为 missing，明确"
            "冲突为 contradicted，无法裁定为 unknown。引"
            "用支持另判。"
        ),
        "semantic_requirements": deepcopy(
            _FACT_PARTS.get(fact_id, [fact["claim"]]) if known_definition else [fact["claim"]]
        ),
        "non_requirements": non_requirements,
        "evidence_group_ids": deepcopy(group_ids),
        "evidence_groups": [deepcopy(groups[group_id]) for group_id in group_ids],
        "source_refs": [
            f"dataset.cases[id={case['id']}].facts[id={fact_id}]",
            *[
                f"dataset.cases[id={case['id']}].evidence_groups[id={group_id}]"
                for group_id in group_ids
            ],
        ],
    }


def build_calibration_packet(
    cases: list[dict[str, Any]],
    protocols: dict[str, Any] | None = None,
    *,
    dataset_sha256: str,
) -> dict[str, Any]:
    """Return deterministic guidance; callers validate input releases separately.

    ``calibration_sha256`` hashes this packet without that self-digest field.
    A review/bundle may additionally bind ``fingerprint(packet)`` (the complete
    packet); those two hashes have intentionally different scopes.
    """
    if len(dataset_sha256) != 64 or any(c not in "0123456789abcdef" for c in dataset_sha256):
        raise ValueError("calibration needs a canonical dataset SHA-256")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate calibration case IDs")
    protocol_rows = protocols.get("cases", []) if protocols else []
    if len({row["case_id"] for row in protocol_rows}) != len(protocol_rows):
        raise ValueError("duplicate calibration protocol case IDs")
    by_protocol = {row["case_id"]: row for row in protocol_rows}
    output = []
    for case in cases:
        case_id = case["id"]
        definition_sha = fingerprint(case_definition(case))
        known_definition = _KNOWN_DEFINITIONS.get(case_id) == definition_sha
        protocol = by_protocol.get(case_id)
        if protocols is not None and protocol is None:
            raise ValueError("missing calibration protocol case")
        if protocol and protocol.get("case_definition_sha256") != definition_sha:
            raise ValueError("calibration protocol belongs to a different case definition")
        facts = case["facts"]
        if len({fact["id"] for fact in facts}) != len(facts):
            raise ValueError("duplicate calibration fact IDs")
        required = [fact["id"] for fact in facts if fact.get("required", True)]
        if protocol and protocol["required_fact_ids"] != required:
            raise ValueError("calibration must preserve protocol required fact identities")
        examples = deepcopy(_EXAMPLES.get(case_id, [])) if known_definition else []
        for example in examples:
            example["kind"] = "synthetic_scoring_example_not_annotation"
            example["review_status"] = "agent_suggested_human_pending"
        specialist = (protocol or {}).get("specialist_protocol") or {}
        output.append(
            {
                "case_id": case_id,
                "question": case["question"],
                "case_definition_sha256": definition_sha,
                "required_fact_count": len(required),
                "required_fact_ids": required,
                "fact_denominator_policy": "frozen_required_facts_only",
                "answerability": case["answerability"],
                "facts": [
                    _fact_packet(case, fact, known_definition=known_definition) for fact in facts
                ],
                "case_specific_guidance_applied": known_definition,
                "review_focus": deepcopy((protocol or {}).get("human_review_focus", [])),
                "constraints": {
                    "source_scope": deepcopy((protocol or {}).get("source_scope", [])),
                    "source_scope_kind": (protocol or {}).get(
                        "source_scope_kind", "consult_question_and_frozen_case"
                    ),
                    "forbidden_claims": deepcopy(case.get("forbidden_claims", [])),
                    "refusal_basis": deepcopy(case.get("refusal_basis")),
                },
                "boundary_notes": deepcopy(_CASE_NOTES.get(case_id, []))
                if known_definition
                else [],
                "specialist_boundary": {
                    key: deepcopy(specialist[key])
                    for key in ("answer_boundary", "conversation_protocol", "coverage_scope")
                    if key in specialist
                },
                "examples": examples,
                "case_human_review": deepcopy(case["human_review"]),
                "source_refs": [
                    f"dataset.cases[id={case_id}]",
                    *([f"protocols.cases[case_id={case_id}]"] if protocol else []),
                ],
            }
        )
    packet = {
        "schema_version": 1,
        "rubric_version": CALIBRATION_VERSION,
        "dataset_sha256": dataset_sha256,
        "protocol_sha256": fingerprint(protocols) if protocols is not None else None,
        "annotation_status": "guidance_only_human_pending",
        "policy": {
            "fact_statuses": deepcopy(FACT_STATUSES),
            "support_statuses": deepcopy(SUPPORT_STATUSES),
            "principles": deepcopy(PRINCIPLES),
            "dimension_guidance": deepcopy(DIMENSION_GUIDANCE),
            "frozen_open_question_policy": (protocols or {}).get("open_question_policy"),
            "automatic_judgments": False,
            "changes_frozen_annotations": False,
            "changes_human_approval": False,
        },
        "independent_case_count": len(cases),
        "required_fact_count": sum(row["required_fact_count"] for row in output),
        "cases": output,
    }
    packet["calibration_sha256"] = fingerprint(packet)
    return packet


def validate_calibration_packet(
    packet: dict[str, Any],
    cases: list[dict[str, Any]],
    protocols: dict[str, Any] | None = None,
    *,
    dataset_sha256: str,
) -> None:
    """Reject altered guidance, stale versions, missing cases and changed inputs."""
    expected = build_calibration_packet(cases, protocols, dataset_sha256=dataset_sha256)
    if packet != expected:
        raise ValueError("calibration packet differs from its versioned guidance or bound inputs")


def validate_review_decisions(
    reviews: AnswerReviews,
    capture: dict[str, Any],
    cases: list[dict[str, Any]],
    protocols: dict[str, Any] | None = None,
) -> None:
    """Check new calibrated reviews without inferring any semantic judgments.

    Call this only for reviews explicitly bound to a calibration packet. Historical
    reviews retain their original validator. Delivered citation/metadata content
    remains a reviewer judgment: metadata may support a refusal's stated scope,
    but it cannot be silently promoted to positive historical fact evidence.
    """
    validate_reviews(reviews, capture, cases)
    by_case = {case["id"]: case for case in cases}
    by_raw = {raw["case_id"]: raw for raw in capture["cases"]}
    by_protocol = {row["case_id"]: row for row in (protocols or {}).get("cases", [])}
    placeholders = {
        "待复核",
        "待人工复核",
        "待审",
        "未复核",
        "待逐项复核",
        "pending",
        "todo",
        "unknown",
        "not reviewed",
        "review required",
        "n/a",
        "na",
        "不适用",
    }

    def substantive(reason: str) -> bool:
        normalized = reason.strip().strip("。.：: ").lower()
        return normalized not in placeholders and not normalized.startswith(
            ("待", "awaiting_", "pending", "todo")
        )

    for review in reviews.cases:
        case = by_case[review.case_id]
        raw = by_raw[review.case_id]
        protocol = by_protocol.get(review.case_id, {})
        for fact in review.facts:
            judged = fact.status != "unknown" or fact.support_status != "unknown"
            if judged and not substantive(fact.reason):
                raise ValueError("calibrated fact judgments require a substantive reason")
            if fact.status in {"covered", "partial", "contradicted"}:
                if not fact.answer_excerpt or not fact.answer_excerpt.strip():
                    raise ValueError("calibrated expressed facts require a verbatim answer excerpt")
                if fact.support_status == "not_applicable":
                    raise ValueError("an expressed fact needs a support judgment or unknown")
            if fact.status == "missing" and fact.support_status not in {
                "unknown",
                "not_applicable",
            }:
                raise ValueError("missing body fact cannot be labeled citation-supported")
        for name, judgment in review.dimensions.items():
            if judgment.status != "unknown" and not substantive(judgment.reason):
                raise ValueError("calibrated dimension judgments require a substantive reason")
            if judgment.status != "not_applicable":
                continue
            applicable = name == "routing"
            applicable |= name == "citation_support" and bool(
                case["facts"] or raw["answer"]["citations"]
            )
            applicable |= name in {"safe_refusal", "scope_explanation"} and (
                case["answerability"] != "answerable"
            )
            applicable |= name == "source_constraint" and (
                protocol.get("source_scope_kind") == "hard_user_constraint"
                or "只依据" in case["question"]
            )
            applicable |= name == "time_constraint" and bool(
                re.search(r"(?:18|19|20)\d{2}|\d{1,2}月", case["question"])
            )
            if applicable:
                raise ValueError(f"calibrated applicable dimension cannot be N/A: {name}")
