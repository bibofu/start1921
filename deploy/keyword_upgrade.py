"""Versioned keyword-index migration for a locked application rollout.

Run inside the candidate image with production mounts and settings. Old
generations remain available so image rollback can also restore its index.
"""

from __future__ import annotations

import argparse
import json
import time

from history_agent.config import get_settings
from history_agent.db_backend import database_connection
from history_agent.retrieval.keyword_postgres import INDEX_VERSION, build_keyword_index


def index_state() -> dict[str, object]:
    settings = get_settings()
    with database_connection(settings.keyword_index_target) as connection:
        row = connection.execute(
            "SELECT g.generation_id, g.index_version, g.chunks_count "
            "FROM keyword_active a JOIN keyword_generations g USING(generation_id) "
            "WHERE a.singleton=1"
        ).fetchone()
        if row is None or int(row[2]) <= 0:
            raise ValueError("A populated keyword generation is required before deployment")
        return {
            "generation_id": int(row[0]), "index_version": row[1],
            "chunks_count": int(row[2]), "expected_version": INDEX_VERSION,
            "needs_upgrade": row[1] != INDEX_VERSION,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "upgrade", "restore"))
    parser.add_argument("--generation", type=int)
    args = parser.parse_args()
    settings = get_settings()
    before = index_state()
    if args.action == "upgrade" and before["needs_upgrade"]:
        build_keyword_index(
            chunks_dir=settings.chunks_dir, index_path=settings.keyword_index_target,
            reports_dir=settings.reports_dir,
            run_id=f"release_keyword_{time.time_ns()}", project_root=settings.project_root,
        )
    elif args.action == "restore":
        if args.generation is None or args.generation <= 0:
            raise ValueError("A positive rollback generation is required")
        with database_connection(settings.keyword_index_target) as connection:
            row = connection.execute(
                "SELECT chunks_count FROM keyword_generations WHERE generation_id=?",
                (args.generation,),
            ).fetchone()
            if row is None or int(row[0]) <= 0:
                raise ValueError("Rollback keyword generation is missing or empty")
            connection.execute(
                "UPDATE keyword_active SET generation_id=? WHERE singleton=1",
                (args.generation,),
            )
    after = index_state()
    if args.action == "upgrade" and after["needs_upgrade"]:
        raise ValueError("Keyword index version still does not match the candidate")
    print(json.dumps(after))


if __name__ == "__main__":
    main()
