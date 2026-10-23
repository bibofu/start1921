"""Evidence tools used by the single research workflow.

Tools collect or analyze evidence. They never route, replan, retry, or deliver a
final answer; those decisions belong to the request workflow.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence

import httpx
from llama_index.core import QueryBundle
from llama_index.core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from history_agent.answering.evidence import (
    EvidenceCollection,
    EvidenceRegistry,
    quote_for_hit,
    unsupported_leading_entity,
)
from history_agent.answering.full_text import _section_candidates, read_source_evidence
from history_agent.answering.llamaindex_llm import (
    DeepSeekLlamaIndexLLM,
    chat_messages,
    response_usage,
)
from history_agent.answering.models import (
    QueryEntity,
    QueryPlan,
    QuestionRequest,
    ResearchTask,
    TaskResult,
)
from history_agent.answering.query_understanding import query_execution
from history_agent.answering.runtime import LLMRuntime, RequestBudget
from history_agent.answering.structured import collect_structured_evidence
from history_agent.answering.timeline_evidence import filter_person_timeline_evidence
from history_agent.config import Settings
from history_agent.corpus.catalog import load_catalog
from history_agent.errors import CatalogError, RetrievalError, llm_http_error_code
from history_agent.retrieval.hybrid import search_hybrid_index
from history_agent.retrieval.keyword import infer_query_intent
from history_agent.retrieval.llamaindex import (
    HistoryEvidencePostprocessor,
    HistoryHybridRetriever,
    node_to_search_hit,
)
from history_agent.retrieval.models import RetrievalPlan


class _Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1600)
    evidence_ids: list[str] = Field(min_length=1, max_length=36)


class _Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[_Finding] = Field(default_factory=list, max_length=16)
    missing_aspects: list[str] = Field(default_factory=list, max_length=12)


ANALYSIS_PARSER = PydanticOutputParser(_Analysis)


def search_kwargs(settings: Settings, retrieval_plan: RetrievalPlan | None) -> dict[str, object]:
    return {
        "keyword_index_path": settings.keyword_index_target,
        "vector_index_path": settings.vector_index_target,
        "model_cache_dir": settings.model_cache_dir / "fastembed",
        "aliases_path": settings.person_aliases_path,
        "plan": retrieval_plan,
    }


def _title_key(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", value).casefold()


def _source_documents(settings: Settings, task: ResearchTask) -> list[str] | None:
    if not task.source_title:
        return list(task.document_ids) or None
    catalog = load_catalog(settings.catalog_path)
    expected = _title_key(task.source_title)
    matches = [
        document
        for document in catalog.documents
        if document.enabled and expected in _title_key(document.title)
    ]
    volume_match = re.search(
        r"(?:》\s*|(?<![\u3400-\u9fff]))(?P<volume>[上中下]卷|第[一二三四五六七八九十0-9]+卷)",
        task.query,
    )
    if volume_match:
        volume = _title_key(volume_match.group("volume"))
        matches = [
            document
            for document in matches
            if volume in _title_key(document.volume or "") or volume in _title_key(document.title)
        ]
    ids = [document.document_id for document in matches]
    if not matches:
        # A quoted name may identify a section within a volume.
        ids = [
            entry.document_id
            for entry in _section_candidates(settings.structure_dir, task.source_title)
        ]
    if task.document_ids:
        ids = [item for item in ids if item in task.document_ids]
    return list(dict.fromkeys(ids))


class HistoryTaskExecutor:
    def __init__(
        self,
        settings: Settings,
        request: QuestionRequest,
        registry: EvidenceRegistry,
        runtime: LLMRuntime | None = None,
        budget: RequestBudget | None = None,
        interpretation: QueryPlan | None = None,
    ) -> None:
        self.settings = settings
        self.request = request
        self.registry = registry
        self.runtime = runtime
        self.budget = budget
        self.interpretation = interpretation

    async def execute(
        self,
        task: ResearchTask,
        prior_results: Mapping[str, TaskResult] | Sequence[TaskResult] = (),
    ) -> TaskResult:
        if self.budget is not None:
            self.budget.timeout(self.settings.request_timeout_seconds)
        results = (
            dict(prior_results)
            if isinstance(prior_results, Mapping)
            else {result.task_id: result for result in prior_results}
        )
        if any(dependency not in results for dependency in task.depends_on):
            return self._result(
                task, "skipped", error_code="missing_dependency", missing_aspects=[task.objective]
            )
        try:
            if task.tool == "analyze":
                return await self._analyze(task, results)
            if task.tool == "read_source":
                collection = await asyncio.to_thread(
                    read_source_evidence,
                    self.settings,
                    question=task.query,
                    title=task.source_title,
                    document_ids=task.document_ids or None,
                )
                return self._register_collection(task, collection)
            document_ids = await asyncio.to_thread(_source_documents, self.settings, task)
            if document_ids == []:
                return self._result(
                    task,
                    "empty",
                    error_code="source_not_found",
                    missing_aspects=[task.objective],
                    limitations=[
                        f"本地目录未找到指定来源《{task.source_title}》，未放宽到其他文献。"
                    ],
                )
            if task.tool in {"timeline", "intersection"}:
                collection = await asyncio.to_thread(
                    collect_structured_evidence,
                    self.settings,
                    question=task.query,
                    intent=task.tool,
                    person_names=task.person_names,
                    start_year=task.start_year,
                    end_year=task.end_year,
                    top_k=self.request.top_k,
                )
                if document_ids is not None:
                    collection.items = [
                        item
                        for item in collection.items
                        if item.citation.document_id in document_ids
                    ]
                    if collection.status == "completed" and not collection.items:
                        collection.status = "empty"
                    collection.content = None
                    collection.limitations.append(
                        "结构化记录已按指定来源筛选，采样结果不代表该来源的完整记录。"
                    )
                return self._register_collection(task, collection)
            return await self._search(task, document_ids)
        except (RetrievalError, CatalogError) as exc:
            return self._result(
                task,
                "unavailable",
                error_code=type(exc).__name__,
                missing_aspects=[task.objective],
                limitations=["取证工具暂不可用；不能将工具失败解释为史实不存在。"],
            )
        except httpx.HTTPError as exc:
            return self._result(
                task,
                "unavailable",
                error_code=llm_http_error_code(exc),
                missing_aspects=[task.objective],
            )

    @staticmethod
    def _result(task: ResearchTask, status: str, **kwargs: object) -> TaskResult:
        return TaskResult.model_validate(
            {"task_id": task.task_id, "tool": task.tool, "status": status, **kwargs}
        )

    def _register_collection(
        self, task: ResearchTask, collection: EvidenceCollection
    ) -> TaskResult:
        ids: list[str] = []
        findings: list[str] = []
        for item in collection.items:
            citation = self.registry.register_citation(
                item.citation, task.task_id, item.source_key, item.raw_text
            )
            if citation.evidence_id not in ids:
                ids.append(citation.evidence_id)
            if item.finding:
                findings.append(f"{item.finding} [{citation.evidence_id}]")
        content = collection.content
        if content and ids:
            if task.tool == "read_source":
                content += "\n\n" + " ".join(f"[{item}]" for item in ids)
            elif findings:
                content += "\n\n" + "\n".join(f"- {item}" for item in findings)
        return self._result(
            task,
            collection.status,
            evidence_ids=ids,
            findings=findings,
            missing_aspects=[] if ids else [task.objective],
            limitations=collection.limitations,
            content=content,
            error_code=collection.error_code,
        )

    async def _search(self, task: ResearchTask, document_ids: list[str] | None) -> TaskResult:
        base = self.interpretation or QueryPlan.model_validate(
            {"intent": infer_query_intent(task.query), "normalized_question": self.request.question}
        )
        task_plan = base.model_copy(
            update={
                "normalized_question": task.query[:500],
                "search_queries": base.search_queries
                if task.query == self.request.question
                else [],
                "start_year": task.start_year,
                "end_year": task.end_year,
                "coverage": task.coverage,
                "entities": [
                    QueryEntity(type="person", text=name, canonical=name)
                    for name in task.person_names
                ]
                or base.entities,
            }
        )
        execution = query_execution(task.query, task_plan, self.settings.person_aliases_path)
        limit = self.request.top_k
        if task.coverage == "balanced_period":
            limit = max(limit, 24)
        elif task.coverage != "relevance":
            limit = max(limit, len(execution.additional_queries) * 3)
        limit = min(limit, 36)
        capture = bool(getattr(self.runtime, "capture_retrieval_trace", False))
        retriever = HistoryHybridRetriever(
            search_backend=search_hybrid_index,
            search_kwargs={
                **search_kwargs(self.settings, execution.retrieval_plan),
                "document_ids": document_ids,
                "top_k": limit,
                "capture_trace": capture,
            },
            additional_queries=list(execution.additional_queries),
            callback_manager=getattr(self.runtime, "callback_manager", None),
        )
        bundle = QueryBundle(query_str=execution.primary_query)
        nodes = await retriever.aretrieve(bundle)
        nodes = await HistoryEvidencePostprocessor(
            max_nodes=limit, callback_manager=retriever.callback_manager
        ).apostprocess_nodes(nodes, query_bundle=bundle)
        retrieval = retriever.last_response
        if retrieval is None:
            raise RetrievalError("Retriever returned no response")
        # Domain selection consumes SearchHit only at its boundary. Returned
        # framework nodes remain the authoritative source for the registry.
        retrieval = retrieval.model_copy(
            update={
                "hits": [node_to_search_hit(node, rank) for rank, node in enumerate(nodes, start=1)]
            }
        )
        nodes_by_id = {node.node.node_id: node for node in nodes}
        observer = getattr(self.runtime, "record_retrieval", None)
        if capture and callable(observer):
            observer("retrieval_round", retrieval)
        original = retrieval
        if task.source_title:
            expected_source = _title_key(task.source_title)
            retrieval = retrieval.model_copy(
                update={
                    "hits": [
                        hit
                        for hit in retrieval.hits
                        if expected_source in _title_key(hit.title)
                        or any(expected_source == _title_key(part) for part in hit.section_path)
                    ]
                }
            )
        filtered = await asyncio.to_thread(
            filter_person_timeline_evidence,
            self.settings,
            task.query,
            retrieval,
            self.runtime,
            self.budget,
        )
        retrieval = filtered.retrieval.model_copy(update={"rag_framework": "llamaindex"})
        if capture and callable(observer):
            observer("after_timeline_filter", retrieval)
        limitations: list[str] = []
        if filtered.status == "applied":
            limitations.append(f"已核对人物动作主体，剔除 {filtered.removed_count} 条候选。")
        elif filtered.status == "fallback":
            limitations.append("人物活动主体审查暂未完成，不能把仅被提及的材料直接视为本人经历。")
        if retrieval.degraded_components:
            limitations.append("部分检索组件不可用：" + "、".join(retrieval.degraded_components))
        if retrieval.query_intent == "intersection":
            limitations.append("人名共现只是线索，不能据此断言共同参与或互动。")
            if retrieval.query_year_range and not retrieval.query_years:
                start_year, end_year = retrieval.query_year_range
                limitations.append(
                    f"时间条件按 {start_year}—{end_year} 年范围召回资料；"
                    "这不是精确起止日期，具体活动的时期归属须结合原文核对。"
                )
        unsupported = unsupported_leading_entity(task.query, original.hits)
        keyword_available = "keyword" not in retrieval.degraded_components
        eligible = (
            bool(retrieval.hits)
            and not unsupported
            and (
                not keyword_available or any(hit.keyword_rank is not None for hit in retrieval.hits)
            )
        )
        if not eligible:
            limitations.append(
                f"检索片段中没有出现问题人物“{unsupported}”。"
                if unsupported
                else "当前候选缺少可用的关键词支持或直接证据，未用向量相似性代替证据。"
            )
        ids: list[str] = []
        if eligible:
            for hit in retrieval.hits:
                citation = self.registry.register_node(
                    nodes_by_id[hit.chunk_id],
                    task.task_id,
                    quote_for_hit(hit, retrieval.query_terms, query_people=retrieval.query_people),
                )
                if citation.evidence_id not in ids:
                    ids.append(citation.evidence_id)
        missing = list(retrieval.coverage_gaps)
        if not ids:
            missing = list(dict.fromkeys([*missing, task.objective]))
        return self._result(
            task,
            "completed" if ids else "empty",
            evidence_ids=ids,
            missing_aspects=missing,
            limitations=limitations,
            retrieval=retrieval,
            usage=filtered.usage,
            error_code=filtered.error_code,
        )

    async def _analyze(self, task: ResearchTask, results: dict[str, TaskResult]) -> TaskResult:
        ids = list(
            dict.fromkeys(
                evidence_id
                for dependency in task.depends_on
                for evidence_id in results[dependency].evidence_ids
                if self.registry.contains(evidence_id)
            )
        )
        if not ids:
            return self._result(
                task, "empty", error_code="no_dependency_evidence", missing_aspects=[task.objective]
            )
        if not self.settings.llm_enabled:
            return self._result(
                task,
                "unavailable",
                evidence_ids=ids,
                error_code="analysis_llm_disabled",
                missing_aspects=[task.objective],
                limitations=["分析模型未启用，仅保留已检索到的原文证据。"],
            )
        evidence = "\n\n".join(
            f"[{item.evidence_id}] 《{item.document}》"
            f"PDF第{item.pdf_page}—{item.pdf_page_end or item.pdf_page}页："
            f"{self.registry.raw_text(item.evidence_id)}"
            for item in self.registry.citations(ids)
        )
        instructions = (
            "你是历史研究证据分析器。仅分析给定证据，不使用模型记忆，不调用检索，不生成最终回答。"
            "区分原文观点、后人叙述、时间差异与真正冲突；共现不证明交集，索引日期不等于事件已核实。"
            "每条finding必须用evidence_ids列出实际支持它的原始编号；缺证据的要求放missing_aspects。"
        )
        payload: dict[str, object] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": ANALYSIS_PARSER.format(instructions)},
                {
                    "role": "user",
                    "content": (
                        f"任务：{task.objective}\n要求：{task.required_aspects}\n证据：\n{evidence}"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "max_tokens": min(2200, self.settings.llm_max_tokens),
        }
        usage: dict[str, int] | None = None
        try:
            response = await DeepSeekLlamaIndexLLM(
                settings=self.settings, runtime=self.runtime, budget=self.budget
            ).achat(chat_messages(payload), request_payload=payload)
            usage = response_usage(response)
            if response.additional_kwargs.get("finish_reason") == "length":
                raise ValueError("truncated analysis")
            analysis = ANALYSIS_PARSER.parse(response.message.content or "")
            allowed = set(ids)
            if any(not set(item.evidence_ids) <= allowed for item in analysis.findings):
                raise ValueError("analysis invented evidence IDs")
            if any(
                not set(re.findall(r"\[(E[1-9]\d*)\]", item.text)) <= allowed
                for item in analysis.findings
            ):
                raise ValueError("analysis invented inline evidence IDs")
        except (ValueError, TypeError, KeyError, IndexError, ValidationError):
            return self._result(
                task,
                "failed",
                evidence_ids=ids,
                error_code="invalid_analysis",
                missing_aspects=[task.objective],
                usage=usage,
            )
        findings = [
            item.text
            + " "
            + " ".join(f"[{evidence_id}]" for evidence_id in dict.fromkeys(item.evidence_ids))
            for item in analysis.findings
        ]
        return self._result(
            task,
            "completed" if findings else "empty",
            evidence_ids=ids,
            findings=findings,
            missing_aspects=analysis.missing_aspects or ([] if findings else [task.objective]),
            usage=usage,
        )
