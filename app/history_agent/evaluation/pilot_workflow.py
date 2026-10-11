"""Prepare fresh, capture-bound review packets without assigning any judgments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from history_agent.evaluation.pilot_answers import (
    DIMENSIONS,
    AnswerReviews,
    answer_fingerprint,
    fingerprint,
    validate_reviews,
)
from history_agent.evaluation.pilot_models import PilotDataset, case_definition
from history_agent.evaluation.pilot_process_reviews import prepare_process_reviews


def validate_capture_binding(
    cases: list[dict[str, Any]], capture: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    captured = {row["case_id"]: row for row in capture["cases"]}
    if len(captured) != len(capture["cases"]):
        raise ValueError("duplicate capture case IDs")
    if {case["id"] for case in cases} != set(captured):
        raise ValueError("capture and dataset case IDs differ")
    for case in cases:
        if fingerprint(case_definition(case)) != captured[case["id"]]["case_definition_sha256"]:
            raise ValueError(f"question or evidence definition changed: {case['id']}; recollect")
    return captured


def protect_inputs(outputs: list[Path], inputs: list[Path | None]) -> None:
    """Never overwrite an input through a same-path, relative-path or symlink alias."""
    resolved = [path.resolve() for path in outputs]
    if len(set(resolved)) != len(resolved):
        raise ValueError("output paths overlap")
    if set(resolved) & {path.resolve() for path in inputs if path is not None}:
        raise ValueError("output must not overwrite an input artifact")


def prepare_reviews(
    dataset_path: Path,
    capture_path: Path,
    output_dir: Path,
    *,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    dataset = PilotDataset.model_validate(json.loads(dataset_path.read_text(encoding="utf8")))
    cases = [case.model_dump(mode="json") for case in dataset.cases]
    capture = json.loads(capture_path.read_text(encoding="utf8"))
    captured = validate_capture_binding(cases, capture)
    process = prepare_process_reviews(
        cases, capture, fingerprint(dataset.model_dump(mode="json")), protocol_path=protocol_path
    )
    answer_cases = []
    packet_cases = []
    for case in cases:
        raw = captured[case["id"]]
        answer = raw.get("answer")
        if answer is not None:
            answer_cases.append(
                {
                    "case_id": case["id"],
                    "case_definition_sha256": raw["case_definition_sha256"],
                    "answer_sha256": answer_fingerprint(answer),
                    "basis": None,
                    "reviewer": None,
                    "reviewed_at": None,
                    "facts": [
                        {
                            "fact_id": fact["id"],
                            "status": "unknown",
                            "reason": "待逐事实复核",
                            "support_status": "unknown",
                        }
                        for fact in case["facts"]
                    ],
                    "dimensions": {
                        name: {"status": "unknown", "reason": "待本次回答复核"}
                        for name in DIMENSIONS
                    },
                }
            )
        packet_cases.append(
            {
                "case_id": case["id"],
                "definition": case,
                "answer": answer,
                "capture_case_path": f"cases[case_id={case['id']}]",
                "trace_fields": ["production_stages", "generation_contexts", "llm_calls"],
            }
        )
    answers = AnswerReviews.model_validate(
        {"capture_sha256": fingerprint(capture), "cases": answer_cases}
    )
    validate_reviews(answers, capture, cases)
    packet = {
        "schema_version": 1,
        "dataset_path": str(dataset_path.resolve()),
        "capture_path": str(capture_path.resolve()),
        "dataset_sha256": fingerprint(dataset.model_dump(mode="json")),
        "capture_sha256": fingerprint(capture),
        "cases": packet_cases,
    }
    # All validation happens before creating the directory. Never replace a review in progress.
    output_dir.mkdir(parents=True, exist_ok=False)
    files = {
        "answer_reviews.json": answers.model_dump(mode="json"),
        "process_reviews.json": process,
        "review_packet.json": packet,
    }
    for name, payload in files.items():
        (output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
    (output_dir / "README.md").write_text(
        "# 本次运行复核包\n\n"
        "先读 review_packet.json 的题目、必要事实、证据与本次回答，再核对 capture 中的轨迹。\n"
        "answer_reviews.json 用于事实、引用、来源/时间限制、路由和拒答；"
        "process_reviews.json 用于问题理解与检索计划。所有初始判断均为 unknown。\n\n"
        "作出明确判断时填写 basis（agent_review 或 human_review）、reviewer 和带时区的 "
        "reviewed_at，并逐项记录理由。不要更改任何哈希或观测快照来绕过绑定检查。\n"
        "新 capture 必须生成新的复核包；不能沿用旧回答的通过/失败判断。"
        "unknown 可直接评分但结果保持 N/A；人工复核答案不会自动批准整题 Golden。\n\n"
        "使用 pilot score --assessments answer_reviews.json "
        "--process-reviews process_reviews.json；如准备时绑定了协议，"
        "评分时还需传入同一 --protocols。\n",
        encoding="utf8",
    )
    return {"output_dir": str(output_dir), "answer_cases": len(answer_cases), "cases": len(cases)}
