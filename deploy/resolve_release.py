"""Resolve a release tag to a commit reachable from origin/main."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9][A-Za-z0-9.-]*)?")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def resolve(tag: str, *, event: str, ref: str, event_sha: str) -> str:
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError("Use a version tag such as v0.1.0 or v0.1.0-rc.1")
    if event == "workflow_dispatch" and ref != "refs/heads/main":
        raise ValueError("Run the manual release workflow from the main branch")
    if event not in {"push", "workflow_dispatch"}:
        raise ValueError("Only tag pushes and manual releases are supported")
    if event == "push" and ref != f"refs/tags/{tag}":
        raise ValueError("The pushed ref must be the requested tag")
    # actions/checkout can materialize a tag event as a lightweight local ref.
    # Refresh only that local ref from origin, even when origin has an annotated
    # tag object. The event commit and main ancestry checks below still prevent
    # a tag moved to another commit from being released by an older push event.
    git(
        "fetch",
        "--no-tags",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        f"+refs/tags/{tag}:refs/tags/{tag}",
    )
    commit = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    if event == "push" and git("rev-parse", f"{event_sha}^{{commit}}") != commit:
        raise ValueError("The remote tag changed after the push event")
    result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"])
    if result.returncode != 0:
        raise ValueError("Release tag must point to a commit contained in origin/main")
    return commit


def main() -> None:
    tag = os.environ["RELEASE_TAG"]
    commit = resolve(
        tag,
        event=os.environ["GITHUB_EVENT_NAME"],
        ref=os.environ["GITHUB_REF"],
        event_sha=os.environ["GITHUB_SHA"],
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"tag={tag}\ncommit={commit}\n")
    print(f"Release {tag}: {commit} (contained in main)")


if __name__ == "__main__":
    main()
