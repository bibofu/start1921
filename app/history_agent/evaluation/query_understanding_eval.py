"""Query-understanding evaluation: schema, rule baseline, LLM baseline, metrics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from history_agent.answering.models import ConversationMessage, QuestionRequest
from history_agent.answering.planning import compile_research_plan
from history_agent.answering.query_understanding import plan_question
from history_agent.config import Settings
from history_agent.retrieval.hybrid import cpc_congress_ordinals
from history_agent.retrieval.keyword_common import infer_year_range

Intent = Literal[
    "general",
    "event_overview",
    "timeline",
    "intersection",
    "viewpoint",
    "observation",
    "comparison",
    "causal_analysis",
    "out_of_scope",
]
MentionType = Literal[
    "person",
    "person_group",
    "event",
    "congress",
    "document",
    "place",
    "organization",
    "period",
    "other",
]
Route = Literal["fast_fact", "deep", "clarify"]
YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")


class QueryMention(BaseModel):
    text: str = Field(min_length=1)
    type: MentionType
    canonical: list[str] = Field(min_length=1)


class QueryTime(BaseModel):
    start: int
    end: int
    precision: Literal["year", "month", "day", "period"]


class QueryUnderstandingCase(BaseModel):
    id: str = Field(min_length=1)
    split: Literal["development", "holdout"]
    question: str = Field(min_length=2)
    history: list[ConversationMessage] = Field(default_factory=list)
    intent: Intent
    route: Route
    flags: list[str] = Field(default_factory=list)
    mentions: list[QueryMention] = Field(default_factory=list)
    time: QueryTime | None = None
    constraints: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    review_status: Literal["agent_prepared", "human_approved"] = "agent_prepared"


class QueryUnderstandingDataset(BaseModel):
    schema_version: Literal[1] = 1
    version: str = Field(min_length=1)
    description: str = ""
    cases: list[QueryUnderstandingCase] = Field(min_length=1)



def canonical_key(value: str) -> str:
    text = value.replace("《", "").replace("》", "").strip()
    text = re.sub(r"[（(][^）)]*[）)]\s*$", "", text)
    congress = re.fullmatch(r"中国共产党第([一二三四五六七八九十]+)次全国代表大会", text)
    if congress is not None:
        return f"中共{congress.group(1)}大"
    text = text.replace("中华人民共和国", "")
    text = text.replace("红军学校", "红军大学")
    for suffix in ("运动", "初期", "时期"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def canonical_keys(value: str) -> set[str]:
    return {
        canonical_key(part)
        for part in re.split(r"[、,，/]", value)
        if part.strip()
    }


def intent_family(intent: str) -> str:
    return "fact" if intent in {"general", "event_overview", "timeline"} else intent


class Prediction(BaseModel):
    intent: Intent
    route: Route
    canonicals: list[str] = Field(default_factory=list)
    time: QueryTime | None = None
    needs_clarification: bool = False


def load_dataset(path: Path) -> QueryUnderstandingDataset:
    return QueryUnderstandingDataset.model_validate_json(path.read_text(encoding="utf-8"))


def predict_with_rules(case: QueryUnderstandingCase, aliases_path: Path) -> Prediction:
    plan = compile_research_plan(case.question, None, aliases_path).interpretation
    people = [
        entity.canonical for entity in plan.entities if entity.type == "person"
    ]
    congress = [f"中共{ordinal}大" for ordinal in cpc_congress_ordinals(case.question)]
    time = None
    if plan.start_year is not None and plan.end_year is not None:
        time = QueryTime(
            start=plan.start_year,
            end=plan.end_year,
            precision="year" if plan.start_year == plan.end_year else "period",
        )
    else:
        years = sorted({int(match.group()) for match in YEAR.finditer(case.question)})
        period = infer_year_range(case.question, years)
        if period:
            time = QueryTime(
                start=period[0],
                end=period[1],
                precision="year" if period[0] == period[1] else "period",
            )
    route: Route = (
        "clarify"
        if plan.needs_clarification
        else "fast_fact"
        if plan.retrieval_route == "structured"
        else "deep"
    )
    return Prediction(
        intent=plan.intent,
        route=route,
        canonicals=[*people, *congress],
        time=time,
        needs_clarification=plan.needs_clarification,
    )


def predict_with_llm(
    settings: Settings, case: QueryUnderstandingCase, fallback: Prediction
) -> Prediction:
    result = plan_question(
        settings,
        QuestionRequest(question=case.question, history=case.history),
    )
    plan = result.plan
    if result.status != "used" or plan is None:
        return fallback
    canonicals = [entity.canonical for entity in plan.entities]
    time = None
    if plan.start_year is not None and plan.end_year is not None:
        time = QueryTime(
            start=plan.start_year,
            end=plan.end_year,
            precision="year",
        )
    route: Route = (
        "clarify"
        if plan.needs_clarification
        else "fast_fact"
        if plan.retrieval_route == "structured"
        else "deep"
    )
    return Prediction(
        intent=plan.intent,
        route=route,
        canonicals=canonicals,
        time=time,
        needs_clarification=plan.needs_clarification,
    )


def _prf(tp: int, predicted: int, expected: int) -> dict[str, float | int]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": tp,
        "predicted": predicted,
        "expected": expected,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate(
    cases: list[QueryUnderstandingCase],
    predictions: dict[str, Prediction],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    intent_hits = 0
    family_hits = 0
    route_hits = 0
    tp = predicted_total = expected_total = 0
    time_exact = time_evaluable = 0
    clarification_tp = clarification_pred = clarification_expected = 0

    for case in cases:
        prediction = predictions[case.id]
        expected = {
            key
            for mention in case.mentions
            for name in mention.canonical
            for key in canonical_keys(name)
        }
        got = {
            key for name in prediction.canonicals for key in canonical_keys(name)
        }
        case_tp = len(expected & got)
        tp += case_tp
        predicted_total += len(got)
        expected_total += len(expected)
        intent_hit = prediction.intent == case.intent
        family_hit = intent_family(prediction.intent) == intent_family(case.intent)
        route_hit = prediction.route == case.route
        intent_hits += int(intent_hit)
        family_hits += int(family_hit)
        route_hits += int(route_hit)
        time_ok: bool | None = None
        if case.time is not None:
            time_evaluable += 1
            time_ok = (
                prediction.time is not None
                and prediction.time.start == case.time.start
                and prediction.time.end == case.time.end
            )
            time_exact += int(time_ok)
        clarification_pred += int(prediction.needs_clarification)
        clarification_expected += int(case.needs_clarification)
        clarification_tp += int(
            prediction.needs_clarification and case.needs_clarification
        )
        rows.append(
            {
                "id": case.id,
                "split": case.split,
                "intent": {
                    "expected": case.intent,
                    "predicted": prediction.intent,
                    "ok": intent_hit,
                    "family_ok": family_hit,
                },
                "route": {"expected": case.route, "predicted": prediction.route, "ok": route_hit},
                "mentions": {
                    "expected": sorted(expected),
                    "predicted": sorted(got),
                    "missing": sorted(expected - got),
                    "extra": sorted(got - expected),
                },
                "time": {
                    "expected": case.time.model_dump() if case.time else None,
                    "predicted": prediction.time.model_dump() if prediction.time else None,
                    "ok": time_ok,
                },
                "clarification": {
                    "expected": case.needs_clarification,
                    "predicted": prediction.needs_clarification,
                },
            }
        )

    total = len(cases)
    return {
        "cases": total,
        "intent_accuracy": intent_hits / total if total else 0.0,
        "intent_family_accuracy": family_hits / total if total else 0.0,
        "route_accuracy": route_hits / total if total else 0.0,
        "mention": _prf(tp, predicted_total, expected_total),
        "time": {
            "evaluable": time_evaluable,
            "exact_accuracy": time_exact / time_evaluable if time_evaluable else 0.0,
        },
        "clarification": {
            **_prf(clarification_tp, clarification_pred, clarification_expected),
            "predicted_positive": clarification_pred,
            "expected_positive": clarification_expected,
        },
        "rows": rows,
    }


def render_markdown(title: str, result: dict[str, Any]) -> str:
    mention = result["mention"]
    time = result["time"]
    clarification = result["clarification"]
    lines = [
        f"# {title}",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 题数 | {result['cases']} |",
        f"| 意图准确率（精确） | {result['intent_accuracy']:.1%} |",
        f"| 意图准确率（事实族合并） | {result['intent_family_accuracy']:.1%} |",
        f"| 路由准确率 | {result['route_accuracy']:.1%} |",
        f"| Mention Precision | {mention['precision']:.1%} |",
        f"| Mention Recall | {mention['recall']:.1%} |",
        f"| Mention F1 | {mention['f1']:.1%} |",
        f"| 时间精确匹配 | {time['exact_accuracy']:.1%}（{time['evaluable']} 题） |",
        f"| 澄清 Precision | {clarification['precision']:.1%} |",
        f"| 澄清 Recall | {clarification['recall']:.1%} |",
        "",
        "## 逐题",
        "",
        "| 题 | 意图 | 路由 | 缺失 mention | 多余 mention | 时间 |",
        "|---|---|---|---|---|---|",
    ]
    for row in result["rows"]:
        intent = row["intent"]
        route = row["route"]
        mentions = row["mentions"]
        time_row = row["time"]
        lines.append(
            "| `{}` | {}{} | {}{} | {} | {} | {} |".format(
                row["id"],
                intent["predicted"],
                "" if intent["ok"] else "（应为 " + intent["expected"] + "）",
                route["predicted"],
                "" if route["ok"] else "（应为 " + route["expected"] + "）",
                "、".join(mentions["missing"]) or "—",
                "、".join(mentions["extra"]) or "—",
                "—"
                if time_row["expected"] is None
                else (
                    "OK"
                    if time_row["ok"]
                    else f"{time_row['predicted']} / 应为 {time_row['expected']}"
                ),
            )
        )
    lines.append("")
    return "\n".join(lines)
