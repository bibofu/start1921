"""Run the same business queries against SQLite and an isolated PostgreSQL schema."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from history_agent.corpus.models import CorpusCatalog
from history_agent.corpus.scanner import scan_corpus
from history_agent.db import Database
from history_agent.research.event_deduplication import (
    list_event_merge_review_queue,
    merge_duplicate_events,
)
from history_agent.research.model_extraction import select_event_candidates
from history_agent.research.models import (
    EventParticipant,
    EvidenceReference,
    HistoricalEvent,
    HistoricalRelationship,
    PersonCatalog,
    RelationTypeCatalog,
    ReviewStatus,
    TemporalPoint,
)
from history_agent.research.organization import get_organization_relationships
from history_agent.research.people import sync_person_catalog, sync_relation_types
from history_agent.research.store import ResearchStore
from history_agent.research.timeline import get_person_timeline
from psycopg import sql
from pypdf import PdfWriter

ZHOU_DOCUMENT = "zhou_enlai_chronology_1949_1976"
LIN_DOCUMENT = "lin_biao_chronology"


def _catalog() -> PersonCatalog:
    return PersonCatalog.model_validate(
        {
            "people": [
                {"person_id": "zhou_enlai", "canonical_name": "周恩来"},
                {"person_id": "lin_biao", "canonical_name": "林彪"},
                {"person_id": "mao_zedong", "canonical_name": "毛泽东"},
            ]
        }
    )


@pytest.fixture(params=["sqlite", "postgresql"])
def research_database(request: pytest.FixtureRequest, work_path: Path) -> Iterator[Database]:
    target = os.environ.get("HISTORY_AGENT_TEST_POSTGRES_URL")
    schema: str | None = None
    if request.param == "postgresql":
        if not target:
            pytest.skip("Set HISTORY_AGENT_TEST_POSTGRES_URL for PostgreSQL business SQL checks")
        schema = f"test_research_{uuid4().hex}"
        with psycopg.connect(target, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        parsed = urlsplit(target)
        query = dict(parse_qsl(parsed.query))
        query["options"] = f"{query.get('options', '')} -csearch_path={schema}".strip()
        database = Database(urlunsplit(parsed._replace(query=urlencode(query))))
    else:
        database = Database(work_path / "research.sqlite")
    try:
        sync_person_catalog(database, _catalog())
        sync_relation_types(
            database,
            RelationTypeCatalog.model_validate(
                {
                    "relation_types": [
                        {
                            "relation_type": "held_position",
                            "label": "任职",
                            "object_kind": "organization",
                            "extraction_policy": "allowed",
                            "description": "任职关系测试",
                        }
                    ]
                }
            ),
        )
        with database.connect() as connection:
            for document_id, title in (
                (ZHOU_DOCUMENT, "周恩来年谱"),
                (LIN_DOCUMENT, "林彪年谱"),
            ):
                connection.execute(
                    "INSERT INTO documents "
                    "(document_id, title, creators_json, source_type, source_series_json, "
                    "verification_status, enabled, ocr_strategy, created_at, updated_at) "
                    "VALUES (?, ?, '[]', 'chronology', '[]', 'verified', 1, 'none', 'now', 'now')",
                    (document_id, title),
                )
                connection.execute(
                    "INSERT INTO document_files "
                    "(document_id, relative_path, filename, sha256, size_bytes, page_count, "
                    "modified_at, is_encrypted, first_seen_at, last_seen_at) "
                    "VALUES (?, ?, ?, ?, 100, 100, 'now', 0, 'now', 'now')",
                    (document_id, f"{document_id}.pdf", f"{document_id}.pdf", document_id),
                )
        yield database
    finally:
        if schema is not None and target is not None:
            with psycopg.connect(target, autocommit=True) as connection:
                connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def _save_event(
    database: Database,
    event_id: str,
    *,
    document_id: str = ZHOU_DOCUMENT,
    description: str = "周恩来、林彪致电毛泽东，说明谈判条件并提出两种解决办法。",
    review_status: ReviewStatus = "needs_review",
    confidence: float = 0.6,
    evidence_count: int = 1,
) -> HistoricalEvent:
    event = HistoricalEvent(
        event_id=event_id,
        name=description,
        event_type="correspondence",
        start=TemporalPoint(
            value="1943-01-21",
            precision="day",
            certainty="exact" if document_id == ZHOU_DOCUMENT else "inferred",
        ),
        description=description,
        participants=[
            EventParticipant(
                person_id="zhou_enlai",
                role="年谱主体" if document_id == ZHOU_DOCUMENT else None,
                mention_text="周恩来",
            ),
            EventParticipant(
                person_id="lin_biao",
                role="年谱主体" if document_id == LIN_DOCUMENT else None,
                mention_text="林彪",
            ),
            EventParticipant(person_id="mao_zedong", mention_text="毛泽东"),
        ],
        evidence=[
            EvidenceReference(
                evidence_id=f"evidence_{event_id}_{index}",
                document_id=document_id,
                pdf_page_start=10 + index,
                pdf_page_end=10 + index,
                quote=description,
                extraction_methods=["text_layer"],
            )
            for index in range(evidence_count)
        ],
        extraction_method="rule",
        extraction_confidence=confidence,
        review_status=review_status,
        extractor_version="chronology-rules-v1",
    )
    ResearchStore(database).save_event(event)
    return event


def test_timeline_accepts_null_and_named_other_person(research_database: Database) -> None:
    _save_event(research_database, "event_source")
    for other_person_id in (None, "lin_biao"):
        response = get_person_timeline(
            research_database,
            person_id="zhou_enlai",
            other_person_id=other_person_id,
            start_year=1943,
            end_year=1943,
        )
        assert response.total == 1
        assert response.events[0].event_id == "event_source"
        assert response.events[0].evidence[0].pdf_page_start == 10


def test_merge_review_queue_and_canonical_timeline_queries(
    research_database: Database, work_path: Path,
) -> None:
    _save_event(research_database, "event_zhou", confidence=0.9, review_status="unreviewed")
    _save_event(
        research_database,
        "event_lin",
        document_id=LIN_DOCUMENT,
        description="林彪、周恩来致电毛泽东，说明谈判条件，提出两种解决办法。",
        confidence=0.9,
        review_status="unreviewed",
    )
    summary = merge_duplicate_events(
        database=research_database,
        reports_dir=work_path / "reports",
        run_id="postgres-business-queries",
        minimum_score=0.65,
        automatic_score=0.99,
    )
    assert summary.uncertain_groups == 1
    queue = list_event_merge_review_queue(research_database)
    assert len(queue) == 1
    assert queue[0]["member_count"] == 2
    for other_person_id in (None, "lin_biao"):
        timeline = get_person_timeline(
            research_database, person_id="zhou_enlai", other_person_id=other_person_id,
        )
        assert timeline.total == 1
        assert timeline.events[0].record_kind == "canonical"
        assert set(timeline.events[0].source_event_ids) == {"event_zhou", "event_lin"}


def test_model_candidate_selection_deduplicates_and_orders_without_calling_model(
    research_database: Database,
) -> None:
    _save_event(research_database, "event_review", confidence=0.7, evidence_count=2)
    _save_event(
        research_database, "event_low_score", confidence=0.1, review_status="unreviewed",
    )
    candidates, skipped = select_event_candidates(
        research_database, catalog=_catalog(), model_name="deepseek-v4-pro", limit=10,
    )
    assert skipped == 0
    assert [candidate.event.event_id for candidate in candidates] == [
        "event_review", "event_low_score",
    ]
    assert len(candidates[0].event.evidence) == 2


def test_organization_pagination_keeps_unknown_dates_first(research_database: Database) -> None:
    event = _save_event(research_database, "event_relationship")
    for relationship_id, start in (
        ("relationship_dated", event.start),
        ("relationship_unknown", TemporalPoint()),
    ):
        ResearchStore(research_database).save_relationship(
            HistoricalRelationship(
                relationship_id=relationship_id,
                relation_type="held_position",
                subject_person_id="zhou_enlai",
                subject_mention_text="周恩来",
                organization_name="政务院",
                role_title="总理",
                start=start,
                evidence=event.evidence,
                extraction_method="manual",
                extraction_confidence=0.5,
                review_status="unreviewed",
            )
        )
    first = get_organization_relationships(
        research_database, person_id="zhou_enlai", limit=1,
    )
    second = get_organization_relationships(
        research_database, person_id="zhou_enlai", limit=1, offset=1,
    )
    assert first.total == second.total == 2
    assert first.relationships[0].relationship_id == "relationship_unknown"
    assert second.relationships[0].relationship_id == "relationship_dated"


def test_corpus_scanner_preserves_nul_metadata_on_insert_and_upsert(
    research_database: Database, work_path: Path,
) -> None:
    docs_dir = work_path / "docs"
    docs_dir.mkdir()
    title = "含空字符\0的标题😀"
    author = "作者\0姓名"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": title, "/Author": author})
    with (docs_dir / "metadata.pdf").open("wb") as stream:
        writer.write(stream)
    catalog = CorpusCatalog.model_validate(
        {
            "documents": [{
                "document_id": "metadata_document",
                "filename": "metadata.pdf",
                "title": "PDF 元数据保真",
                "source_type": "chronology",
                "verification_status": "verified",
            }]
        }
    )
    for run_id, status in (("metadata_insert", "new"), ("metadata_upsert", "unchanged")):
        result = scan_corpus(
            database=research_database,
            catalog=catalog,
            docs_dir=docs_dir,
            project_root=work_path,
            run_id=run_id,
        )
        assert result.observations[0].status == status
        with research_database.connect() as connection:
            rows = connection.execute(
                "SELECT pdf_title, pdf_author FROM document_files WHERE document_id=?",
                ("metadata_document",),
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["pdf_title"] == title
        assert rows[0]["pdf_author"] == author
        assert isinstance(rows[0]["pdf_title"], str)
