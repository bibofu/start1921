"""Capture fresh production answers for offline check calibration.

The 2026-10-05 capture was produced while delivery-time date repair was still
active, so its surviving answers are exactly the ones that passed (or were
rewritten). Measuring a new date rule on it would be biased. This script runs
the current pipeline, which performs no date validation, and stores the answers
with their citations for offline replay.

Usage:
    python scripts/capture_live_answers.py \
        --questions-from data/reports/eval_observation_20261005/live_capture.json \
        --output data/reports/citation_date_calibration/live_answers.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))

from history_agent.answering.models import QuestionRequest  # noqa: E402
from history_agent.answering.service import answer_question  # noqa: E402
from history_agent.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions-from", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    source = json.loads(args.questions_from.read_text(encoding="utf8"))
    questions = [
        {"case_id": case["case_id"], "question": case["question"]}
        for case in source.get("cases", [])
    ]
    if args.limit:
        questions = questions[: args.limit]

    settings = get_settings()
    rows: list[dict[str, object]] = []
    for index, item in enumerate(questions, start=1):
        started = time.perf_counter()
        print(f"[{index}/{len(questions)}] {item['question']}", flush=True)
        try:
            response = answer_question(settings, QuestionRequest(question=str(item["question"])))
            rows.append(
                {
                    "case_id": item["case_id"],
                    "question": item["question"],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    "response": response.model_dump(mode="json"),
                }
            )
            print(
                f"    mode={response.generator_mode} citations={len(response.citations)} "
                f"chars={len(response.answer)}",
                flush=True,
            )
        except Exception as exc:  # keep going; a failed case is data too
            rows.append(
                {
                    "case_id": item["case_id"],
                    "question": item["question"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"    FAILED {type(exc).__name__}: {exc}", flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"model": settings.llm_model, "cases": rows}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf8",
        )
    print(f"wrote {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
