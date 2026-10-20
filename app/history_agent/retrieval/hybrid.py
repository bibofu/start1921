from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Literal

from history_agent.errors import RetrievalError
from history_agent.retrieval.keyword import YEAR, has_explicit_year_range, search_keyword_index
from history_agent.retrieval.models import (
    RetrievalPlan,
    RetrievalStageTrace,
    RetrievalTraceDrop,
    SearchHit,
    SearchResponse,
)
from history_agent.retrieval.vector import VectorIndexTarget, search_vector_index

RRF_K = 60
INTENT_SOURCE_BONUS = 0.004
TEMPORAL_BUCKET_COUNT = 3
MIN_TEMPORAL_COVERAGE_YEARS = 5
TEMPORAL_FOCUS_MARKERS = ("初期", "前期", "早期", "中期", "后期", "晚期", "末期")
OBSERVATION_QUERY_MARKERS = ("怎样记述", "如何记述", "怎样描述", "如何描述")
OBSERVATION_EXPANSION = "外貌 性格 生活 印象"
CAREER_QUERY_MARKERS = ("党内职务", "职务变化", "职务变动", "任职", "担任", "出任")
CAREER_ROLE_MARKER = re.compile(
    r"(?:第一书记|副书记|书记|候补委员|常务委员|常委|委员|副主席|主席|"
    r"秘书长|副部长|部长|负责人|政治委员|政委|党代表|中央局|党委|"
    r"党支部|特委|前委)"
)
PARTY_ROLE_MARKER = re.compile(
    r"(?:第一书记|副书记|书记|候补委员|常务委员|常委|(?<!政治)委员|副主席|主席|"
    r"秘书长|副部长|部长|负责人|党代表|中央局|党委|党支部|特委|前委)"
)
CAREER_CHANGE_MARKER = re.compile(
    r"(?:担任|出任|当选|选举|任命|改任|调任|兼任|升任|增补|组成|"
    r"进入|成为|任职|免去|免职|撤销|辞去|代理)"
)
CAREER_LEADING_PERSON = re.compile(
    r"^(?:(?:请问|请|梳理|介绍|概括|总结))?"
    r"(?P<person>[\u3400-\u4dbf\u4e00-\u9fff·]{2,8}?)(?=在|\s|(?:18|19|20)\d{2})"
)
CPC_CONGRESS_ORDINALS = (
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
)
CPC_CONGRESS_NUMBER = {
    ordinal: number for number, ordinal in enumerate(CPC_CONGRESS_ORDINALS, start=1)
}
CPC_CONGRESS_SHORT_NAME = re.compile(r"中共(?:第)?(?P<ordinal>[一二三四五六七八九十]{1,3})大")
CPC_CONGRESS_RANGE = re.compile(
    r"中共(?:第)?(?P<start>[一二三四五六七八九十]{1,3})大\s*"
    r"(?:至|到|—|–|-|~|～)\s*"
    r"中共(?:第)?(?P<end>[一二三四五六七八九十]{1,3})大"
)
logger = logging.getLogger(__name__)


def _stage_start(trace: list[RetrievalStageTrace] | None) -> float:
    return perf_counter() if trace is not None else 0.0


def _record_stage(
    trace: list[RetrievalStageTrace] | None,
    *,
    stage: str,
    query: str,
    hits: list[SearchHit],
    started: float,
    before: list[SearchHit] | None = None,
    reason: str = "filtered",
    notes: list[str] | None = None,
    requested_k: int | None = None,
    status: Literal["ok", "failed"] = "ok",
) -> None:
    if trace is None:
        return
    elapsed_ms = max(0.0, (perf_counter() - started) * 1000)
    retained = {hit.chunk_id for hit in hits}
    trace.append(
        RetrievalStageTrace(
            stage=stage,
            query=query,
            hits=[
                hit.model_copy(deep=True, update={"rank": rank})
                for rank, hit in enumerate(hits, start=1)
            ],
            elapsed_ms=round(elapsed_ms, 3),
            input_count=len(before) if before is not None else None,
            requested_k=requested_k,
            notes=notes or [],
            dropped=[
                RetrievalTraceDrop(chunk_id=hit.chunk_id, reason=reason)
                for hit in before or []
                if hit.chunk_id not in retained
            ],
            status=status,
        )
    )


def _rrf_snapshot(hits: list[SearchHit], scores: dict[str, float]) -> list[SearchHit]:
    return [
        hit.model_copy(
            update={"score": round(scores[hit.chunk_id], 8),
                    "rrf_score": round(scores[hit.chunk_id], 8)}
        )
        for hit in sorted(
            hits, key=lambda item: (-scores[item.chunk_id], item.pdf_page_start, item.chunk_id)
        )
    ]


def cpc_congress_ordinals(query: str) -> list[str]:
    ordinals: list[str] = []
    for match in CPC_CONGRESS_RANGE.finditer(query):
        start = CPC_CONGRESS_NUMBER.get(match.group("start"))
        end = CPC_CONGRESS_NUMBER.get(match.group("end"))
        if start is None or end is None:
            continue
        step = 1 if start <= end else -1
        ordinals.extend(
            CPC_CONGRESS_ORDINALS[number - 1] for number in range(start, end + step, step)
        )
    ordinals.extend(match.group("ordinal") for match in CPC_CONGRESS_SHORT_NAME.finditer(query))
    return list(dict.fromkeys(ordinals))


def expand_query(query: str) -> str:
    """Add restrained search hints for source observations and named congresses."""

    expansions: list[str] = []
    if any(marker in query for marker in OBSERVATION_QUERY_MARKERS):
        expansions.append(OBSERVATION_EXPANSION)
    for ordinal in cpc_congress_ordinals(query):
        expansions.append(f"中国共产党第{ordinal}次全国代表大会")
    return f"{query} {' '.join(expansions)}" if expansions else query


def _career_relevant_hits(
    hits: list[SearchHit], *, query: str, query_people: list[str]
) -> list[SearchHit]:
    """Keep only passages that directly connect the requested person to a role."""

    if not any(marker in query for marker in CAREER_QUERY_MARKERS):
        return hits
    if not query_people:
        match = CAREER_LEADING_PERSON.search(query.strip())
        query_people = [match.group("person")] if match is not None else []
    if not query_people:
        return hits
    role_marker = PARTY_ROLE_MARKER if "党内" in query else CAREER_ROLE_MARKER
    selected: list[SearchHit] = []
    for hit in hits:
        title_anchor = any(person in hit.title for person in query_people)
        clauses = re.split(r"(?<=[，,。！？；;])|\n+", hit.text)
        for clause in clauses:
            direct = any(
                re.search(
                    rf"{re.escape(person)}.{{0,10}}"
                    rf"(?:担任|出任|当选为|选为|任命为|改任|调任|兼任|升任|"
                    rf"增补为|成为|任职为|代理|为|任).{{0,12}}{role_marker.pattern}",
                    clause,
                )
                or re.search(
                    rf"{role_marker.pattern}.{{0,6}}{re.escape(person)}",
                    clause,
                )
                or re.search(
                    rf"{re.escape(person)}.{{0,60}}组成.{{0,20}}{role_marker.pattern}",
                    clause,
                )
                for person in query_people
            )
            title_context = (
                title_anchor
                and role_marker.search(clause) is not None
                and CAREER_CHANGE_MARKER.search(clause) is not None
            )
            if direct or title_context:
                selected.append(hit)
                break
    return selected


def _source_bonus(intent: str, source_type: str, title: str, query_people: list[str]) -> float:
    if intent == "timeline":
        if query_people and any(person in title for person in query_people):
            return INTENT_SOURCE_BONUS
        if not query_people and source_type == "chronology":
            return INTENT_SOURCE_BONUS
    if intent == "viewpoint" and source_type == "selected_works":
        return INTENT_SOURCE_BONUS
    if intent == "observation" and source_type == "contemporary_observation":
        return INTENT_SOURCE_BONUS
    return 0.0


def _primary_year(hit: SearchHit, start_year: int, end_year: int) -> int | None:
    years = sorted(year for year in hit.year_mentions if start_year <= year <= end_year)
    if not years:
        return None
    section_years = [
        int(match.group(1))
        for section in hit.section_path
        for match in YEAR.finditer(section)
        if start_year <= int(match.group(1)) <= end_year
    ]
    if section_years:
        return section_years[0]
    positions = [
        (hit.text.find(f"{year}年"), year) for year in years if hit.text.find(f"{year}年") >= 0
    ]
    return min(positions)[1] if positions else years[0]


def _select_with_temporal_coverage(
    ranked: list[SearchHit],
    *,
    query: str,
    query_year_range: list[int],
    top_k: int,
    coverage: str = "auto",
) -> list[SearchHit]:
    if coverage in {"relevance", "per_item"}:
        return ranked[:top_k]
    forced = coverage in {"per_year", "balanced_period"}
    if (
        len(query_year_range) != 2
        or (
            not forced
            and query_year_range[1] - query_year_range[0] + 1 < MIN_TEMPORAL_COVERAGE_YEARS
        )
        or top_k < TEMPORAL_BUCKET_COUNT
        or (not forced and any(marker in query for marker in TEMPORAL_FOCUS_MARKERS))
    ):
        return ranked[:top_k]

    start_year, end_year = query_year_range
    span = end_year - start_year + 1
    if coverage == "per_year" or span <= top_k:
        covered_ids: set[str] = set()
        for target_year in range(start_year, end_year + 1):
            match = next(
                (hit for hit in ranked if _primary_year(hit, start_year, end_year) == target_year),
                None,
            )
            if match is not None:
                covered_ids.add(match.chunk_id)
        for hit in ranked:
            if len(covered_ids) >= top_k:
                break
            covered_ids.add(hit.chunk_id)
        return [hit for hit in ranked if hit.chunk_id in covered_ids][:top_k]

    buckets: list[list[SearchHit]] = [[] for _ in range(TEMPORAL_BUCKET_COUNT)]
    for hit in ranked:
        primary_year = _primary_year(hit, start_year, end_year)
        if primary_year is None:
            continue
        bucket_index = min(
            TEMPORAL_BUCKET_COUNT - 1,
            (primary_year - start_year) * TEMPORAL_BUCKET_COUNT // span,
        )
        buckets[bucket_index].append(hit)

    quota = max(1, top_k // TEMPORAL_BUCKET_COUNT)
    selected_ids: set[str] = set()
    for bucket in buckets:
        for hit in bucket[:quota]:
            selected_ids.add(hit.chunk_id)
    for hit in ranked:
        if len(selected_ids) >= top_k:
            break
        selected_ids.add(hit.chunk_id)
    return [hit for hit in ranked if hit.chunk_id in selected_ids][:top_k]


def _best_congress_hits(ranked: list[SearchHit], query: str) -> list[SearchHit]:
    ordinals = cpc_congress_ordinals(query)
    selected: list[SearchHit] = []
    for ordinal in ordinals:
        markers = (
            f"党的第{ordinal}次全国代表大会",
            f"中国共产党第{ordinal}次全国代表大会",
            f"第{ordinal}次全国代表大会",
        )
        matches = [
            (index, hit)
            for index, hit in enumerate(ranked)
            if any(marker in " ".join(hit.section_path) for marker in markers)
            or any(marker in hit.text for marker in markers)
        ]
        if not matches:
            continue
        _, match = max(
            matches,
            key=lambda item: (
                any(marker in " ".join(item[1].section_path) for marker in markers),
                any(marker in item[1].text for marker in markers),
                "召开" in item[1].text or "举行" in item[1].text,
                item[1].source_type == "official_history",
                -item[0],
            ),
        )
        selected.append(match)
    return selected


def _select_with_congress_coverage(
    ranked: list[SearchHit], *, query: str, top_k: int
) -> list[SearchHit]:
    ordinals = cpc_congress_ordinals(query)
    if len(ordinals) < 2 or len(ordinals) > top_k:
        return ranked
    covered_ids = {hit.chunk_id for hit in _best_congress_hits(ranked, query)}
    for hit in ranked:
        if len(covered_ids) >= top_k:
            break
        covered_ids.add(hit.chunk_id)
    return [hit for hit in ranked if hit.chunk_id in covered_ids]


def _prepend_congress_keyword_hits(
    primary: SearchResponse, congress_hits: list[SearchHit]
) -> SearchResponse:
    combined: list[SearchHit] = []
    seen_ids: set[str] = set()
    for hit in [*congress_hits, *primary.hits]:
        if hit.chunk_id in seen_ids:
            continue
        seen_ids.add(hit.chunk_id)
        combined.append(hit.model_copy(update={"rank": len(combined) + 1}))
    return primary.model_copy(update={"hits": combined})


def fuse_search_responses(
    keyword: SearchResponse,
    vector: SearchResponse,
    *,
    top_k: int,
    coverage: str = "auto",
    trace: list[RetrievalStageTrace] | None = None,
) -> SearchResponse:
    """Fuse keyword and semantic rankings with reciprocal-rank fusion."""

    started = _stage_start(trace)
    by_chunk: dict[str, SearchHit] = {}
    scores: dict[str, float] = {}
    for hit in keyword.hits:
        merged = hit.model_copy(deep=True)
        merged.keyword_rank = hit.rank
        merged.keyword_score = hit.score
        merged.vector_rank = None
        merged.vector_score = None
        merged.rrf_score = None
        by_chunk[hit.chunk_id] = merged
        scores[hit.chunk_id] = 1.0 / (RRF_K + hit.rank)
    for hit in vector.hits:
        existing = by_chunk.get(hit.chunk_id)
        if existing is None:
            existing = hit.model_copy(deep=True)
            existing.keyword_rank = None
            existing.keyword_score = None
            by_chunk[hit.chunk_id] = existing
            scores[hit.chunk_id] = 0.0
        existing.vector_rank = hit.rank
        existing.vector_score = hit.score
        scores[hit.chunk_id] += 1.0 / (RRF_K + hit.rank)

    if trace is not None:
        _record_stage(
            trace, stage="rrf_fusion", query=keyword.query,
            hits=_rrf_snapshot(list(by_chunk.values()), scores), started=started,
            before=[*keyword.hits, *vector.hits],
            notes=["Reciprocal-rank fusion by chunk ID; no source bonus or model reranker."],
        )
    started = _stage_start(trace)
    for chunk_id, hit in by_chunk.items():
        scores[chunk_id] += _source_bonus(
            keyword.query_intent,
            hit.source_type,
            hit.title,
            keyword.query_people,
        )
        hit.rrf_score = round(scores[chunk_id], 8)
        hit.score = hit.rrf_score

    ranked = sorted(
        by_chunk.values(),
        key=lambda hit: (
            -scores[hit.chunk_id],
            hit.pdf_page_start,
            hit.chunk_id,
        ),
    )
    _record_stage(
        trace, stage="rule_ranking", query=keyword.query, hits=ranked, started=started,
        before=list(by_chunk.values()),
        notes=["Intent/source preference bonus applied to RRF; this is not a model reranker."],
    )
    started = _stage_start(trace)
    query_people = keyword.query_people
    if not query_people and any(marker in keyword.query for marker in CAREER_QUERY_MARKERS):
        match = CAREER_LEADING_PERSON.search(keyword.query.strip())
        query_people = [match.group("person")] if match is not None else []
    before = ranked
    ranked = _career_relevant_hits(ranked, query=keyword.query, query_people=query_people)
    _record_stage(
        trace, stage="career_filter", query=keyword.query, hits=ranked, started=started,
        before=before, reason="no_direct_person_role_change",
    )
    # A page may yield several adjacent chunks. One result per physical page gives
    # the answer layer a broader, less repetitive evidence set.
    started = _stage_start(trace)
    preferred_ids = {hit.chunk_id for hit in _best_congress_hits(ranked, keyword.query)}
    unique_by_page: dict[tuple[str, int], SearchHit] = {}
    for hit in ranked:
        page_key = (hit.document_id, hit.pdf_page_start)
        existing = unique_by_page.get(page_key)
        if existing is None or (
            hit.chunk_id in preferred_ids and existing.chunk_id not in preferred_ids
        ):
            unique_by_page[page_key] = hit
    unique_pages = sorted(unique_by_page.values(), key=lambda hit: ranked.index(hit))
    _record_stage(
        trace, stage="page_deduplication", query=keyword.query,
        hits=unique_pages, started=started, before=ranked, reason="same_document_pdf_page",
        notes=["Congress evidence preference can replace an earlier chunk from the same page."],
    )

    started = _stage_start(trace)
    congress_covered = _select_with_congress_coverage(
        unique_pages, query=keyword.query, top_k=top_k
    )
    _record_stage(
        trace, stage="congress_coverage", query=keyword.query,
        hits=congress_covered, started=started, before=unique_pages,
        reason="outside_congress_coverage_selection",
    )
    started = _stage_start(trace)
    selected = _select_with_temporal_coverage(
        congress_covered,
        query=keyword.query,
        query_year_range=keyword.query_year_range,
        top_k=top_k,
        coverage=coverage,
    )
    for rank, hit in enumerate(selected, start=1):
        hit.rank = rank
    _record_stage(
        trace, stage="final", query=keyword.query, hits=selected, started=started,
        before=congress_covered, reason="outside_coverage_or_top_k", requested_k=top_k,
        notes=[f"Temporal coverage policy: {coverage}; final result selection."],
    )

    return SearchResponse(
        query=keyword.query,
        query_intent=keyword.query_intent,
        query_terms=keyword.query_terms,
        query_years=keyword.query_years,
        query_year_range=keyword.query_year_range,
        query_people=query_people,
        document_filters=keyword.document_filters,
        include_out_of_scope=keyword.include_out_of_scope,
        hits=selected,
        retrieval_mode="hybrid_rrf",
        trace=trace,
    )


def _single_branch_response(
    response: SearchResponse,
    *,
    branch: str,
    failed: str,
    top_k: int,
    coverage: str,
    trace: list[RetrievalStageTrace] | None = None,
) -> SearchResponse:
    started = _stage_start(trace)
    hits: list[SearchHit] = []
    for hit in response.hits:
        updates: dict[str, object] = {
            "keyword_rank": hit.rank if branch == "keyword" else None,
            "vector_rank": hit.rank if branch == "vector" else None,
        }
        hits.append(hit.model_copy(update=updates))
    query_people = response.query_people
    if not query_people and any(marker in response.query for marker in CAREER_QUERY_MARKERS):
        match = CAREER_LEADING_PERSON.search(response.query.strip())
        query_people = [match.group("person")] if match is not None else []
    before = hits
    hits = _career_relevant_hits(hits, query=response.query, query_people=query_people)
    _record_stage(
        trace, stage="career_filter", query=response.query, hits=hits, started=started,
        before=before, reason="no_direct_person_role_change",
        notes=[f"Only {branch} available; no RRF, source bonus or page deduplication executed."],
    )
    started = _stage_start(trace)
    selected = _select_with_temporal_coverage(
        hits,
        query=response.query,
        query_year_range=response.query_year_range,
        top_k=top_k,
        coverage=coverage,
    )
    for rank, hit in enumerate(selected, start=1):
        hit.rank = rank
    _record_stage(
        trace, stage="final", query=response.query, hits=selected, started=started,
        before=hits, reason="outside_coverage_or_top_k", requested_k=top_k,
        notes=[f"Temporal coverage policy: {coverage}; degraded {branch}-only selection."],
    )
    return response.model_copy(
        update={
            "hits": selected,
            "query_people": query_people,
            "retrieval_mode": f"{branch}_only",
            "degraded_components": [failed],
            "trace": trace,
        }
    )


def _search_one(
    *,
    keyword_index_path: Path | str,
    vector_index_path: VectorIndexTarget,
    model_cache_dir: Path,
    aliases_path: Path,
    query: str,
    top_k: int,
    document_ids: list[str] | None,
    include_out_of_scope: bool,
    plan: RetrievalPlan | None,
    candidate_k: int | None = None,
    capture_trace: bool = False,
) -> SearchResponse:
    congress_count = len(cpc_congress_ordinals(query))
    branch_k = (
        candidate_k if candidate_k is not None
        else min(100, max(30, top_k * 4, congress_count * 12))
    )
    search_query = expand_query(query)
    keyword_trace: list[RetrievalStageTrace] | None = [] if capture_trace else None
    vector_trace: list[RetrievalStageTrace] | None = [] if capture_trace else None
    keyword: SearchResponse | None = None
    vector: SearchResponse | None = None
    keyword_error: Exception | None = None
    vector_error: Exception | None = None

    def keyword_branch() -> SearchResponse:
        started = _stage_start(keyword_trace)
        try:
            result = search_keyword_index(
                index_path=keyword_index_path,
                query=search_query,
                aliases_path=aliases_path,
                top_k=branch_k,
                document_ids=document_ids,
                include_out_of_scope=include_out_of_scope,
                plan=plan,
            )
        except Exception as exc:
            _record_stage(
                keyword_trace, stage="keyword_candidates", query=search_query, hits=[],
                started=started, requested_k=branch_k, status="failed",
                notes=[f"Backend failed: {type(exc).__name__}"],
            )
            raise
        _record_stage(
            keyword_trace, stage="keyword_candidates", query=search_query,
            hits=result.hits, started=started, requested_k=branch_k,
            notes=["Backend-returned keyword order includes existing BM25/source rules."],
        )
        congress_hits: list[SearchHit] = []
        if congress_count >= 2:
            for ordinal in cpc_congress_ordinals(query):
                formal_name = f"中国共产党第{ordinal}次全国代表大会"
                targeted_k = min(24, candidate_k) if candidate_k is not None else 24
                started = _stage_start(keyword_trace)
                try:
                    targeted = search_keyword_index(
                        index_path=keyword_index_path,
                        query=formal_name,
                        aliases_path=aliases_path,
                        top_k=targeted_k,
                        document_ids=document_ids,
                        include_out_of_scope=include_out_of_scope,
                        section_path_contains=f"第{ordinal}次全国代表大会",
                        plan=plan,
                    )
                except Exception as exc:
                    _record_stage(
                        keyword_trace, stage="keyword_targeted_candidates", query=formal_name,
                        hits=[], started=started, requested_k=targeted_k, status="failed",
                        notes=[f"Extra congress lookup failed: {type(exc).__name__}"],
                    )
                    raise
                _record_stage(
                    keyword_trace, stage="keyword_targeted_candidates", query=formal_name,
                    hits=targeted.hits, started=started, requested_k=targeted_k,
                    notes=[
                        f"Additional congress lookup beyond main candidate_k={branch_k}; "
                        f"section filter: 第{ordinal}次全国代表大会.",
                    ],
                )
                best_hits = _best_congress_hits(targeted.hits, query)
                if best_hits:
                    congress_hits.append(best_hits[0])
            started = _stage_start(keyword_trace)
            before = [*congress_hits, *result.hits]
            result = _prepend_congress_keyword_hits(result, congress_hits)
            if candidate_k is not None:
                result = result.model_copy(update={"hits": result.hits[:candidate_k]})
            _record_stage(
                keyword_trace, stage="keyword_candidates_augmented", query=search_query,
                hits=result.hits, started=started, before=before,
                reason="outside_augmented_candidate_budget", requested_k=candidate_k,
                notes=[
                    "Prepended one selected hit per congress and merged duplicate chunk IDs.",
                    f"Extra keyword lookups: {congress_count}; "
                    f"requested hits per extra lookup: {targeted_k}.",
                    "Fixed candidate_k caps the augmented branch output; "
                    "it does not cap the sum of main and congress backend requests."
                    if candidate_k is not None else
                    "Legacy congress expansion can exceed the main branch candidate budget.",
                ],
            )
        return result

    def vector_branch() -> SearchResponse:
        started = _stage_start(vector_trace)
        try:
            result = search_vector_index(
                index_path=vector_index_path,
                model_cache_dir=model_cache_dir,
                aliases_path=aliases_path,
                query=search_query,
                top_k=branch_k,
                document_ids=document_ids,
                include_out_of_scope=include_out_of_scope,
                plan=plan,
            )
        except Exception as exc:
            _record_stage(
                vector_trace, stage="vector_candidates", query=search_query, hits=[],
                started=started, requested_k=branch_k, status="failed",
                notes=[f"Backend failed: {type(exc).__name__}"],
            )
            raise
        notes = ["Backend-returned vector order; internal candidates are not exposed here."]
        if (
            result.query_years and result.query_intent == "timeline"
            and not (bool(plan and plan.query_year_range) or has_explicit_year_range(search_query))
        ):
            notes.append(
                "Native vector backend internally requests "
                f"{min(500, max(100, branch_k * 20))} points for exact-year heading preference "
                f"before returning at most {branch_k}; internal ranking is unobserved."
            )
        _record_stage(
            vector_trace, stage="vector_candidates", query=search_query,
            hits=result.hits, started=started, requested_k=branch_k, notes=notes,
        )
        return result

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieval") as executor:
        keyword_future = executor.submit(keyword_branch)
        vector_future = executor.submit(vector_branch)
        try:
            keyword = keyword_future.result()
        except Exception as exc:
            keyword_error = exc
            logger.warning(
                "keyword retrieval degraded",
                extra={"context": {"error": type(exc).__name__}},
            )
        try:
            vector = vector_future.result()
        except Exception as exc:
            vector_error = exc
            logger.warning(
                "vector retrieval degraded",
                extra={"context": {"error": type(exc).__name__}},
            )
    coverage = plan.coverage if plan is not None else "auto"
    trace = [*(keyword_trace or []), *(vector_trace or [])] if capture_trace else None
    if keyword is not None and vector is not None:
        return fuse_search_responses(keyword, vector, top_k=top_k, coverage=coverage, trace=trace)
    if keyword is not None:
        return _single_branch_response(
            keyword, branch="keyword", failed="vector", top_k=top_k, coverage=coverage,
            trace=trace,
        )
    if vector is not None:
        return _single_branch_response(
            vector, branch="vector", failed="keyword", top_k=top_k, coverage=coverage,
            trace=trace,
        )
    cause = vector_error or keyword_error
    raise RetrievalError("Keyword and vector retrieval are both unavailable.") from cause


def _fuse_query_variants(
    responses: list[SearchResponse],
    *,
    query: str,
    top_k: int,
    plan: RetrievalPlan,
    trace: list[RetrievalStageTrace] | None = None,
) -> SearchResponse:
    started = _stage_start(trace)
    by_chunk: dict[str, SearchHit] = {}
    scores: dict[str, float] = {}
    for response in responses:
        for hit in response.hits:
            current = by_chunk.get(hit.chunk_id)
            if current is None:
                current = hit.model_copy(deep=True)
                by_chunk[hit.chunk_id] = current
                scores[hit.chunk_id] = 0.0
            else:
                ranks = [rank for rank in (current.keyword_rank, hit.keyword_rank) if rank]
                current.keyword_rank = min(ranks) if ranks else None
                ranks = [rank for rank in (current.vector_rank, hit.vector_rank) if rank]
                current.vector_rank = min(ranks) if ranks else None
            scores[hit.chunk_id] += 1.0 / (RRF_K + hit.rank)
    ranked = sorted(
        by_chunk.values(),
        key=lambda hit: (-scores[hit.chunk_id], hit.pdf_page_start, hit.chunk_id),
    )
    if trace is not None:
        _record_stage(
            trace, stage="variants_rrf_fusion", query=query,
            hits=_rrf_snapshot(ranked, scores), started=started,
            before=[hit for response in responses for hit in response.hits],
            notes=["RRF over each query's already-selected results, not raw branch candidates."],
        )
    started = _stage_start(trace)
    query_people = responses[0].query_people or plan.query_people
    if not query_people and any(marker in query for marker in CAREER_QUERY_MARKERS):
        person_match = CAREER_LEADING_PERSON.search(query.strip())
        query_people = [person_match.group("person")] if person_match is not None else []
    before = ranked
    ranked = _career_relevant_hits(ranked, query=query, query_people=query_people)
    _record_stage(
        trace, stage="variants_career_filter", query=query,
        hits=_rrf_snapshot(ranked, scores) if trace is not None else ranked,
        started=started, before=before, reason="no_direct_person_role_change",
    )
    started = _stage_start(trace)
    unique_pages: list[SearchHit] = []
    pages: set[tuple[str, int]] = set()
    for hit in ranked:
        page = (hit.document_id, hit.pdf_page_start)
        if page not in pages:
            pages.add(page)
            unique_pages.append(hit)
    _record_stage(
        trace, stage="variants_page_deduplication", query=query,
        hits=_rrf_snapshot(unique_pages, scores) if trace is not None else unique_pages,
        started=started, before=ranked, reason="same_document_pdf_page",
    )
    started = _stage_start(trace)
    if plan.coverage == "per_item":
        reserved: list[SearchHit] = []
        reserved_ids: set[str] = set()
        for response in responses[1:]:
            match = next((hit for hit in response.hits if hit.chunk_id not in reserved_ids), None)
            if match is not None:
                reserved.append(by_chunk[match.chunk_id])
                reserved_ids.add(match.chunk_id)
        selected = reserved[:top_k]
        selected.extend(hit for hit in unique_pages if hit.chunk_id not in reserved_ids)
        selected = selected[:top_k]
    else:
        selected = _select_with_temporal_coverage(
            unique_pages,
            query=query,
            query_year_range=plan.query_year_range,
            top_k=top_k,
            coverage=plan.coverage,
        )
    for rank, hit in enumerate(selected, start=1):
        hit.rank = rank
        hit.rrf_score = round(scores[hit.chunk_id], 8)
        hit.score = hit.rrf_score
    _record_stage(
        trace, stage="final", query=query, hits=selected, started=started,
        before=unique_pages, reason="outside_coverage_or_top_k", requested_k=top_k,
        notes=[
            f"Query-variant merge coverage policy: {plan.coverage}; final retrieval selection.",
            "Per-item reservations may reintroduce a same-page chunk from a query result."
            if plan.coverage == "per_item" else "No per-item reservations applied.",
        ],
    )
    degraded = sorted(
        {component for response in responses for component in response.degraded_components}
    )
    coverage_gaps = [
        response.query
        for response in responses[1:]
        if not response.hits
        or (
            "keyword" not in response.degraded_components
            and not any(hit.keyword_rank is not None for hit in response.hits)
        )
    ]
    return SearchResponse(
        query=query,
        query_intent=plan.query_intent,
        query_terms=list(dict.fromkeys(term for item in responses for term in item.query_terms)),
        query_years=plan.query_years,
        query_year_range=plan.query_year_range,
        query_people=query_people,
        document_filters=responses[0].document_filters,
        include_out_of_scope=responses[0].include_out_of_scope,
        hits=selected,
        retrieval_mode="planned_hybrid_rrf",
        degraded_components=degraded,
        coverage_gaps=coverage_gaps,
        trace=trace,
    )


def search_hybrid_index(
    *,
    keyword_index_path: Path | str,
    vector_index_path: VectorIndexTarget,
    model_cache_dir: Path,
    aliases_path: Path,
    query: str,
    top_k: int = 10,
    document_ids: list[str] | None = None,
    include_out_of_scope: bool = False,
    plan: RetrievalPlan | None = None,
    additional_queries: list[str] | None = None,
    candidate_k: int | None = None,
    capture_trace: bool = False,
) -> SearchResponse:
    """Retrieve with optional fixed branch budgets and immutable stage snapshots.

    candidate_k is per query and per main retrieval branch, not a global budget:
    congress lookups and native exact-year vector overfetch are recorded in trace
    notes when capture_trace is enabled. No prompt construction is traced here.
    """
    if candidate_k is not None and (
        not isinstance(candidate_k, int) or isinstance(candidate_k, bool)
        or not 1 <= candidate_k <= 100 or candidate_k < top_k
    ):
        raise RetrievalError("candidate_k must be an integer in 1..100 and >= top_k.")
    queries = list(dict.fromkeys([query, *(additional_queries or [])]))
    responses = [
        _search_one(
            keyword_index_path=keyword_index_path,
            vector_index_path=vector_index_path,
            model_cache_dir=model_cache_dir,
            aliases_path=aliases_path,
            query=item,
            top_k=top_k,
            document_ids=document_ids,
            include_out_of_scope=include_out_of_scope,
            plan=plan,
            candidate_k=candidate_k,
            capture_trace=capture_trace,
        )
        for item in queries
    ]
    trace = None
    if capture_trace and len(responses) > 1:
        trace = [
            stage.model_copy(update={"stage": "query_final"})
            if stage.stage == "final" else stage
            for response in responses for stage in response.trace or []
        ]
    if plan is not None and len(responses) > 1:
        return _fuse_query_variants(responses, query=query, top_k=top_k, plan=plan, trace=trace)
    if trace is not None:
        started = _stage_start(trace)
        _record_stage(
            trace, stage="final", query=query, hits=responses[0].hits,
            started=started, requested_k=top_k,
            notes=["No retrieval plan: additional queries executed but were not merged "
                   "(existing production behavior); returning the primary query's results."],
        )
        return responses[0].model_copy(update={"query": query, "trace": trace})
    return responses[0].model_copy(update={"query": query})
