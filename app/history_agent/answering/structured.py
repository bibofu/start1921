"""Evidence collectors for auditable structured historical records."""

from __future__ import annotations

import re

from history_agent.answering.evidence import CollectedEvidence, EvidenceCollection
from history_agent.answering.models import Citation
from history_agent.config import Settings
from history_agent.db import Database
from history_agent.db_backend import DATABASE_ERRORS
from history_agent.errors import ResearchDataError
from history_agent.research.intersections import get_person_intersections
from history_agent.research.people import resolve_person
from history_agent.research.timeline import TimelineEvidence, get_person_timeline

_RAW_TIMELINE = re.compile(r"列出|时间线|逐条|原文|明细|记录|清单|参加[过了]哪些会议")
MAX_STRUCTURED_SUMMARY_RECORDS = 36


def _citation(
    evidence: TimelineEvidence,
    number: int,
    quote: str,
    *,
    section: list[str] | None = None,
    event_date: str | None = None,
) -> Citation:
    year_match = re.match(r"(?P<year>(?:18|19|20)\d{2})", event_date or "")
    year_mentions = [int(year_match["year"])] if year_match is not None else []
    return Citation(
        evidence_id=f"E{number}",
        document_id=evidence.document_id,
        document=evidence.document_title,
        volume=evidence.volume,
        pdf_page=evidence.pdf_page_start,
        pdf_page_end=evidence.pdf_page_end,
        section=section or [],
        quote=quote,
        source_type=evidence.source_type,
        verification_status=evidence.verification_status,
        extraction_methods=evidence.extraction_methods,
        year_mentions=year_mentions,
        event_date=event_date,
    )


def _structured_result_limit(top_k: int, start: int, end: int) -> int:
    span = end - start + 1
    return min(MAX_STRUCTURED_SUMMARY_RECORDS, max(top_k, span * 3))


def collect_structured_evidence(
    settings: Settings,
    *,
    question: str,
    intent: str,
    person_names: list[str],
    start_year: int | None,
    end_year: int | None,
    top_k: int = 12,
) -> EvidenceCollection:
    """Collect audited records without deciding routing, retries or final answers."""
    if intent not in {"timeline", "intersection"}:
        return EvidenceCollection("not_applicable", error_code="unsupported_structured_tool")
    lower, upper = settings.research_start.year, settings.research_end.year
    start, end = start_year, end_year
    if start is None or end is None:
        return EvidenceCollection("not_applicable", error_code="missing_time_bounds")
    if not lower <= start <= end <= upper:
        return EvidenceCollection(
            "not_applicable",
            error_code="invalid_time_bounds",
            content=f"研究范围为 {lower}—{upper} 年，请提供范围内且起止顺序正确的年份。",
        )
    expected_count = 2 if intent == "intersection" else 1
    if len(person_names) != expected_count:
        return EvidenceCollection("not_applicable", error_code="invalid_person_count")
    database = Database(settings.database_target)
    try:
        with database.connect() as connection:
            forms = {
                str(row[0])
                for row in connection.execute(
                    "SELECT canonical_name FROM persons UNION "
                    "SELECT alias_text FROM person_aliases WHERE is_active=1"
                ).fetchall()
                if len(str(row[0])) >= 2
            }
        if not forms:
            return EvidenceCollection(
                "unavailable",
                error_code="person_catalog_unavailable",
                content="人物主数据尚未就绪，请先初始化研究库。",
            )
        person_ids: list[str] = []
        for name in person_names:
            resolution = resolve_person(database, name)
            if resolution.status != "resolved":
                return EvidenceCollection(
                    "ambiguous",
                    error_code="person_not_resolved",
                    content=f"无法唯一确定人物“{name}”，请补充人物信息。",
                )
            person = resolution.candidates[0]
            person_ids.append(person.merged_into_person_id or person.person_id)
        if len(set(person_ids)) != expected_count:
            return EvidenceCollection(
                "ambiguous",
                error_code="same_person_aliases",
                content="交集查询需要两位不同人物；两个称呼可能是同一人的别名。",
            )
        items: list[CollectedEvidence] = []
        normalized = re.sub(r"\s+", "", question).rstrip("？?。！!")
        event_types = ["meeting"] if "会议" in normalized else None
        result_limit = _structured_result_limit(top_k, start, end)
        if intent == "intersection":
            intersections = get_person_intersections(
                database,
                person_id=person_ids[0],
                other_person_id=person_ids[1],
                start_year=start,
                end_year=end,
                event_types=event_types,
                limit=result_limit,
            )
            for item in intersections.events:
                proof = item.joint_evidence[0]
                evidence = next(
                    e for e in item.event.evidence if e.evidence_id == proof.evidence_id
                )
                raw = proof.supporting_text
                quote = raw[:420] + ("……" if len(raw) > 420 else "")
                citation = _citation(
                    evidence,
                    len(items) + 1,
                    quote,
                    event_date=item.event.start.value,
                )
                roles = "、".join(
                    f"{name}：{proof.roles[pid]}"
                    for name, pid in (
                        (intersections.canonical_name, person_ids[0]),
                        (intersections.other_canonical_name, person_ids[1]),
                    )
                )
                finding = (
                    f"记录日期 {item.event.start.value or '不明确'}"
                    f"（{item.event.start.certainty}）；"
                    f"{roles}；待复核。原文：{quote}"
                )
                items.append(
                    CollectedEvidence(citation, f"structured:{evidence.evidence_id}", raw, finding)
                )
            limitations = [
                intersections.limitation,
                "角色和日期来自规则/索引，尚未逐条核实；同一史实可能保留多条来源候选。",
            ]
            total = intersections.total
            content = (
                (
                    f"当前规则找到 {total} 条交集候选，按时间展示前 {len(items)} 条；"
                    "不是完整或已确认的交集清单。"
                )
                if items
                else (
                    "当前规则未找到可展示的共同动作候选；这不代表两人没有交集，复杂句式仍可能漏检。"
                )
            )
        else:
            summarize = _RAW_TIMELINE.search(normalized) is None
            timeline = get_person_timeline(
                database,
                person_id=person_ids[0],
                start_year=start,
                end_year=end,
                event_types=event_types,
                limit=result_limit if summarize else top_k,
                sample_across_range=summarize,
                subject_only=True,
            )
            for event in timeline.events:
                evidence = event.evidence[0]
                raw = evidence.quote
                quote = raw[:420] + ("……" if len(raw) > 420 else "")
                citation = _citation(
                    evidence,
                    len(items) + 1,
                    quote,
                    section=[f"结构化索引日期：{event.start.value or '不明确'}"],
                    event_date=event.start.value,
                )
                finding = (
                    f"记录日期 {event.start.value or '不明确'}（{event.start.certainty}）；"
                    f"记录复核状态：{event.review_status}。原文：{quote}"
                )
                items.append(
                    CollectedEvidence(citation, f"structured:{evidence.evidence_id}", raw, finding)
                )
            limitations = [
                "时间线只纳入目标人物被标记为年谱主体的记录；动作归属仍须结合原文核对。",
                (
                    "记录按月份/时段抽样并优先采用较高复核状态，不等同于重要性排名；"
                    "日期为索引字段，须结合原文精度和来源差异核对。"
                    if summarize
                    else "按时间展示而非重要性排序；日期为索引字段，须结合原文精度和来源差异核对。"
                ),
            ]
            if not items:
                limitations.append("未找到目标人物的年谱主体记录，不能据此断言该时期没有活动。")
            total = timeline.total
            content = (
                f"找到 {total} 条与{timeline.canonical_name}相关的事件记录，"
                + (
                    f"从所问时段抽取 {len(items)} 条代表性记录供综合，不是完整经历结论。"
                    if summarize
                    else f"按时间展示前 {len(items)} 条，不是完整经历结论。"
                )
                if items
                else "当前结构化研究库未找到符合条件的记录，不能据此断言该时期没有活动。"
            )
        return EvidenceCollection(
            "completed" if items else "empty",
            items=items,
            limitations=limitations,
            content=content,
            total=total,
        )
    except (ResearchDataError, *DATABASE_ERRORS):
        return EvidenceCollection(
            "unavailable",
            error_code="structured_lookup_unavailable",
            content="结构化研究查询暂不可用，请检查研究库初始化状态；本次没有用人名共现结果替代回答。",
        )
