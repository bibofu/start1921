"""Evaluate query understanding with the rule baseline and the LLM planner."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from history_agent.config import get_settings
from history_agent.evaluation.query_understanding_eval import (
    evaluate,
    load_dataset,
    predict_with_llm,
    predict_with_rules,
    render_markdown,
)
from history_agent.log import log_event

LOGGER = logging.getLogger(__name__)
DEFAULT_CASES = Path("evals/query_understanding/cases.json")
DEFAULT_OUTPUT = Path("evals/query_understanding/baselines")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--aliases", type=Path, default=Path("config/person_aliases.json"))
    parser.add_argument("--mode", choices=["rules", "llm", "both"], default="rules")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    settings = get_settings()
    dataset = load_dataset(args.cases)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    modes = ["rules", "llm"] if args.mode == "both" else [args.mode]
    summary: dict[str, object] = {"version": dataset.version, "cases": len(dataset.cases)}
    for mode in modes:
        predictions = {}
        for case in dataset.cases:
            rules = predict_with_rules(case, args.aliases)
            predictions[case.id] = (
                predict_with_llm(settings, case, rules) if mode == "llm" else rules
            )
        result = evaluate(dataset.cases, predictions)
        (args.output_dir / f"{mode}.json").write_text(
            json.dumps(
                {
                    "mode": mode,
                    "version": dataset.version,
                    "result": result,
                    "predictions": {
                        case_id: prediction.model_dump()
                        for case_id, prediction in predictions.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        title = "查询理解基线：规则" if mode == "rules" else "查询理解基线：LLM 规划器"
        (args.output_dir / f"{mode}.md").write_text(
            render_markdown(title, result), encoding="utf-8"
        )
        summary[mode] = {
            "intent_accuracy": result["intent_accuracy"],
            "route_accuracy": result["route_accuracy"],
            "mention_f1": result["mention"]["f1"],
            "time_exact_accuracy": result["time"]["exact_accuracy"],
            "clarification_f1": result["clarification"]["f1"],
        }
        print(mode, summary[mode])

    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log_event(LOGGER, logging.INFO, "query_understanding_evaluated", modes=modes)


if __name__ == "__main__":
    main()
