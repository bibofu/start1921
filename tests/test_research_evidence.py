from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from history_agent.answering.evidence import EvidenceRegistry
from history_agent.answering.full_text import read_source_evidence
from history_agent.answering.models import QuestionRequest, ResearchTask, TaskResult
from history_agent.answering.task_executor import HistoryTaskExecutor, _source_documents
from history_agent.config import Settings
from history_agent.retrieval.llamaindex import node_to_search_hit, search_hit_to_node
from history_agent.retrieval.models import SearchHit, SearchResponse
from llama_index.core.llms import ChatMessage, ChatResponse
from pydantic import SecretStr


def _hit() -> SearchHit:
    return SearchHit(
        rank=1,
        chunk_id="chunk-one",
        document_id="source_one",
        title="史料一",
        filename="史料一.pdf",
        source_type="chronology",
        verification_status="edition_labeled",
        pdf_page_start=12,
        pdf_page_end=13,
        section_path=["1943年"],
        text="1943年，周恩来参加会议。随后提出建议。",
        year_mentions=[1943],
        people=["周恩来"],
        extraction_methods=["text_layer"],
        score=0.8,
        matched_terms=["周恩来"],
        keyword_rank=1,
        vector_rank=2,
    )


def test_registry_reuses_ids_without_replacing_raw_text_or_page_range() -> None:
    registry = EvidenceRegistry()
    hit = _hit()
    first = registry.register_hit(hit, "first", "周恩来参加会议。")
    second = registry.register_hit(hit, "second", "随后提出建议。")
    third = registry.register_hit(hit.model_copy(update={"chunk_id": "chunk-two"}), "second")

    assert first.evidence_id == second.evidence_id == "E1"
    assert third.evidence_id == "E2"
    assert registry.raw_text("E1") == hit.text
    citation = registry.citations(["E1"])[0]
    assert citation.pdf_page == 12 and citation.pdf_page_end == 13
    assert "参加会议" in citation.quote and "提出建议" in citation.quote
    assert registry.nodes(["E1"])[0].node.metadata["task_ids"] == ["first", "second"]
    citation.quote = "caller mutation"
    assert registry.citations(["E1"])[0].quote != "caller mutation"


def test_node_roundtrip_retains_postprocessed_text_and_source_metadata() -> None:
    node = search_hit_to_node(_hit())
    node.node.text = "经上下文扩展后的完整原文。"
    node.node.metadata["pdf_page_end"] = 14
    node.node.metadata["section_path"] = ["新的来源章节"]
    node.score = 0.9

    hit = node_to_search_hit(node, rank=3)

    assert hit.text == "经上下文扩展后的完整原文。"
    assert hit.pdf_page_end == 14
    assert hit.section_path == ["新的来源章节"]
    assert hit.keyword_rank == 1 and hit.vector_rank == 2
    assert hit.rank == 3 and hit.score == 0.9


def test_source_constraint_keeps_requested_volume(work_path: Path) -> None:
    catalog = work_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": f"deng_{label}",
                        "filename": f"{volume}.pdf",
                        "title": f"邓小平年谱（1904—1974）{volume}",
                        "volume": volume,
                        "source_type": "chronology",
                        "verification_status": "edition_labeled",
                    }
                    for label, volume in [("upper", "上卷"), ("lower", "下卷")]
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, project_root=work_path, catalog_path=catalog)
    task = ResearchTask(
        task_id="lookup",
        tool="search",
        objective="查找指定卷册",
        query="只依据《邓小平年谱（1904—1974）》下卷查找有关记载",
        source_title="邓小平年谱（1904—1974）",
    )

    assert _source_documents(settings, task) == ["deng_lower"]
    assert (
        _source_documents(settings, task.model_copy(update={"document_ids": ["deng_upper"]})) == []
    )


def test_full_text_tool_preserves_body_without_generating_answer(work_path: Path) -> None:
    from test_full_text import _write_section

    settings = _write_section(work_path)
    result = read_source_evidence(settings, question="请读取《矛盾论》全文")
    assert result.status == "completed"
    assert len(result.items) == 1
    item = result.items[0]
    assert "第一页正文。\n\n第二页正文。" in item.raw_text
    assert "下一篇正文" not in item.raw_text
    assert item.citation.pdf_page == 185 and item.citation.pdf_page_end == 186
    assert result.content is not None and "[E1]" not in result.content


def test_full_text_task_uses_request_registry_citation_ids(work_path: Path) -> None:
    from test_full_text import _write_section

    settings = _write_section(work_path)
    registry = EvidenceRegistry()
    registry.register_hit(_hit(), "earlier_task")
    request = QuestionRequest(question="请读取《矛盾论》全文")
    task = ResearchTask(
        task_id="read",
        tool="read_source",
        objective="读取原文",
        query=request.question,
        source_title="矛盾论",
    )

    result = asyncio.run(HistoryTaskExecutor(settings, request, registry).execute(task))

    assert result.status == "completed"
    assert result.evidence_ids == ["E2"]
    assert result.content is not None and result.content.endswith("[E2]")
    assert "[E1]" not in result.content


def test_analysis_rejects_evidence_outside_its_dependencies(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def answer(*args: object, **kwargs: object) -> ChatResponse:
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=json.dumps(
                    {
                        "findings": [{"text": "材料支持这项判断", "evidence_ids": ["E2"]}],
                        "missing_aspects": [],
                    },
                    ensure_ascii=False,
                ),
            )
        )

    monkeypatch.setattr("history_agent.answering.task_executor.DeepSeekLlamaIndexLLM.achat", answer)
    registry = EvidenceRegistry()
    registry.register_hit(_hit(), "dependency")
    registry.register_hit(_hit().model_copy(update={"chunk_id": "unrelated"}), "other")
    settings = Settings(_env_file=None, project_root=work_path, llm_api_key=SecretStr("test-key"))
    request = QuestionRequest(question="比较这些材料")
    task = ResearchTask(
        task_id="analysis",
        tool="analyze",
        objective="比较材料",
        query=request.question,
        depends_on=["dependency"],
    )
    result = asyncio.run(
        HistoryTaskExecutor(settings, request, registry).execute(
            task,
            {
                "dependency": TaskResult(
                    task_id="dependency", tool="search", status="completed", evidence_ids=["E1"]
                )
            },
        )
    )

    assert result.status == "failed"
    assert result.error_code == "invalid_analysis"
    assert result.findings == []


def test_analysis_reads_original_evidence_beyond_display_excerpt(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[str] = []

    async def answer(*args: object, **kwargs: object) -> ChatResponse:
        payload = kwargs["request_payload"]
        received.append(str(payload))
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=json.dumps(
                    {
                        "findings": [{"text": "文末另有补充决定。", "evidence_ids": ["E1"]}],
                        "missing_aspects": [],
                    },
                    ensure_ascii=False,
                ),
            )
        )

    monkeypatch.setattr("history_agent.answering.task_executor.DeepSeekLlamaIndexLLM.achat", answer)
    registry = EvidenceRegistry()
    raw = "会议记录正文。" * 100 + "文末补充决定涉及会后的执行安排。"
    registry.register_hit(_hit().model_copy(update={"text": raw}), "dependency", "会议记录正文。")
    settings = Settings(_env_file=None, project_root=work_path, llm_api_key=SecretStr("test-key"))
    task = ResearchTask(
        task_id="analysis",
        tool="analyze",
        objective="比较材料",
        query="材料的结尾提供哪些补充？",
        depends_on=["dependency"],
    )

    result = asyncio.run(
        HistoryTaskExecutor(settings, QuestionRequest(question=task.query), registry).execute(
            task,
            {
                "dependency": TaskResult(
                    task_id="dependency",
                    tool="read_source",
                    status="completed",
                    evidence_ids=["E1"],
                )
            },
        )
    )

    assert result.status == "completed"
    assert "文末补充决定涉及会后的执行安排。" in received[0]
    assert "PDF第12—13页" in received[0]
    assert result.findings == ["文末另有补充决定。 [E1]"]


@pytest.mark.parametrize("error_type", [ValueError, TypeError, KeyError, IndexError])
def test_analysis_malformed_provider_response_retains_evidence(
    work_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    async def malformed_response(*args: object, **kwargs: object) -> ChatResponse:
        raise error_type("malformed provider payload")

    monkeypatch.setattr(
        "history_agent.answering.task_executor.DeepSeekLlamaIndexLLM.achat", malformed_response
    )
    registry = EvidenceRegistry()
    registry.register_hit(_hit(), "dependency")
    settings = Settings(_env_file=None, project_root=work_path, llm_api_key=SecretStr("test-key"))
    task = ResearchTask(
        task_id="analysis",
        tool="analyze",
        objective="比较材料",
        query="比较这些材料",
        depends_on=["dependency"],
    )

    result = asyncio.run(
        HistoryTaskExecutor(settings, QuestionRequest(question=task.query), registry).execute(
            task,
            {
                "dependency": TaskResult(
                    task_id="dependency", tool="search", status="completed", evidence_ids=["E1"]
                )
            },
        )
    )

    assert result.status == "failed"
    assert result.error_code == "invalid_analysis"
    assert result.evidence_ids == ["E1"]
    assert result.findings == []
    assert result.missing_aspects == ["比较材料"]


@pytest.mark.parametrize("keyword_failed,expected", [(False, "empty"), (True, "completed")])
def test_search_preserves_keyword_support_gate(
    work_path: Path, monkeypatch: pytest.MonkeyPatch, keyword_failed: bool, expected: str
) -> None:
    hit = _hit().model_copy(update={"keyword_rank": None, "vector_rank": 1})
    response = SearchResponse(
        query="会议有哪些记载",
        query_intent="general",
        query_terms=["会议"],
        query_years=[],
        query_year_range=[],
        query_people=[],
        document_filters=[],
        include_out_of_scope=False,
        hits=[hit],
        degraded_components=["keyword"] if keyword_failed else [],
    )
    monkeypatch.setattr(
        "history_agent.answering.task_executor.search_hybrid_index", lambda **kwargs: response
    )
    monkeypatch.setattr(
        "history_agent.answering.query_understanding.load_person_aliases", lambda path: {}
    )
    settings = Settings(_env_file=None, project_root=work_path, llm_api_key=None)
    registry = EvidenceRegistry()
    executor = HistoryTaskExecutor(settings, QuestionRequest(question=response.query), registry)
    task = ResearchTask(
        task_id="search", tool="search", objective="查找会议材料", query=response.query
    )

    result = asyncio.run(executor.execute(task))

    assert result.status == expected
    assert bool(result.evidence_ids) == keyword_failed
    assert len(registry) == int(keyword_failed)


def test_search_registers_actual_returned_nodes(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hit = _hit()
    response = SearchResponse(
        query="会议有哪些记载",
        query_intent="general",
        query_terms=["会议"],
        query_years=[],
        query_year_range=[],
        query_people=[],
        document_filters=[],
        include_out_of_scope=False,
        hits=[hit],
    )

    async def retrieve(retriever: object, bundle: object) -> list[object]:
        retriever.last_response = response
        node = search_hit_to_node(hit)
        node.node.text = "完整会议原文及紧邻的补充说明。"
        node.node.metadata["pdf_page_end"] = 14
        node.node.metadata["context_origin"] = "adjacent_source"
        return [node]

    monkeypatch.setattr(
        "history_agent.answering.task_executor.HistoryHybridRetriever.aretrieve", retrieve
    )
    monkeypatch.setattr(
        "history_agent.answering.query_understanding.load_person_aliases", lambda path: {}
    )
    registry = EvidenceRegistry()
    settings = Settings(_env_file=None, project_root=work_path, llm_api_key=None)
    task = ResearchTask(
        task_id="search", tool="search", objective="查找会议材料", query=response.query
    )
    result = asyncio.run(
        HistoryTaskExecutor(settings, QuestionRequest(question=response.query), registry).execute(
            task
        )
    )

    assert result.status == "completed"
    assert registry.raw_text("E1") == "完整会议原文及紧邻的补充说明。"
    assert registry.citations()[0].pdf_page_end == 14
    assert registry.nodes()[0].node.metadata["context_origin"] == "adjacent_source"
