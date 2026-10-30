"""Build the v1 entity index from catalogs and processed chunks.

The index is query-side only: it powers mention detection and anchoring. It
does not change the runtime person filter catalog or the retrieval index.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(".")
CONFIG = ROOT / "config"
ENTITIES = CONFIG / "entities"
CHUNKS = ROOT / "data/processed/chunks"
OUTPUT = ENTITIES / "entities.jsonl"
MANIFEST = ENTITIES / "manifest.json"

ORDINALS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
            "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八",
            "十九", "二十"]
NUMBER = {ordinal: number for number, ordinal in enumerate(ORDINALS, start=1)}
CONGRESS_SECTION = re.compile(r"第([一二三四五六七八九十]+)次全国代表大会")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_document(documents: Counter[str], document_id: str) -> None:
    documents[document_id] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    personas = _load(CONFIG / "person_aliases.json")["people"]
    extras = _load(ENTITIES / "extra_persons.json")["people"]
    groups = _load(ENTITIES / "group_aliases.json")["groups"]
    document_aliases = {
        entry["title"]: entry.get("aliases", [])
        for entry in _load(ENTITIES / "document_aliases.json")["entries"]
    }
    catalog = _load(CONFIG / "corpus_catalog.json")["documents"]
    events = _load(ENTITIES / "extra_events.json")["events"]
    places = _load(ENTITIES / "extra_places.json")["places"]
    organizations = _load(ENTITIES / "extra_organizations.json")["organizations"]
    extra_documents = _load(ENTITIES / "extra_documents.json")["documents"]

    person_ids: dict[str, str] = {}
    person_aliases: dict[str, list[str]] = {}
    for item in [*personas, *extras]:
        canonical = item["canonical_name"]
        person_ids[canonical] = f"person:{item['person_id']}"
        person_aliases[canonical] = [
            alias["name"] if isinstance(alias, dict) else alias
            for alias in item.get("aliases", [])
        ]

    documents: dict[str, Counter[str]] = defaultdict(Counter)
    active_years: dict[str, list[int]] = defaultdict(list)
    cooccurrence: Counter[tuple[str, str]] = Counter()
    congress_documents: dict[str, Counter[str]] = defaultdict(Counter)
    congress_years: dict[str, list[int]] = defaultdict(list)

    for path in sorted(CHUNKS.glob("*.jsonl")):
        for line in path.open(encoding="utf-8"):
            chunk = json.loads(line)
            document_id = chunk["document_id"]
            years = [int(year) for year in chunk.get("year_mentions", [])]
            present: set[str] = set()
            for canonical in chunk.get("people", []):
                if canonical in person_ids:
                    present.add(canonical)
            text = chunk.get("text", "")
            for canonical in person_aliases:
                if canonical in present:
                    continue
                if canonical in text:
                    present.add(canonical)
            for canonical in present:
                documents[canonical][document_id] += 1
                active_years[canonical].extend(years)
            for left in sorted(present):
                for right in sorted(present):
                    if left < right:
                        cooccurrence[(left, right)] += 1

            section = " ".join(chunk.get("section_path", []))
            for match in CONGRESS_SECTION.finditer(section):
                ordinal = match.group(1)
                if ordinal not in NUMBER:
                    continue
                name = f"中共{ordinal}大"
                congress_documents[name][document_id] += 1
                congress_years[name].extend(years)

    records = []
    for canonical, entity_id in person_ids.items():
        documents_for = documents[canonical]
        top_docs = [
            {"document_id": document_id, "mentions": count}
            for document_id, count in documents_for.most_common(5)
        ]
        years = active_years[canonical]
        active = (
            {"start": min(years), "end": max(years)}
            if years and min(years) <= max(years)
            else None
        )
        related = [
            {"canonical": right if left == canonical else left, "count": count}
            for (left, right), count in cooccurrence.most_common()
            if canonical in (left, right)
        ][:5]
        records.append(
            {
                "entity_id": entity_id,
                "type": "person",
                "canonical": canonical,
                "aliases": sorted(set(person_aliases[canonical])),
                "active": active,
                "documents": top_docs,
                "cooccurrence": related,
            }
        )

    def base_title(title: str) -> str:
        text = re.sub(r"\s*第[一二三四五六七八九十]+卷.*$", "", title)
        text = re.sub(r"[（(][^）)]*[）)].*$", "", text)
        return text.strip()

    for document in [*catalog, *extra_documents]:
        title = document["title"]
        canonical = base_title(title)
        aliases = {
            title,
            canonical,
            *document_aliases.get(title, []),
            *document.get("aliases", []),
        }
        records.append(
            {
                "entity_id": f"document:{document['document_id']}",
                "type": "document",
                "canonical": canonical,
                "aliases": sorted(alias for alias in aliases if alias and alias != canonical),
                "active": None,
                "documents": [
                    {
                        "document_id": document["document_id"],
                        "mentions": 1,
                    }
                ],
                "cooccurrence": [],
            }
        )

    for item in events:
        records.append(
            {
                "entity_id": f"{item.get('type', 'event')}:{item['event_id']}",
                "type": item.get("type", "event"),
                "canonical": item["canonical_name"],
                "aliases": item.get("aliases", []),
                "active": (
                    {"start": item["start"], "end": item["end"]}
                    if item.get("start") is not None and item.get("end") is not None
                    else None
                ),
                "documents": [],
                "cooccurrence": [],
            }
        )
    for item in places:
        records.append(
            {
                "entity_id": f"place:{item['place_id']}",
                "type": "place",
                "canonical": item["canonical_name"],
                "aliases": item.get("aliases", []),
                "active": None,
                "documents": [],
                "cooccurrence": [],
            }
        )
    for item in organizations:
        records.append(
            {
                "entity_id": f"organization:{item['organization_id']}",
                "type": "organization",
                "canonical": item["canonical_name"],
                "aliases": item.get("aliases", []),
                "active": None,
                "documents": [],
                "cooccurrence": [],
            }
        )

    for ordinal in ORDINALS:
        canonical = f"中共{ordinal}大"
        years = congress_years.get(canonical, [])
        records.append(
            {
                "entity_id": f"congress:cpc_{NUMBER[ordinal]}",
                "type": "congress",
                "canonical": canonical,
                "aliases": [
                    f"党的{ordinal}大",
                    f"{ordinal}大",
                    f"第{ordinal}次全国代表大会",
                    f"中国共产党第{ordinal}次全国代表大会",
                ],
                "active": None,
                "documents": [
                    {"document_id": document_id, "mentions": count}
                    for document_id, count in congress_documents[canonical].most_common(5)
                ],
                "cooccurrence": [],
            }
        )

    group_records = [
        {
            "entity_id": f"group:{index + 1}",
            "type": "person_group",
            "canonical": group["text"],
            "aliases": [],
            "active": None,
            "documents": [],
            "cooccurrence": [],
            "members": group["entity_ids"],
        }
        for index, group in enumerate(groups)
    ]

    records.extend(group_records)
    records.sort(key=lambda item: item["entity_id"])

    if not args.write:
        print(
            f"dry run: {len(records)} entities "
            f"({sum(r['type'] == 'person' for r in records)} persons, "
            f"{sum(r['type'] == 'document' for r in records)} documents, "
            f"{sum(r['type'] == 'congress' for r in records)} congresses, "
            f"{sum(r['type'] in {'event', 'period'} for r in records)} events, "
            f"{sum(r['type'] == 'place' for r in records)} places, "
            f"{sum(r['type'] == 'organization' for r in records)} organizations, "
            f"{len(group_records)} groups)"
        )
        return

    ENTITIES.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "schema_version": 1,
        "index_version": "entity-index-v1-20261030",
        "records": len(records),
        "persons": sum(record["type"] == "person" for record in records),
        "documents": sum(record["type"] == "document" for record in records),
        "congresses": sum(record["type"] == "congress" for record in records),
        "events": sum(record["type"] in {"event", "period"} for record in records),
        "places": sum(record["type"] == "place" for record in records),
        "organizations": sum(record["type"] == "organization" for record in records),
        "groups": len(group_records),
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUTPUT} with {len(records)} entities")


if __name__ == "__main__":
    main()
