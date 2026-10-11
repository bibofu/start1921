"""Load development protocols without changing annotation or Agent contracts.

Schema 2 is a frozen annotation release, not a legacy PilotDataset. It can only
be executed through a caller that explicitly supplies its bound protocol file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from history_agent.answering.models import QuestionRequest
from history_agent.evaluation.pilot_answers import fingerprint
from history_agent.evaluation.pilot_models import PilotCase, PilotDataset, case_definition

CONTRACT_VERSION = "development-protocol-execution-v1"
HISTORY_CASE_ID = "dev_constraint_history_isolation"
HUNAN_CASE_ID = "dev_multi_mao_hunan"
_STAGES = {
    "query_understanding",
    "routing",
    "retrieval",
    "ranking",
    "context",
    "answer",
    "citation",
    "refusal",
    "cost",
}
_RELEASE_FIELDS = {
    "schema_version",
    "case_schema_version",
    "version",
    "description",
    "annotation_status",
    "execution_status",
    "execution_note",
    "protocols_file",
    "historical_executable_dataset",
    "evidence_group_semantics",
    "cases",
}
_DEVELOPMENT_CASE_IDS = {
    "pilot_exact_deng_1952_appointment",
    "pilot_semantic_deng_1962_agriculture",
    "pilot_multievidence_zunyi_leadership",
    "pilot_negative_cppcc_1949",
    "pilot_constraint_deng_1973_march",
    "pilot_refusal_out_of_scope_2024",
    "dev_exact_zhou_1954",
    "dev_exact_deng_1954",
    "dev_constraint_month_place",
    "dev_multi_zhou_periods",
    "dev_semantic_investigation",
    "dev_semantic_contradiction",
    "dev_semantic_first_congress",
    "dev_exact_zunyi_election",
    "dev_multi_meetings",
    HISTORY_CASE_ID,
    HUNAN_CASE_ID,
    "dev_intersection_mao_zhou_1949",
    "dev_refusal_einstein",
    "dev_refusal_source_year",
}


@dataclass(frozen=True)
class EvaluationInputs:
    dataset: PilotDataset
    dataset_sha256: str
    protocols: dict[str, Any] | None
    protocol_file_sha256: str | None
    protocol_sha256: str | None
    variants: dict[str, list[dict[str, Any]]]
    is_protocol_release: bool


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(value, dict):
        raise ValueError("evaluation input must be a JSON object")
    return value


def _variants(case: PilotCase, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    variants = protocol.get("input_variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError(f"missing input variants: {case.id}")
    ids = []
    for variant in variants:
        if not isinstance(variant, dict) or set(variant) != {"id", "question", "history"}:
            raise ValueError(f"unknown or missing input fields: {case.id}")
        if not isinstance(variant["id"], str) or not variant["id"].strip():
            raise ValueError(f"invalid input variant ID: {case.id}")
        ids.append(variant["id"])
        if variant["question"] != case.question or not isinstance(variant["history"], list):
            raise ValueError(f"input question/history differs: {case.id}")
        for message in variant["history"]:
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                raise ValueError(f"unknown or missing history fields: {case.id}")
        QuestionRequest(question=variant["question"], history=variant["history"])
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate input variant IDs: {case.id}")
    if protocol.get("independent_case_count") != 1:
        raise ValueError(f"each protocol must represent one independent case: {case.id}")
    if case.id != HISTORY_CASE_ID:
        if variants != [{"id": "single_turn", "question": case.question, "history": []}]:
            raise ValueError(f"single-turn input must preserve the selected question: {case.id}")
        return variants

    specialist = protocol.get("specialist_protocol") or {}
    conversation = specialist.get("conversation_protocol") or {}
    treatment, control = conversation.get("treatment", {}), conversation.get("control", {})
    expected_history = [{"role": "user", "content": "林彪在1930—1949年相继担任哪些职务？"}]
    expected = [
        {"id": "with_history", "question": case.question, "history": expected_history},
        {"id": "without_history_control", "question": case.question, "history": []},
    ]
    if variants != expected:
        raise ValueError("history isolation requires the exact treatment and control inputs")
    if treatment != {"conversation_history": expected_history, "question": case.question}:
        raise ValueError("history treatment differs from conversation protocol")
    if control != {"conversation_history": [], "question": case.question}:
        raise ValueError("history control differs from conversation protocol")
    if (
        conversation.get("required") is not True
        or conversation.get("no_assistant_history_fabrication") is not True
        or conversation.get("isolation_denominator") != 4
        or len(conversation.get("primary_isolation_checks", [])) != 4
    ):
        raise ValueError("history isolation protocol must preserve its four explicit checks")
    return variants


def _validate_hunan(case: PilotCase, protocol: dict[str, Any]) -> None:
    specialist = protocol.get("specialist_protocol") or {}
    boundary = specialist.get("answer_boundary") or {}
    year_rows = boundary.get("years", [])
    years = [row.get("year") for row in year_rows]
    if years != list(range(1921, 1927)) or boundary.get("year_coverage_denominator") != 6:
        raise ValueError("Hunan requires six ordered year partitions, 1921 through 1926")
    required_facts = [fact.id for fact in case.facts if fact.required]
    required_groups = [group.id for group in case.evidence_groups]
    all_facts: list[str] = []
    all_groups: list[str] = []
    expected_counts = {1921: 2, 1922: 2, 1923: 2, 1924: 1, 1925: 5, 1926: 2}
    for row in year_rows:
        year = row["year"]
        facts, groups = row.get("required_fact_ids", []), row.get("required_evidence_group_ids", [])
        if len(facts) != expected_counts[year] or len(groups) != expected_counts[year]:
            raise ValueError(f"Hunan year denominator changed: {year}")
        if any(not fact.startswith(f"y{year}_") for fact in facts + groups):
            raise ValueError(f"Hunan evidence assigned to the wrong year: {year}")
        if row.get("absence_claim_allowed") is not False:
            raise ValueError(f"Hunan positive-evidence year cannot permit absence claims: {year}")
        all_facts.extend(facts)
        all_groups.extend(groups)
    if all_facts != required_facts or all_groups != required_groups:
        raise ValueError("Hunan year partitions must cover every fact and evidence group once")
    year_coverage = protocol.get("year_coverage") or {}
    if year_coverage.get("years") != years or year_coverage.get("denominator") != 6:
        raise ValueError("Hunan year coverage denominator differs")
    stages = specialist.get("stage_criteria") or {}
    recall = stages.get("recall") or {}
    if recall.get("per_year_recall_denominators") != {
        str(year): count for year, count in expected_counts.items()
    }:
        raise ValueError("Hunan per-year retrieval denominators differ")
    if (recall.get("year_hit_rate") or {}).get("denominator") != 6:
        raise ValueError("Hunan year hit rate requires six years")
    final_answer = stages.get("final_answer") or {}
    if (
        final_answer.get("fact_coverage_denominator") != 14
        or final_answer.get("year_completeness_denominator") != 6
    ):
        raise ValueError("Hunan answer fact/year denominators differ")


def _development_dataset(payload: dict[str, Any], protocols: dict[str, Any]) -> PilotDataset:
    if set(payload) != _RELEASE_FIELDS:
        raise ValueError("unknown or missing development release fields")
    if (
        payload.get("case_schema_version") != 1
        or payload.get("execution_status") != "annotation_only"
    ):
        raise ValueError("unsupported development annotation release contract")
    if protocols.get("schema_version") != 1 or protocols.get("annotation_sha256") != fingerprint(
        payload
    ):
        raise ValueError("protocols refer to a different annotation release")
    dataset = PilotDataset(
        schema_version=1,
        version=payload["version"],
        description=payload["description"],
        annotation_status=payload["annotation_status"],
        evidence_group_semantics=payload["evidence_group_semantics"],
        cases=payload["cases"],
    )
    cases = dataset.cases
    ids = {case.id for case in cases}
    if len(cases) != 20 or ids != _DEVELOPMENT_CASE_IDS:
        raise ValueError("development release requires the 20 selected development cases")
    raw_protocols = protocols.get("cases")
    if not isinstance(raw_protocols, list):
        raise ValueError("development protocols require case records")
    by_id = {row["case_id"]: row for row in raw_protocols}
    if len(by_id) != len(raw_protocols) or set(by_id) != ids:
        raise ValueError("protocols must cover every development case exactly once")
    if protocols.get("k_values") != [1, 3, 5, 10, 20]:
        raise ValueError("development protocol K values differ")
    for case in cases:
        protocol = by_id[case.id]
        if protocol.get("case_definition_sha256") != fingerprint(
            case_definition(case.model_dump(mode="json"))
        ):
            raise ValueError(f"stale protocol case definition: {case.id}")
        facts = [fact.id for fact in case.facts if fact.required]
        groups = [group.id for group in case.evidence_groups]
        if protocol.get("required_fact_ids") != facts:
            raise ValueError(f"fact denominator differs: {case.id}")
        if protocol.get("required_evidence_group_ids") != groups:
            raise ValueError(f"evidence denominator differs: {case.id}")
        stages = protocol.get("stages") or {}
        if set(stages) != _STAGES:
            raise ValueError(f"incomplete stage protocol: {case.id}")
        if case.answerability == "answerable":
            for stage, count in (
                ("retrieval", len(groups)),
                ("context", len(groups)),
                ("answer", len(facts)),
                ("citation", len(facts)),
            ):
                if stages[stage].get("denominator") != count:
                    raise ValueError(f"stage denominator differs: {case.id}/{stage}")
        else:
            for stage in ("retrieval", "ranking"):
                if stages[stage].get("denominator") is not None:
                    raise ValueError(f"refusal has no positive ranking denominator: {case.id}")
            if not case.refusal_basis:
                raise ValueError(f"refusal requires explicit boundary evidence: {case.id}")
        if protocol.get("source_scope_kind") not in {
            "annotation_sources_not_exclusive",
            "hard_user_constraint",
        }:
            raise ValueError(f"unsupported source scope kind: {case.id}")
        _variants(case, protocol)
        if case.id == HUNAN_CASE_ID:
            _validate_hunan(case, protocol)
    return dataset


def load_inputs(dataset_path: Path, protocol_path: Path | None = None) -> EvaluationInputs:
    """Preserve legacy normalized hashes and bind schema 2 to its entire frozen package."""
    payload = _read(dataset_path)
    protocols = _read(protocol_path) if protocol_path is not None else None
    release = payload.get("schema_version") == 2
    if release:
        if protocols is None:
            raise ValueError("schema 2 development release requires explicit --protocols")
        dataset = _development_dataset(payload, protocols)
        by_id = {row["case_id"]: row for row in protocols["cases"]}
        variants = {case.id: _variants(case, by_id[case.id]) for case in dataset.cases}
        if sum(map(len, variants.values())) != 21:
            raise ValueError("development release requires 20 independent cases and 21 inputs")
        dataset_sha256 = fingerprint(payload)
    else:
        dataset = PilotDataset.model_validate(payload)
        dataset_sha256 = fingerprint(dataset.model_dump(mode="json"))
        variants = {
            case.id: [{"id": "single_turn", "question": case.question, "history": []}]
            for case in dataset.cases
        }
    return EvaluationInputs(
        dataset=dataset,
        dataset_sha256=dataset_sha256,
        protocols=protocols,
        protocol_file_sha256=(
            hashlib.sha256(protocol_path.read_bytes()).hexdigest() if protocol_path else None
        ),
        protocol_sha256=fingerprint(protocols) if protocols is not None else None,
        variants=variants,
        is_protocol_release=release,
    )


def capture_contract(inputs: EvaluationInputs) -> dict[str, Any]:
    """Immutable execution intent, including both arms before any Agent call."""
    return {
        "schema_version": 1,
        "execution_contract_version": CONTRACT_VERSION,
        "is_protocol_release": inputs.is_protocol_release,
        "dataset_sha256": inputs.dataset_sha256,
        "protocol_sha256": inputs.protocol_sha256,
        "protocol_file_sha256": inputs.protocol_file_sha256,
        "protocol_version": inputs.protocols.get("version") if inputs.protocols else None,
        "independent_case_count": len(inputs.dataset.cases),
        "execution_input_count": sum(map(len, inputs.variants.values())),
        "input_variants": {
            case_id: [
                {
                    **variant,
                    "input_sha256": fingerprint(
                        {
                            "question": variant["question"],
                            "history": variant["history"],
                        }
                    ),
                }
                for variant in variants
            ]
            for case_id, variants in inputs.variants.items()
        },
    }
