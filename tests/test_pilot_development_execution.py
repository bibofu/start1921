import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from history_agent.config import Settings
from history_agent.evaluation.pilot import collect, score, validate_anchors
from history_agent.evaluation.pilot_models import PilotDataset
from history_agent.evaluation.pilot_protocols import HISTORY_CASE_ID, load_inputs
from history_agent.evaluation.pilot_workflow import prepare_reviews

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals/golden/development_annotations_v3.json"
PROTOCOLS = ROOT / "evals/golden/development_protocols_v3.json"


def _fake_collection(
    work_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_hashes: tuple[str, str] = ("synthetic-source", "synthetic-source"),
) -> tuple[dict, Path, list]:
    inputs = load_inputs(DATASET, PROTOCOLS)
    hashes = {
        a.document_id: a.file_sha256
        for case in inputs.dataset.cases
        for group in case.evidence_groups
        for a in group.alternatives
    }
    corpus = {
        "sha256": "synthetic-corpus",
        "documents": [
            {"document_id": doc_id, "sha256": sha, "title": doc_id}
            for doc_id, sha in hashes.items()
        ],
    }
    monkeypatch.setattr("history_agent.evaluation.pilot.corpus_snapshot", lambda settings: corpus)
    monkeypatch.setattr("history_agent.evaluation.pilot.validate_anchors", lambda *args: None)
    monkeypatch.setattr(
        "history_agent.evaluation.pilot._load_index_metadata", lambda settings: {"reports": {}}
    )
    monkeypatch.setattr(
        "history_agent.evaluation.pilot._index_attribution",
        lambda *args: {"attribution_safe": False},
    )
    fingerprints = iter(source_hashes)
    monkeypatch.setattr(
        "history_agent.evaluation.pilot.source_fingerprint", lambda root: next(fingerprints)
    )
    requests = []

    def search(**kwargs: object) -> SimpleNamespace:
        stage = {
            "stage": "final",
            "query": kwargs["query"],
            "hits": [
                {
                    "document_id": next(iter(hashes)),
                    "pdf_page_start": 1,
                    "pdf_page_end": 1,
                    "text": "Synthetic unlabeled candidate span",
                }
            ],
            "elapsed_ms": 1.0,
            "status": "ok",
        }
        return SimpleNamespace(
            degraded_components=[],
            trace=[SimpleNamespace(model_dump=lambda **kw: stage)],
            model_dump=lambda **kw: {"trace": [stage]},
        )

    def answer(settings: Settings, request: object, *, runtime: object) -> SimpleNamespace:
        assert settings.llm_api_key is None
        requests.append(request.model_dump(mode="json"))
        payload = {
            "answer": "Synthetic unreviewed answer",
            "citations": [],
            "query_plan": {"normalized_question": request.question},
            "retrieval_mode": "hybrid_retrieval",
        }
        return SimpleNamespace(model_dump=lambda **kw: payload)

    monkeypatch.setattr("history_agent.evaluation.pilot.search_hybrid_index", search)
    monkeypatch.setattr("history_agent.evaluation.pilot.answer_question", answer)
    capture_path = work_path / "capture.json"
    result = collect(
        DATASET,
        capture_path,
        protocols_path=PROTOCOLS,
        settings=Settings(_env_file=None, project_root=work_path, llm_api_key="unused-test-key"),
    )
    return result, capture_path, requests


def test_twenty_case_collection_preserves_real_history_and_counts_control_separately(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture, _, requests = _fake_collection(work_path, monkeypatch)
    assert len(capture["cases"]) == 20
    assert len(capture["control_cases"]) == 1
    assert len(requests) == 21
    primary = next(row for row in capture["cases"] if row["case_id"] == HISTORY_CASE_ID)
    control = capture["control_cases"][0]
    assert primary["request"]["history"] == [
        {"role": "user", "content": "林彪在1930—1949年相继担任哪些职务？"}
    ]
    assert primary["input_variant_id"] == "with_history"
    assert control["input_variant_id"] == "without_history_control"
    assert control["request"]["history"] == []
    assert all(row["session_id"] is None for row in requests)
    assert all(not row["llm_calls"] for row in [*capture["cases"], *capture["control_cases"]])
    assert capture["source_sha256"] == capture["source_sha256_after_collection"]


def test_collection_records_source_drift_and_blocks_attribution(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture, _, _ = _fake_collection(work_path, monkeypatch, ("before", "after"))
    assert capture["source_sha256"] == "before"
    assert capture["source_sha256_after_collection"] == "after"
    assert capture["index_attribution"]["attribution_safe"] is False
    assert "source files changed during collection" in capture["index_attribution"][
        "attribution_unsafe_reasons"
    ]


def test_development_review_score_flow_preserves_denominators_and_unknowns(
    work_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, capture_path, _ = _fake_collection(work_path, monkeypatch)
    reviews = work_path / "reviews"
    prepare_reviews(DATASET, capture_path, reviews, protocol_path=PROTOCOLS)
    main = json.loads((reviews / "answer_reviews.json").read_text(encoding="utf8"))
    control = json.loads(
        (reviews / "controls/without_history_control/answer_reviews.json").read_text(
            encoding="utf8"
        )
    )
    assert len(main["cases"]) == 20
    assert sum(len(case["facts"]) for case in main["cases"]) == 85
    assert len(control["cases"]) == 1 and len(control["cases"][0]["facts"]) == 10
    assert main["capture_sha256"] != control["capture_sha256"]
    control_packet = json.loads(
        (reviews / "controls/without_history_control/review_packet.json").read_text(encoding="utf8")
    )
    assert control_packet["capture_view"] == "control_projection"
    assert control_packet["parent_capture_sha256"] == main["capture_sha256"]
    assert control_packet["cases"][0]["capture_case_path"].startswith("control_cases[")
    assert control_packet["cases"][0]["request"]["history"] == []
    result = score(
        DATASET,
        capture_path,
        work_path / "report.json",
        protocols_path=PROTOCOLS,
        reviews_dir=reviews,
    )
    assert len(result["cases"]) == 20
    assert result["process_summary"]["target_cases"] == 20
    assert result["execution_accounting"]["execution_count"] == 21
    assert result["execution_accounting"]["independent_case_count"] == 20
    assert result["execution_accounting"]["http_calls"] == 0
    assert result["execution_accounting"]["tokens"]["total_tokens"]["value"] is None
    assert result["provisional_answer_aggregate"]["required_fact_recall"]["denominator"] == 0
    assert result["provisional_aggregate"]["final.required_group_recall@5"]["evaluable_cases"] == 17
    assert result["provisional_aggregate"]["final.precision@5"]["value"] is None
    assert len(result["control_reports"]["without_history_control"]["cases"]) == 1
    markdown = (work_path / "report.md").read_text(encoding="utf8")
    assert "独立题数：20；实际执行：21" in markdown
    assert "湖南活动：固定六年分层" in markdown
    assert "四项隔离检查" in markdown
    # A primary review file may not be copied onto a control arm, even for the same case ID.
    (reviews / "controls/without_history_control/answer_reviews.json").write_text(
        json.dumps(main), encoding="utf8"
    )
    with pytest.raises(ValueError, match="different capture"):
        score(
            DATASET,
            capture_path,
            work_path / "wrong_report.json",
            protocols_path=PROTOCOLS,
            reviews_dir=reviews,
        )


def test_negative_search_audit_expires_when_text_cache_changes(work_path: Path) -> None:
    settings = Settings(_env_file=None, project_root=work_path)
    settings.pages_dir.mkdir(parents=True)
    page_path = settings.pages_dir / "doc.jsonl"
    page_path.write_text("old searched text", encoding="utf8")
    sha = "a" * 64
    dataset = PilotDataset.model_validate(
        {
            "schema_version": 1,
            "version": "test",
            "description": "negative audit binding",
            "cases": [
                {
                    "id": "negative",
                    "question": "Unsupported premise?",
                    "category": "refusal",
                    "answerability": "unanswerable",
                    "split": "development",
                    "topic_group": "refusal",
                    "human_review": {"status": "pending"},
                    "refusal_basis": {
                        "local_search_audit": {
                            "documents": [
                                {
                                    "document_id": "doc",
                                    "sha256": sha,
                                    "actual_pdf_sha256": sha,
                                    "pages_cache_sha256": hashlib.sha256(
                                        page_path.read_bytes()
                                    ).hexdigest(),
                                    "ocr_cache_sha256": None,
                                }
                            ]
                        }
                    },
                }
            ],
        }
    )
    corpus = {"documents": [{"document_id": "doc", "sha256": sha}]}
    validate_anchors(dataset, settings, corpus)
    page_path.write_text(
        "new OCR text could support the previously unanswerable premise", encoding="utf8"
    )
    with pytest.raises(ValueError, match="refusal search audit text changed"):
        validate_anchors(dataset, settings, corpus)
