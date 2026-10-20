"""Keyword API: PostgreSQL production and unchanged SQLite baselines."""

from __future__ import annotations

from pathlib import Path

from history_agent.db_backend import is_postgres_target
from history_agent.retrieval import keyword_legacy, keyword_postgres
from history_agent.retrieval.keyword_legacy import (
    CJK_RUN as CJK_RUN,
)
from history_agent.retrieval.keyword_legacy import (
    INDEX_VERSION as INDEX_VERSION,
)
from history_agent.retrieval.keyword_legacy import (
    LATIN_OR_NUMBER as LATIN_OR_NUMBER,
)
from history_agent.retrieval.keyword_legacy import (
    PERIOD_RANGES as PERIOD_RANGES,
)
from history_agent.retrieval.keyword_legacy import (
    QUERY_STOP_EDGE_CHARACTERS as QUERY_STOP_EDGE_CHARACTERS,
)
from history_agent.retrieval.keyword_legacy import (
    QUERY_STOP_TERMS as QUERY_STOP_TERMS,
)
from history_agent.retrieval.keyword_legacy import (
    YEAR as YEAR,
)
from history_agent.retrieval.keyword_legacy import (
    YEAR_RANGE as YEAR_RANGE,
)
from history_agent.retrieval.keyword_legacy import (
    cjk_bigrams as cjk_bigrams,
)
from history_agent.retrieval.keyword_legacy import (
    hard_filter_people as hard_filter_people,
)
from history_agent.retrieval.keyword_legacy import (
    has_explicit_year_range as has_explicit_year_range,
)
from history_agent.retrieval.keyword_legacy import (
    infer_query_intent as infer_query_intent,
)
from history_agent.retrieval.keyword_legacy import (
    infer_year_range as infer_year_range,
)
from history_agent.retrieval.keyword_legacy import (
    load_chunks as load_chunks,
)
from history_agent.retrieval.keyword_legacy import (
    tokenize_for_index as tokenize_for_index,
)
from history_agent.retrieval.keyword_legacy import (
    tokenize_query as tokenize_query,
)
from history_agent.retrieval.keyword_legacy import (
    utc_now as utc_now,
)
from history_agent.retrieval.keyword_postgres import (
    load_keyword_index_metadata as load_keyword_index_metadata,
)
from history_agent.retrieval.models import KeywordIndexSummary, RetrievalPlan, SearchResponse


def build_keyword_index(
    *, chunks_dir: Path, index_path: Path | str, reports_dir: Path, run_id: str,
    project_root: Path | None = None,
) -> KeywordIndexSummary:
    if is_postgres_target(index_path):
        return keyword_postgres.build_keyword_index(
            chunks_dir=chunks_dir, index_path=str(index_path), reports_dir=reports_dir,
            run_id=run_id, project_root=project_root,
        )
    return keyword_legacy.build_keyword_index(
        chunks_dir=chunks_dir, index_path=Path(index_path), reports_dir=reports_dir,
        run_id=run_id, project_root=project_root,
    )


def search_keyword_index(
    *, index_path: Path | str, query: str, aliases_path: Path, top_k: int = 10,
    document_ids: list[str] | None = None, include_out_of_scope: bool = False,
    section_path_contains: str | None = None, plan: RetrievalPlan | None = None,
) -> SearchResponse:
    if is_postgres_target(index_path):
        return keyword_postgres.search_keyword_index(
            index_path=str(index_path), query=query, aliases_path=aliases_path, top_k=top_k,
            document_ids=document_ids, include_out_of_scope=include_out_of_scope,
            section_path_contains=section_path_contains, plan=plan,
        )
    return keyword_legacy.search_keyword_index(
        index_path=Path(index_path), query=query, aliases_path=aliases_path, top_k=top_k,
        document_ids=document_ids, include_out_of_scope=include_out_of_scope,
        section_path_contains=section_path_contains, plan=plan,
    )
