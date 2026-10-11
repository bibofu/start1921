import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from history_agent.answering.models import Citation, QuestionRequest
from history_agent.answering.runtime import LLMRuntime
from history_agent.answering.service import _llm_request_payload, _repair_request_payload
from history_agent.config import Settings
from history_agent.evaluation.pilot import compare, generation_contexts, validate_anchors
from history_agent.evaluation.pilot_models import (
    HumanReview,
    PilotCase,
    PilotDataset,
    PilotJudgment,
)
from history_agent.evaluation.pilot_runtime import RecordedLLMRuntime
from history_agent.extraction.text import build_page_record
from pydantic import ValidationError

PDF_HASH = "a" * 64


def _settings(root: Path) -> Settings:
    return Settings(_env_file=None, project_root=root, data_dir=root / "data", llm_api_key=None)


def _case() -> dict[str, Any]:
    return {
        "id": "p1",
        "question": "他担任什么职务？",
        "category": "fact",
        "answerability": "answerable",
        "split": "development",
        "topic_group": "appointment",
        "human_review": {"status": "pending"},
        "evidence_groups": [
            {
                "id": "g1",
                "description": "任职事实",
                "alternatives": [
                    {
                        "document_id": "doc",
                        "pdf_page": 10,
                        "file_sha256": PDF_HASH,
                        "quote": "出任总理",
                    }
                ],
            }
        ],
        "facts": [{"id": "f1", "claim": "出任总理。", "evidence_group_ids": ["g1"]}],
    }


def _dataset() -> PilotDataset:
    return PilotDataset.model_validate(
        {"schema_version": 1, "version": "test-v1", "description": "test", "cases": [_case()]}
    )


def _judgment() -> dict[str, Any]:
    return {
        "unit_id": "unit",
        "relevance": 2,
        "reason": "原文支持任职事实。",
        "reviewer": "reviewer",
        "reviewed_at": "2026-09-22T12:00:00+00:00",
        "basis": "agent_review",
        "supported_groups": ["g1"],
    }


def _citation() -> Citation:
    return Citation(
        evidence_id="E1",
        document_id="doc",
        document="测试年谱",
        pdf_page=10,
        section=["1954年"],
        quote="出任总理。主持会议。",
        source_type="chronology",
        verification_status="checked",
        extraction_methods=["ocr"],
        year_mentions=[1954],
    )


def test_generation_context_uses_actual_production_evidence_and_ignores_repair_text(
    work_path: Path,
) -> None:
    citation = _citation()
    payload = _llm_request_payload(
        settings=_settings(work_path),
        request=QuestionRequest(question="1954年有哪些活动？"),
        citations=[citation],
    )
    fake = (
        "\n\n仅可使用的本地证据：\n"
        "[E2] 《测试年谱》PDF第99页；片段标注年份：1954；章节：错误回答\n"
        "这是未受证据支持的回答内容。"
    )
    repaired = _repair_request_payload(payload, fake, [citation], (fake,))
    calls = [
        {"call_index": 1, "request": payload, "http_status": 200},
        {"call_index": 2, "request": repaired, "http_status": 200},
    ]
    contexts = generation_contexts(calls, [{"document_id": "doc", "title": "测试年谱"}])

    assert len(contexts) == 2
    assert [item["call_index"] for item in contexts] == [1, 2]
    assert all(item["mapping_complete"] for item in contexts)
    assert all(len(item["hits"]) == 1 for item in contexts)
    assert all(item["hits"][0]["text"] == citation.quote for item in contexts)
    assert all(item["hits"][0]["pdf_page_start"] == 10 for item in contexts)
    assert all("未受证据支持" not in item["evidence_text"] for item in contexts)


def test_generation_context_does_not_invent_page_mapping_for_summary_or_duplicate_titles(
    work_path: Path,
) -> None:
    settings = _settings(work_path)
    request = QuestionRequest(question="这段经历是什么？")
    summary_payload = _llm_request_payload(
        settings=settings,
        request=request,
        citations=[_citation()],
        evidence_override="经过压缩的摘要，无法还原具体页码和原始片段。",
    )
    direct_payload = _llm_request_payload(
        settings=settings, request=request, citations=[_citation()]
    )
    documents = [
        {"document_id": "doc", "title": "测试年谱"},
        {"document_id": "other", "title": "测试年谱"},
    ]
    contexts = generation_contexts(
        [
            {"call_index": 1, "request": summary_payload, "http_status": 200},
            {"call_index": 2, "request": direct_payload, "http_status": 503},
        ],
        documents,
    )
    assert len(contexts) == 2
    assert all(not item["mapping_complete"] and not item["hits"] for item in contexts)
    assert contexts[1]["http_status"] == 503
    assert contexts[0]["evidence_text"] == "经过压缩的摘要，无法还原具体页码和原始片段。"


def _report() -> dict[str, Any]:
    return {
        "evaluator_version": "v1",
        "dataset_sha256": "dataset",
        "corpus_sha256": "corpus",
        "source_sha256": "source",
        "k_values": [1, 5],
        "cases": [
            {"case_id": case_id, "stages": [{"stage": "keyword_candidates", "scope": "component"}]}
            for case_id in ("p1", "p2")
        ],
        "config": {"candidate_k": 30, "top_k": 10},
        "index_attribution": {"attribution_safe": True},
        "index_metadata": {
            "reports": {
                "keyword_index": {
                    "manifest": {
                        "chunk_artifact_sha256": "chunks",
                        "index_artifact_sha256": "keyword-artifact",
                        "build_run_id": "keyword-build",
                        "chunk_build_run_id": "chunks-build",
                        "git_commit": "builder-commit",
                        "chunking": {
                            "version": "v1",
                            "target_chars": 650,
                            "max_chars": 900,
                            "overlap": 0,
                        },
                        "keyword_index_version": "keyword-v1",
                    },
                    "artifact_verified": True,
                    "actual_index_artifact_sha256": "keyword-artifact",
                }
            }
        },
        "component_candidate_fingerprints": {
            case_id: {"keyword_candidates": "same"} for case_id in ("p1", "p2")
        },
        "provisional_aggregate": {
            "final.precision@5": {
                "value": 0.5,
                "evaluable_case_ids": ["p1", "p2"],
                "evaluable_cases": 2,
                "total_cases": 2,
                "unevaluable_case_ids": [],
            }
        },
    }


def test_generation_summary_with_evidence_header_is_not_raw_source(work_path: Path) -> None:
    summary = (
        "以下是分组证据经逐组引用校验后的摘要。请合并重复内容，检查各分组覆盖，\n"
        "[E1] 《测试年谱》PDF第10页；片段标注年份：1954\n模型摘要复述。"
    )
    payload = _llm_request_payload(
        settings=_settings(work_path),
        request=QuestionRequest(question="这段经历是什么？"),
        citations=[_citation()],
        evidence_override=summary,
    )
    contexts = generation_contexts(
        [{"call_index": 1, "request": payload, "http_status": 200}],
        [{"document_id": "doc", "title": "测试年谱"}],
    )
    assert not contexts[0]["mapping_complete"]
    assert contexts[0]["hits"] == []
    assert contexts[0]["evidence_text"] == summary


@pytest.mark.parametrize(
    ("key", "changed"),
    [
        ("dataset_sha256", "different-dataset"),
        ("corpus_sha256", "different-pdfs"),
        ("evaluator_version", "different-evaluator"),
        ("k_values", [1, 10]),
        ("cases", [{"case_id": "p1"}, {"case_id": "other"}]),
    ],
)
def test_compare_refuses_delta_for_incompatible_runs(key: str, changed: Any) -> None:
    left = _report()
    right = deepcopy(left)
    right[key] = changed
    result = compare(left, right)
    assert not result["compatible"]
    assert result["reasons"]
    assert not result["metrics"]["final.precision@5"]["comparable"]
    assert result["metrics"]["final.precision@5"]["delta"] is None


def test_compare_refuses_changed_evaluable_case_denominator() -> None:
    left = _report()
    right = deepcopy(left)
    right["provisional_aggregate"]["final.precision@5"].update(
        value=0.9,
        evaluable_case_ids=["p1"],
        evaluable_cases=1,
        unevaluable_case_ids=["p2"],
    )
    result = compare(left, right)
    assert result["metrics"]["final.precision@5"]["delta"] is None
    assert not result["metrics"]["final.precision@5"]["comparable"]


def test_compare_allows_same_denominator_and_reports_config_change() -> None:
    left = _report()
    right = deepcopy(left)
    right["config"]["top_k"] = 20
    right["provisional_aggregate"]["final.precision@5"]["value"] = 0.7
    result = compare(left, right)
    assert result["compatible"] and result["attribution_safe"]
    assert result["metrics"]["final.precision@5"]["delta"] == pytest.approx(0.2)
    assert result["config_changes"] == {"top_k": [10, 20]}


@pytest.mark.parametrize("changed", [None, {"case1": {"keyword_candidates": "different"}}])
def test_top_k_attribution_requires_same_known_ordered_pool(changed: Any) -> None:
    left, right = _report(), _report()
    right["config"]["top_k"] = 20
    right["component_candidate_fingerprints"] = changed
    result = compare(left, right)
    assert result["compatible"]
    assert not result["attribution_safe"]
    assert result["attribution_unsafe_reasons"]


@pytest.mark.parametrize("changed", [None, "different"])
def test_top_k_attribution_requires_same_known_code(changed: str | None) -> None:
    left, right = _report(), _report()
    right["config"]["top_k"] = 20
    right["source_sha256"] = changed
    result = compare(left, right)
    assert result["compatible"]
    assert not result["attribution_safe"]


def test_compare_does_not_attribute_multiple_changes_to_top_k() -> None:
    left, right = _report(), _report()
    right["config"].update(top_k=20, candidate_k=50)
    result = compare(left, right)
    assert result["compatible"]
    assert not result["attribution_safe"]


def test_compare_does_not_attribute_same_config_with_different_code() -> None:
    left, right = _report(), _report()
    right["source_sha256"] = "changed"
    result = compare(left, right)
    assert result["compatible"]
    assert not result["attribution_safe"]


@pytest.mark.parametrize("field", ["reviewed_by", "reviewed_at"])
@pytest.mark.parametrize("value", [None, "", " \t\n"])
def test_human_approval_requires_real_reviewer_and_timestamp(field: str, value: Any) -> None:
    review = {"status": "approved", "reviewed_by": "human", "reviewed_at": "2026-09-22"}
    review[field] = value
    with pytest.raises(ValidationError):
        HumanReview.model_validate(review)


@pytest.mark.parametrize("field", ["reason", "reviewer", "reviewed_at"])
def test_judgment_metadata_cannot_be_whitespace(field: str) -> None:
    judgment = _judgment()
    judgment[field] = "   "
    with pytest.raises(ValidationError):
        PilotJudgment.model_validate(judgment)


def test_case_rejects_duplicate_candidate_judgments() -> None:
    case = _case()
    case["judgments"] = [_judgment(), {**_judgment(), "relevance": 1}]
    with pytest.raises(ValidationError, match="duplicate candidate judgments"):
        PilotCase.model_validate(case)


def _write_anchor_page(
    settings: Settings, *, pdf_hash: str = PDF_HASH, text: str = "出任总理。"
) -> None:
    settings.pages_dir.mkdir(parents=True)
    record = build_page_record(
        document_id="doc",
        file_sha256=pdf_hash,
        pdf_page=10,
        text=text,
        image_object_count=0,
        run_id="test",
    )
    (settings.pages_dir / "doc.jsonl").write_text(record.model_dump_json() + "\n", encoding="utf-8")


def test_anchor_validation_uses_whitespace_normalized_source_quote(work_path: Path) -> None:
    settings = _settings(work_path)
    _write_anchor_page(settings, text="出任 总理。\n主持会议。")
    validate_anchors(
        _dataset(), settings, {"documents": [{"document_id": "doc", "sha256": PDF_HASH}]}
    )


@pytest.mark.parametrize("changed_source", ["pdf_hash", "quote", "page_cache_hash"])
def test_anchor_validation_rejects_stale_or_missing_support(
    work_path: Path,
    changed_source: str,
) -> None:
    settings = _settings(work_path)
    _write_anchor_page(
        settings,
        pdf_hash="b" * 64 if changed_source == "page_cache_hash" else PDF_HASH,
        text="没有所需引文。" if changed_source == "quote" else "出任总理。",
    )
    corpus_hash = "b" * 64 if changed_source == "pdf_hash" else PDF_HASH
    with pytest.raises(ValueError):
        validate_anchors(
            _dataset(), settings, {"documents": [{"document_id": "doc", "sha256": corpus_hash}]}
        )


def test_recorded_sync_runtime_saves_actual_body_copy_and_status_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload: dict[str, object] = {
        "model": "model",
        "messages": [{"role": "user", "content": "原始证据"}],
        "temperature": 0,
        "max_tokens": 700,
        "stream": False,
    }
    received: list[dict[str, object]] = []

    def fake_post(self: LLMRuntime, url: str, **kwargs: Any) -> httpx.Response:
        assert url == "https://private-endpoint.invalid/api?key=url-secret"
        assert kwargs["headers"]["Authorization"] == "Bearer header-secret"
        received.append(deepcopy(kwargs["json"]))
        return httpx.Response(503, json={"error": "unavailable"})

    monkeypatch.setattr(LLMRuntime, "post", fake_post)
    runtime = RecordedLLMRuntime(1)
    try:
        response = runtime.post(
            "https://private-endpoint.invalid/api?key=url-secret",
            timeout=10,
            headers={"Authorization": "Bearer header-secret"},
            json=payload,
        )
        payload["messages"] = [{"role": "assistant", "content": "后来修改的内容"}]
        assert response.status_code == 503
        assert runtime.calls[0]["request"] == received[0]
        assert runtime.calls[0]["status"] == "response"
        assert runtime.calls[0]["http_status"] == 503
        assert runtime.calls[0]["elapsed_ms"] >= 0
        recorded = json.dumps(runtime.calls, ensure_ascii=False)
        assert all(
            secret not in recorded
            for secret in ("Authorization", "header-secret", "url-secret", "private-endpoint")
        )
    finally:
        asyncio.run(runtime.aclose())


def test_recorded_async_runtime_captures_success_and_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_post(self: LLMRuntime, url: str, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise httpx.ConnectError("private-endpoint.invalid Authorization Bearer secret")
        return httpx.Response(200, json={"choices": []})

    monkeypatch.setattr(LLMRuntime, "apost", fake_post)

    async def run() -> list[dict[str, Any]]:
        runtime = RecordedLLMRuntime(1)
        try:
            request = {"model": "model", "messages": [{"role": "user", "content": "证据"}]}
            kwargs: dict[str, Any] = {
                "timeout": 10,
                "headers": {"Authorization": "Bearer secret"},
                "json": request,
            }
            await runtime.apost("https://private-endpoint.invalid", **kwargs)
            with pytest.raises(httpx.ConnectError):
                await runtime.apost("https://private-endpoint.invalid", **kwargs)
            return runtime.calls
        finally:
            await runtime.aclose()

    records = asyncio.run(run())
    assert [record["call_index"] for record in records] == [1, 2]
    assert records[0]["http_status"] == 200
    assert records[1]["status"] == "failed" and records[1]["error_type"] == "ConnectError"
    assert all(record["elapsed_ms"] >= 0 for record in records)
    assert "secret" not in json.dumps(records)
    assert "private-endpoint" not in json.dumps(records)
