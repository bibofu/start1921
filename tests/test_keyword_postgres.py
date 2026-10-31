from __future__ import annotations

import json
import random
import string
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from history_agent.db_backend import database_connection
from history_agent.errors import IndexBuildError
from history_agent.retrieval import keyword_postgres as pg
from history_agent.retrieval.keyword import build_keyword_index, search_keyword_index

# The jieba lexer has its own behavioral tests below.


@pytest.mark.parametrize(
    ("prepared", "expected"),
    [
        ("alpha beta 毛泽东 1949年", ["alpha", "beta", "毛泽东", "1949年"]),
        ("anti-imperialism foo_bar", ["anti", "imperialism", "foo", "bar"]),
        ("1934-1936 1956年", ["1934", "1936", "1956年"]),
    ],
)
def test_lexer_keeps_application_terms(
    prepared: str, expected: list[str],
) -> None:
    assert pg.lex_terms(prepared) == expected


def test_invalid_utf8_at_term_limit_is_rejected_explicitly() -> None:
    with pytest.raises(IndexBuildError, match="invalid UTF-8 boundary"):
        pg.lex_terms("１" * 20000)


def _record(number: int, text: str, **overrides: Any) -> dict[str, Any]:
    result = {
        "chunk_id": f"c{number}", "document_id": f"d{number % 3}", "file_sha256": "hash",
        "title": "标题\x00原样保留", "filename": "文献.pdf", "creators": ["毛泽东"],
        "source_type": "history", "verification_status": "verified",
        "chunk_index": number, "page_chunk_index": 0, "pdf_page_start": number + 1,
        "pdf_page_end": number + 1, "section_path": ["Appendix_100%\\原文", "Ä"],
        "text": text, "search_text": text, "character_count": len(text),
        "year_mentions": [1949], "scope_status": "in_scope", "people": ["毛泽东", "周恩来"],
        "extraction_methods": ["text_layer"], "content_hash": f"hash-{number}",
        "cleaner_version": "fixture", "chunker_version": "fixture",
    }
    result.update(overrides)
    return result


@pytest.fixture
def indexes(work_path: Path, postgres_target: str) -> dict[str, Any]:
    chunks = work_path / "chunks"
    chunks.mkdir()
    rows = [
        _record(0, "毛泽东调查研究政策 alpha-beta alpha-beta 1.25 1949年"),
        _record(1, "毛泽东调查研究政策 alpha beta 1 25 1949年"),
        _record(2, "毛泽东调查研究政策 alpha X beta 1 X 25 1949年"),
        _record(3, "调查研究政策", source_type="selected_works", people=[]),
        _record(4, "毛泽东调查研究政策 1949年经历", source_type="chronology"),
        _record(5, "毛泽东调查研究政策 1935年经历", year_mentions=[1935]),
        _record(6, "毛泽东调查研究政策 1980年", year_mentions=[1980], scope_status="out_of_scope"),
        _record(7, "周恩来调查研究政策", people=["周恩来"], creators=["周恩来"]),
        _record(8, "毛泽东调查研究政策", creators=[], section_path=["different"]),
        _record(9, "稀有词语", creators=[]),
        _record(10, "完全不相干", creators=[]),
        _record(11, "!", creators=[]),
        _record(12, "１２３４５ ١٢٣٤٥ 𝟙𝟚𝟛𝟜𝟝", creators=[]),
    ]
    (chunks / "fixture.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )
    aliases = work_path / "aliases.json"
    aliases.write_text(
        json.dumps({"people": [
            {"person_id": "mao_zedong", "canonical_name": "毛泽东", "aliases": []},
            {"person_id": "zhou_enlai", "canonical_name": "周恩来", "aliases": []},
        ]}, ensure_ascii=False),
        encoding="utf-8",
    )
    build_keyword_index(
        chunks_dir=chunks, index_path=postgres_target, reports_dir=work_path / "postgres",
        run_id="postgres", project_root=work_path,
    )
    return {
        "postgres": postgres_target, "aliases": aliases, "chunks": chunks, "work": work_path,
    }


@pytest.mark.parametrize(
    "query",
    ["毛泽东关于调查研究的观点", "党中央1949年的重要决策", "alpha-beta"],
)
def test_postgres_search_returns_ranked_hits(
    indexes: dict[str, Any], query: str,
) -> None:
    response = search_keyword_index(
        index_path=indexes["postgres"], aliases_path=indexes["aliases"], query=query,
    )
    assert response.hits
    assert [hit.rank for hit in response.hits] == list(range(1, len(response.hits) + 1))
    assert all(
        left.score >= right.score
        for left, right in zip(response.hits, response.hits[1:], strict=False)
    )


def test_postgres_runtime_build_search_and_metadata(indexes: dict[str, Any]) -> None:
    summary = build_keyword_index(
        chunks_dir=indexes["chunks"], index_path=indexes["postgres"],
        reports_dir=indexes["work"] / "rebuilt", run_id="rebuilt", project_root=indexes["work"],
    )
    assert summary.index_version == pg.INDEX_VERSION
    response = search_keyword_index(
        index_path=indexes["postgres"], aliases_path=indexes["aliases"], query="alpha-beta"
    )
    assert response.hits
    metadata = pg.load_keyword_index_metadata(indexes["postgres"])
    assert metadata["artifact_verified"]
    assert indexes["postgres"] not in json.dumps(metadata)


def test_failed_publication_keeps_previous_generation_and_content(
    indexes: dict[str, Any],
) -> None:
    before = pg.load_keyword_index_metadata(indexes["postgres"])
    records = pg.common.load_chunks(indexes["chunks"])
    chunks = list(pg._indexed_records(records))
    chunks[0] = replace(chunks[0], doc_length=chunks[0].doc_length + 1)
    postings = [
        (term, chunk.rowid, positions)
        for chunk in chunks
        for term, positions in sorted(pg.positions_for_terms(chunk.terms).items())
    ]
    with pytest.raises(IndexBuildError, match="lengths"):
        pg.publish_keyword_generation(
            target_url=indexes["postgres"], chunks=chunks, postings=postings,
            run_id="bad", started_at="now",
        )
    after = pg.load_keyword_index_metadata(indexes["postgres"])
    assert before == after
    with database_connection(indexes["postgres"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM keyword_generations").fetchone()[0] == 1


def test_metadata_verification_reads_actual_postings(indexes: dict[str, Any]) -> None:
    before = pg.load_keyword_index_metadata(indexes["postgres"])
    with database_connection(indexes["postgres"]) as connection:
        connection.execute(
            "UPDATE keyword_postings SET term = ? WHERE generation_id = ? AND term = ?",
            ("altered", before["generation_id"], "alpha"),
        )
    after = pg.load_keyword_index_metadata(indexes["postgres"])
    assert not after["artifact_verified"]
    assert after["actual_index_artifact_sha256"] != before["actual_index_artifact_sha256"]


def test_explicit_generation_fingerprint_rejects_missing_generation(
    postgres_target: str,
) -> None:
    pg.publish_keyword_generation(
        target_url=postgres_target, chunks=[], postings=[], run_id="empty", started_at="now"
    )
    with pytest.raises(IndexBuildError, match="does not exist"):
        pg.keyword_generation_fingerprint(target_url=postgres_target, generation_id=99999)


def test_long_ascii_token_exceeding_btree_limit_is_searchable(indexes: dict[str, Any]) -> None:
    token = "".join(random.Random(1921).choices(string.ascii_lowercase, k=40000))
    (indexes["chunks"] / "long.jsonl").write_text(
        json.dumps(_record(13, token), ensure_ascii=False), encoding="utf-8"
    )
    build_keyword_index(
        chunks_dir=indexes["chunks"], index_path=indexes["postgres"],
        reports_dir=indexes["work"] / "postgres", run_id="long-token",
        project_root=indexes["work"],
    )
    response = search_keyword_index(
        index_path=indexes["postgres"], aliases_path=indexes["aliases"], query=token
    )
    assert [hit.chunk_id for hit in response.hits] == ["c13"]
    assert len(pg.lex_terms(token)[0]) == 32768


def test_index_upgrade_preserves_published_content(indexes: dict[str, Any]) -> None:
    before = pg.load_keyword_index_metadata(indexes["postgres"])
    with database_connection(indexes["postgres"]) as connection:
        connection.executescript(
            "DROP INDEX keyword_postings_identity;"
            "DROP INDEX keyword_postings_document_order;"
            "ALTER TABLE keyword_postings ADD PRIMARY KEY(generation_id,term,rowid);"
            "CREATE INDEX keyword_postings_document ON keyword_postings(generation_id,rowid,term);"
        )
    pg.upgrade_keyword_schema(target_url=indexes["postgres"])
    pg.upgrade_keyword_schema(target_url=indexes["postgres"])
    assert pg.load_keyword_index_metadata(indexes["postgres"]) == before
    assert search_keyword_index(
        index_path=indexes["postgres"], aliases_path=indexes["aliases"], query="alpha-beta"
    ).hits


def test_rebuild_schema_check_keeps_published_generation_readable(
    indexes: dict[str, Any],
) -> None:
    with database_connection(indexes["postgres"]) as writer:
        pg._ensure_keyword_schema(pg._postgres(writer))
        with database_connection(indexes["postgres"]) as reader:
            reader.execute("SET LOCAL lock_timeout = '100ms'")
            count = reader.execute("SELECT COUNT(*) FROM keyword_postings").fetchone()
            assert count is not None and count[0] > 0
