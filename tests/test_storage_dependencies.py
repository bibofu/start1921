"""Guard the supported uv environment against reintroducing local storage."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def test_application_imports_without_sqlite_or_local_qdrant() -> None:
    source = textwrap.dedent("""
        import importlib.abc
        import importlib.metadata
        import sys

        blocked = {"sqlite3", "_sqlite3", "aiosqlite", "pysqlite3", "qdrant_client"}

        class NoLocalStorage(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in blocked:
                    raise ModuleNotFoundError("Unsupported local storage: " + fullname)

        sys.meta_path.insert(0, NoLocalStorage())
        for package in ("aiosqlite", "qdrant-client"):
            try:
                importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                continue
            raise AssertionError(package + " must be removed by uv sync")

        import history_agent.cli
        import history_agent.web.app
        from fastembed import TextEmbedding

        assert not (blocked & set(sys.modules))
    """)
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
