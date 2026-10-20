"""Cheap container health probe; functional embedding is checked at rollout."""

import json
from urllib.request import urlopen


def main() -> int:
    try:
        with urlopen("http://127.0.0.1:8000/api/health", timeout=10) as response:
            state = json.load(response)
        indexes = state.get("indexes", {})
        ready = (
            state.get("status") == "ok"
            and state.get("database_ready") is True
            and indexes.get("keyword") is True
            and indexes.get("vector") is True
        )
    except (OSError, ValueError):
        return 1
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
