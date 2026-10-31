"""Fail a build when runtime configuration or frontend assets are missing.

Runs without a database, model downloads, or API credentials, as the same user
that serves requests. This catches an incomplete Docker COPY/build context even
when unit tests pass against a complete source checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

from history_agent.answering.entity_linking import load_entities, normalize_entities
from history_agent.corpus.catalog import load_catalog


def check_image(root: Path) -> None:
    config = root / "config"
    if not load_catalog(config / "corpus_catalog.json").documents:
        raise ValueError("The packaged corpus catalog is empty")
    for filename in ("person_aliases.json", "query_aliases.json", "relation_types.json"):
        json.loads((config / filename).read_text(encoding="utf-8"))

    entities = load_entities(config / "entities" / "entities.jsonl")
    manifest = json.loads((config / "entities" / "manifest.json").read_text(encoding="utf-8"))
    if not entities or len(entities) != manifest["records"]:
        raise ValueError("The packaged entity index does not match its manifest")
    if normalize_entities("毛选和党史", entities) != "毛泽东选集和中国共产党历史":
        raise ValueError("The packaged entity aliases cannot be resolved")

    static = root / "app" / "history_agent" / "web" / "static"
    for filename in ("index.html", "app.css", "app.js", "markdown.js", "stream.js"):
        if not (static / filename).read_bytes():
            raise ValueError(f"Empty packaged frontend asset: {filename}")


if __name__ == "__main__":
    check_image(Path(__file__).resolve().parents[1])
    print("Packaged runtime configuration, entity aliases and frontend assets are readable.")
