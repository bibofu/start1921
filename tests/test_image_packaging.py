from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
check_image = runpy.run_path(str(ROOT / "deploy" / "check_image.py"))["check_image"]


def test_runtime_assets_pass_packaging_check() -> None:
    check_image(ROOT)


def test_missing_domain_dictionary_fails_packaging_check(work_path: Path) -> None:
    shutil.copytree(ROOT / "config", work_path / "config")
    (work_path / "config" / "jieba_userdict.txt").unlink()
    with pytest.raises(FileNotFoundError, match="jieba_userdict.txt"):
        check_image(work_path)


def test_top_level_only_configuration_fails_packaging_check(work_path: Path) -> None:
    # Reproduce the old Docker COPY: all top-level JSON files, no entity subtree.
    destination = work_path / "config"
    destination.mkdir()
    for source in (ROOT / "config").glob("*.json"):
        shutil.copyfile(source, destination / source.name)

    with pytest.raises(FileNotFoundError, match="entities.jsonl"):
        check_image(work_path)


def test_truncated_entity_index_fails_packaging_check(work_path: Path) -> None:
    shutil.copytree(ROOT / "config", work_path / "config")
    manifest_path = work_path / "config" / "entities" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["records"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its manifest"):
        check_image(work_path)
