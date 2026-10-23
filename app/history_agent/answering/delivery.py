"""Project answer policy applied once, after the research workflow terminates."""

from __future__ import annotations

from typing import Literal

from history_agent.answering.models import (
    AnswerResponse,
    Citation,
    ExecutionSummary,
    QuestionRequest,
    TaskResult,
)
from history_agent.answering.query_understanding import QueryPlanningResult
from history_agent.answering.synthesis import (
    LLMResult,
    _citations_used_by_answer,
    _extractive_answer,
)
from history_agent.config import Settings


def deliver_answer(
    settings: Settings,
    request: QuestionRequest,
    planning: QueryPlanningResult,
    summary: ExecutionSummary,
    citations: list[Citation],
    result: LLMResult,
    *,
    unresolved: list[TaskResult],
) -> AnswerResponse:
    plan = summary.plan
    interpretation = plan.interpretation
    tasks = summary.task_results
    limitations = list(dict.fromkeys(note for task in tasks for note in task.limitations))
    missing = list(dict.fromkeys(aspect for task in unresolved for aspect in task.missing_aspects))
    retrievals = [task.retrieval for task in tasks if task.retrieval is not None]
    intent: str = interpretation.intent
    if intent == "general" and retrievals:
        intent = retrievals[0].query_intent
    raw_delivery = len(plan.tasks) == 1 and plan.tasks[0].tool == "read_source"
    terminal_content = next(
        (task.content for task in tasks if task.status == "ambiguous" and task.content), None
    )
    llm_used = bool(result.answer) and not raw_delivery
    if summary.stopped_reason == "out_of_scope":
        answer = (
            "这个问题超出本地知识库的史料范围，暂不回答。当前库只收录"
            f"{settings.research_start.year}—{settings.research_end.year}年中国近现代史相关史料。"
        )
        retrieval_mode = "out_of_scope"
    elif summary.stopped_reason == "clarification":
        answer = (
            terminal_content
            or interpretation.clarification_question
            or "请明确要查询的文献或人物。"
        )
        retrieval_mode = "query_clarification"
    elif raw_delivery:
        answer = next((task.content for task in tasks if task.content), None) or (
            "未找到可以完整交付的篇目原文。"
        )
        retrieval_mode = "full_text"
    else:
        structured_content = [
            task.content
            for task in tasks
            if task.content and task.tool in {"timeline", "intersection"}
        ]
        answer = result.answer or (
            "\n\n".join(structured_content)
            if structured_content and not any(task.tool == "search" for task in tasks)
            else _extractive_answer(intent, citations)
        )
        tool_kinds = {
            task.tool for task in tasks if task.tool != "analyze" and task.status != "skipped"
        }
        retrieval_mode = (
            "structured_" + next(iter(tool_kinds))
            if len(tool_kinds) == 1 and tool_kinds <= {"timeline", "intersection"}
            else retrievals[0].retrieval_mode
            if len(retrievals) == 1
            else "research_hybrid"
            if retrievals
            else "research"
        )
    used = _citations_used_by_answer(answer, citations)
    if raw_delivery and not used and citations:
        # A complete source is an extractive artifact, never silently shortened
        # to Top-K. Attach its original page references if the source has no markers.
        answer += "\n\n" + " ".join(f"[{citation.evidence_id}]" for citation in citations)
        used = list(citations)
    if summary.stopped_reason == "budget_exhausted":
        limitations.append("本次研究已达到执行预算，未完成部分不视为已核实。")
    if missing:
        limitations.append("尚缺证据：" + "；".join(missing))
    if (
        unresolved
        and not missing
        and summary.stopped_reason not in {"clarification", "out_of_scope"}
    ):
        limitations.append("部分研究任务尚未取得充分材料，当前结果不能视为完整结论。")
    if citations and not settings.llm_enabled and not raw_delivery:
        limitations.append("当前未配置生成模型，返回证据摘录式答案。")
    elif citations and not result.answer and not raw_delivery:
        limitations.append(
            f"生成回答未通过（{result.error_code or 'unavailable'}），已返回证据摘录。"
        )
    elif result.error_code == "removed_uncited_claims":
        limitations.append("生成草稿中的未引用段落已移除，其余内容已通过引用核查。")
    elif result.error_code == "hierarchical_partial_map_fallback":
        limitations.append("部分证据分组未生成局部摘要，最终综合时已使用该组原文。")
    if planning.status == "fallback":
        limitations.append(f"查询规划未通过（{planning.error_code}），使用保守计划处理原问题。")
    degraded = sorted(
        {component for retrieval in retrievals for component in retrieval.degraded_components}
    )
    if degraded:
        limitations.append("检索已降级：" + "、".join(degraded) + " 分支暂不可用。")
    if used:
        limitations.append("答案仅代表当前已入库文献，不等同于完整历史结论。")
    evidence_status: Literal["supported", "partial", "no_evidence"] = (
        "no_evidence" if not used else "partial"
    )
    if (
        used
        and not unresolved
        and not degraded
        and summary.stopped_reason == "completed"
        and intent != "intersection"
        and not any(task.tool in {"timeline", "intersection"} for task in tasks)
        and (
            raw_delivery
            or any(
                hit.keyword_rank is not None and hit.vector_rank is not None
                for retrieval in retrievals
                for hit in retrieval.hits[:5]
            )
        )
    ):
        evidence_status = "supported"
    return AnswerResponse(
        question=request.question,
        answer=answer,
        evidence_status=evidence_status,
        generator_mode="llm" if llm_used else "extractive",
        llm_status=(
            "not_applicable"
            if raw_delivery or not used
            else "disabled"
            if not settings.llm_enabled
            else "used"
            if llm_used
            else "fallback"
        ),
        model_name=settings.llm_model if settings.llm_enabled else None,
        llm_usage=result.usage,
        llm_error_code=result.error_code,
        uncited_claims=list(result.uncited_claims),
        query_plan=interpretation,
        research_plan=plan,
        execution_summary=summary,
        query_planner_status=planning.status,
        query_planner_model=planning.model_name,
        query_planner_usage=planning.usage,
        query_planner_error_code=planning.error_code,
        retrieval_mode=retrieval_mode,
        query_intent=intent,
        # Legacy display fields are a projection of research revisions, never an
        # alternative executor. Full counts and gaps are in execution_summary.
        retrieval_reflection_status="retried" if summary.replan_count else "skipped",
        retrieval_rounds=summary.replan_count + 1,
        retrieval_missing_aspects=missing[:4],
        retrieval_reflection_usage=summary.usage_by_stage.get("assessment"),
        citations=used,
        retrieved_evidence_count=len(citations),
        limitations=list(dict.fromkeys(limitations)),
        rag_framework="llamaindex",
    )
