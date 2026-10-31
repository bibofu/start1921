"""Build a jieba user dictionary from the project's curated aliases.

Every entry is a real person, organization, event, place, document or congress
name already maintained for entity linking. Generic words and punctuation are
skipped so the tokenizer does not over-segment ordinary prose.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
OUTPUT = CONFIG / "jieba_userdict.txt"

CJK_OR_LATIN = re.compile(r"[㐀-䶿一-鿿A-Za-z]")
CONGRESS_SHORT_ALIAS = re.compile(r"^[一二三四五六七八九十百]+大$")
UNSAFE = set(" \t\r\n()（）[]【】{}<>《》,，。、：:;；!?！？\"'“”‘’/\\|")


def _clean(term: object) -> str | None:
    if not isinstance(term, str):
        return None
    value = term.strip().strip("《》").strip()
    if len(value) < 2 or not CJK_OR_LATIN.search(value):
        return None
    if any(character in UNSAFE for character in value):
        return None
    return value


class Vocabulary:
    def __init__(self) -> None:
        self.entries: dict[str, tuple[int, str]] = {}

    def add(self, term: object, frequency: int, tag: str) -> None:
        value = _clean(term)
        if value is None:
            return
        current = self.entries.get(value)
        if current is None or frequency > current[0]:
            self.entries[value] = (frequency, tag)

    def write(self, path: Path) -> None:
        lines = [
            f"{term} {frequency} {tag}"
            for term, (frequency, tag) in sorted(self.entries.items())
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load(path: Path) -> object:
    if not path.is_file():
        return None
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return json.loads(path.read_text(encoding="utf-8"))


def _add_people(vocabulary: Vocabulary, payload: object) -> None:
    if not isinstance(payload, dict):
        return
    for person in payload.get("people", []):
        vocabulary.add(person.get("canonical_name"), 100_000, "nr")
        for alias in person.get("aliases", []):
            name = alias.get("name") if isinstance(alias, dict) else alias
            vocabulary.add(name, 5_000, "nr")


def _add_named(vocabulary: Vocabulary, payload: object, key: str, tag: str) -> None:
    if not isinstance(payload, dict):
        return
    for item in payload.get(key, []):
        vocabulary.add(item.get("canonical_name"), 80_000, tag)
        for alias in item.get("aliases", []):
            vocabulary.add(alias, 5_000, tag)


def _add_entities(vocabulary: Vocabulary, payload: object) -> None:
    if not isinstance(payload, list):
        return
    for item in payload:
        entity_type = str(item.get("type") or "")
        tag = {"person": "nr", "organization": "nt", "place": "ns"}.get(
            entity_type, "nz"
        )
        vocabulary.add(item.get("canonical"), 80_000, tag)
        for alias in item.get("aliases", []):
            # Bare "一大"/"七大" are ambiguous inside ordinary words
            # (统一大业); the canonical 中共一大 remains.
            if (
                entity_type == "congress"
                and isinstance(alias, str)
                and CONGRESS_SHORT_ALIAS.fullmatch(alias)
            ):
                continue
            vocabulary.add(alias, 3_000, tag)


def _add_documents(vocabulary: Vocabulary, payload: object) -> None:
    if not isinstance(payload, dict):
        return
    for item in payload.get("entries", []):
        vocabulary.add(item.get("title"), 50_000, "nz")
        for alias in item.get("aliases", []):
            vocabulary.add(alias, 3_000, "nz")


def _add_groups(vocabulary: Vocabulary, payload: object) -> None:
    if not isinstance(payload, dict):
        return
    for item in payload.get("groups", []):
        vocabulary.add(item.get("text"), 30_000, "nz")


def _add_query_aliases(vocabulary: Vocabulary, payload: object) -> None:
    if not isinstance(payload, dict):
        return
    for item in payload.get("entries", []):
        vocabulary.add(item.get("canonical"), 50_000, "nz")
        for alias in item.get("aliases", []):
            vocabulary.add(alias, 3_000, "nz")


MANUAL_TERMS = {
    "遵义会议": 80_000,
    "庐山会议": 80_000,
    "淮海战役": 80_000,
    "渡江战役": 80_000,
    "第一二九师": 60_000,
    "西行漫记": 60_000,
    "红军大学": 60_000,
    "中国共产党": 100_000,
    "中国共产党全国代表大会": 60_000,
}


def main() -> None:
    vocabulary = Vocabulary()
    _add_people(vocabulary, _load(CONFIG / "person_aliases.json"))
    _add_people(vocabulary, _load(CONFIG / "entities/extra_persons.json"))
    _add_named(
        vocabulary, _load(CONFIG / "entities/extra_organizations.json"), "organizations", "nt"
    )
    _add_named(vocabulary, _load(CONFIG / "entities/extra_events.json"), "events", "nz")
    _add_named(vocabulary, _load(CONFIG / "entities/extra_places.json"), "places", "ns")
    _add_entities(vocabulary, _load(CONFIG / "entities/entities.jsonl"))
    _add_documents(vocabulary, _load(CONFIG / "entities/document_aliases.json"))
    _add_groups(vocabulary, _load(CONFIG / "entities/group_aliases.json"))
    _add_query_aliases(vocabulary, _load(CONFIG / "query_aliases.json"))
    for term, frequency in MANUAL_TERMS.items():
        vocabulary.add(term, frequency, "nz")
    vocabulary.write(OUTPUT)
    print(f"wrote {len(vocabulary.entries)} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
