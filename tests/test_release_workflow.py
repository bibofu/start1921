from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_helper(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "deploy" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolver = load_helper("resolve_release")
remote = load_helper("remote_release")


def run_git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", "user.name=Release Test", "-c", "user.email=test@example.invalid", *args],
        cwd=path, text=True, stderr=subprocess.DEVNULL,
    ).strip()


@pytest.fixture
def release_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    origin = tmp_path / "origin.git"
    origin.mkdir()
    run_git(origin, "init", "--bare")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run_git(checkout, "init", "-b", "main")
    run_git(checkout, "commit", "--allow-empty", "-m", "base")
    run_git(checkout, "remote", "add", "origin", str(origin))
    run_git(checkout, "push", "-u", "origin", "main")
    run_git(checkout, "tag", "-a", "v1.0.0", "-m", "release")
    run_git(checkout, "push", "origin", "v1.0.0")
    monkeypatch.chdir(checkout)
    return checkout, run_git(checkout, "rev-parse", "HEAD")


def test_tag_on_main_resolves_annotated_tag(release_repository: tuple[Path, str]) -> None:
    checkout, commit = release_repository
    tag_object = run_git(checkout, "rev-parse", "v1.0.0")
    assert resolver.resolve("v1.0.0", event="push", ref="refs/tags/v1.0.0",
                            event_sha=tag_object) == commit


def test_unmerged_branch_tag_cannot_deploy(release_repository: tuple[Path, str]) -> None:
    checkout, _ = release_repository
    run_git(checkout, "checkout", "-b", "feature")
    run_git(checkout, "commit", "--allow-empty", "-m", "unmerged")
    run_git(checkout, "tag", "v2.0.0")
    run_git(checkout, "push", "origin", "v2.0.0")
    with pytest.raises(ValueError, match="contained in origin/main"):
        resolver.resolve("v2.0.0", event="workflow_dispatch", ref="refs/heads/main",
                         event_sha=run_git(checkout, "rev-parse", "HEAD"))


def test_manual_release_can_choose_previous_main_tag(
    release_repository: tuple[Path, str],
) -> None:
    checkout, commit = release_repository
    run_git(checkout, "commit", "--allow-empty", "-m", "later main")
    run_git(checkout, "push", "origin", "main")
    assert resolver.resolve("v1.0.0", event="workflow_dispatch", ref="refs/heads/main",
                            event_sha=run_git(checkout, "rev-parse", "HEAD")) == commit


def test_changed_tag_event_is_rejected(release_repository: tuple[Path, str]) -> None:
    checkout, commit = release_repository
    run_git(checkout, "commit", "--allow-empty", "-m", "new")
    run_git(checkout, "tag", "v1.1.0")
    run_git(checkout, "push", "origin", "main", "v1.1.0")
    with pytest.raises(ValueError, match="changed after"):
        resolver.resolve("v1.1.0", event="push", ref="refs/tags/v1.1.0", event_sha=commit)


@pytest.mark.parametrize("tag", ["main", "v1.0.0;id", "--help", "v1.0.0\ncommit=evil"])
def test_invalid_tag_rejected_before_git(tag: str) -> None:
    with pytest.raises(ValueError, match="version tag"):
        resolver.resolve(tag, event="workflow_dispatch", ref="refs/heads/main", event_sha="")


def test_manual_run_from_other_branch_rejected() -> None:
    with pytest.raises(ValueError, match="main branch"):
        resolver.resolve("v1.0.0", event="workflow_dispatch", ref="refs/heads/topic", event_sha="")


def test_remote_rollout_uses_temporary_auth_and_fixed_paths() -> None:
    command = remote.remote_command(
        "/tmp/start1921-release.A1B2", "ghcr.io/bibofu/start1921@sha256:" + "a" * 64,
        "b" * 40, "bibofu",
    )
    assert "--password-stdin" in command
    assert "DOCKER_CONFIG=/tmp/start1921-release.A1B2/docker-auth" in command
    assert "--env-file /etc/start1921/start1921.env" in command
    assert "trap " in command
    assert "--revision " + "b" * 40 in command


@pytest.mark.parametrize("directory,image,revision", [
    ("/tmp/../../etc", "ghcr.io/bibofu/start1921@sha256:" + "a" * 64, "b" * 40),
    ("/tmp/start1921-release.A1", "ghcr.io/other/app:latest", "b" * 40),
    ("/tmp/start1921-release.A1", "ghcr.io/bibofu/start1921@sha256:" + "a" * 64, "$(id)"),
])
def test_remote_command_rejects_untrusted_release_values(
    directory: str, image: str, revision: str,
) -> None:
    with pytest.raises(ValueError):
        remote.remote_command(directory, image, revision, "bibofu")
