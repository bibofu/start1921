#!/usr/bin/env python3
"""Replace only the existing app container, or restore its exact previous image.

Run on the Linux deployment host with access to Docker and the protected env file.
This script does not initialize services or migrate business data. It rebuilds
incompatible keyword indexes and restores their generation on image rollback.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.request import urlopen

DOCKER_COMMAND = ["docker"]
IMAGE_PATTERN = re.compile(r"ghcr\.io/bibofu/start1921@sha256:[0-9a-f]{64}\Z")
REVISION_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
BASE_URL = "http://127.0.0.1:18021"
IMAGE_CHECK = """from pathlib import Path
import json
from history_agent.answering.entity_linking import load_entities
root = Path('/app/config')
assert load_entities(root / 'entities/entities.jsonl'), 'entity index is empty'
for name in ('corpus_catalog.json', 'person_aliases.json', 'query_aliases.json'):
    assert json.loads((root / name).read_text(encoding='utf-8'))
"""
SETTINGS_CHECK = "from history_agent.config import get_settings; get_settings()"


class ReleaseError(Exception):
    """A release failed without exposing command output or configuration secrets."""


class DeploymentInterrupted(ReleaseError):
    pass


class Docker:
    def __init__(self, compose: Path, env_file: Path) -> None:
        self.compose = compose
        self.env_file = env_file

    def run(
        self,
        arguments: Sequence[str],
        *,
        image: str | None = None,
        timeout: float = 180,
    ) -> str:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("START1921_", "HISTORY_AGENT_", "COMPOSE_"))
            and key != "DEEPSEEK_API_KEY"
        }
        environment["START1921_ENV_FILE"] = str(self.env_file)
        if image is not None:
            environment["START1921_APP_IMAGE"] = image
        try:
            result = subprocess.run(
                [*DOCKER_COMMAND, *arguments],
                env=environment,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReleaseError(
                f"Docker {arguments[0]} could not complete ({type(exc).__name__})"
            ) from None
        if result.returncode:
            # Compose errors can contain expanded credentials. Never echo stderr.
            raise ReleaseError(f"Docker {arguments[0]} failed (exit {result.returncode})")
        return result.stdout.strip()

    def dc(self, *arguments: str, image: str | None = None, timeout: float = 180) -> str:
        return self.run(
            [
                "compose",
                "--project-name",
                "start1921",
                "--env-file",
                str(self.env_file),
                "--file",
                str(self.compose),
                *arguments,
            ],
            image=image,
            timeout=timeout,
        )

    def container(self, *, image: str | None = None) -> tuple[str, str, str]:
        containers = self.dc("ps", "-q", "app", image=image, timeout=10).splitlines()
        if len(containers) != 1:
            raise ReleaseError("Expected exactly one running start1921 app; initialize it manually")
        fields = self.run(
            [
                "inspect",
                "--format",
                "{{.Image}} {{.State.Running}} "
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}",
                containers[0],
            ],
            timeout=10,
        ).split()
        if len(fields) != 3 or not IMAGE_ID_PATTERN.fullmatch(fields[0]):
            raise ReleaseError("Could not identify the running app image")
        return fields[0], fields[1], fields[2]


@contextlib.contextmanager
def deployment_lock(path: Path) -> Iterator[None]:
    # flock is kernel-scoped and released even when a deployment process crashes.
    if os.name != "posix":
        raise ReleaseError("Deployments must run on the Linux server")
    import fcntl

    with path.open("a", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ReleaseError("Another start1921 deployment is already running") from None
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def interruptible() -> Iterator[None]:
    def interrupted(signum: int, _frame: Any) -> None:
        raise DeploymentInterrupted(f"Deployment interrupted by signal {signum}")

    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        signals.append(signal.SIGHUP)
    previous = {sig: signal.signal(sig, interrupted) for sig in signals}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextlib.contextmanager
def protect_rollback() -> Iterator[None]:
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        signals.append(signal.SIGHUP)
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in signals}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def atomic_write(path: Path, content: bytes) -> None:
    """Keep env ownership/mode and replace in the same directory atomically."""
    metadata = path.stat() if path.exists() else None
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, metadata.st_mode & 0o777 if metadata else 0o600)
        if metadata is not None and hasattr(os, "chown"):
            os.chown(temporary_path, metadata.st_uid, metadata.st_gid)
        os.replace(temporary_path, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary_path.unlink(missing_ok=True)


def image_environment(original: bytes, image: str) -> bytes:
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = [
        line
        for line in text.splitlines(keepends=True)
        if not re.match(r"^\s*(?:export\s+)?START1921_APP_IMAGE\s*=", line)
    ]
    kept = "".join(lines)
    if kept and not kept.endswith(("\r", "\n")):
        kept += newline
    return f"{kept}START1921_APP_IMAGE={image}{newline}".encode()


def api_ready(path: str, timeout: float) -> dict[str, Any]:
    with urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Health response is not an object")
    return value


def wait_healthy(docker: Docker, image: str, image_id: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            actual_image, running, health = docker.container(image=image)
            if actual_image == image_id and running == "true" and health == "healthy":
                state = api_ready("/api/health", max(0.1, min(10, deadline - time.monotonic())))
                indexes = state.get("indexes", {})
                if (
                    state.get("status") == "ok"
                    and state.get("database_ready") is True
                    and isinstance(indexes, dict)
                    and all(indexes.get(name) is True for name in ("keyword", "vector"))
                ):
                    ready = api_ready("/api/ready", max(0.1, min(45, deadline - time.monotonic())))
                    components = ready.get("components", {})
                    if (
                        ready.get("status") == "ready"
                        and isinstance(components, dict)
                        and all(
                            components.get(name) is True
                            for name in ("database", "keyword", "vector")
                        )
                    ):
                        return
        except DeploymentInterrupted:
            raise
        except (ReleaseError, OSError, ValueError, HTTPException):
            pass
        time.sleep(max(0, min(3, deadline - time.monotonic())))
    raise ReleaseError(
        "App readiness deadline expired; all database and retrieval checks must pass"
    )


def deploy(args: argparse.Namespace) -> int:
    if not IMAGE_PATTERN.fullmatch(args.image) or not REVISION_PATTERN.fullmatch(args.revision):
        raise ReleaseError("Use this repository's immutable GHCR digest and full source commit SHA")
    if args.health_timeout <= 0:
        raise ReleaseError("Health timeout must be positive")
    compose = Path(args.compose).resolve(strict=True)
    env_file = Path(args.env_file).resolve(strict=True)
    if not compose.is_file() or not env_file.is_file():
        raise ReleaseError("Compose and environment paths must be regular files")
    docker = Docker(compose, env_file)
    state_path = env_file.parent / "release-state.json"
    with deployment_lock(env_file.parent / ".start1921-release.lock"), interruptible():
        original_env = env_file.read_bytes()
        # Validate that persistence is possible before touching the current app.
        env_content = image_environment(original_env, args.image)
        old_id, running, _health = docker.container()
        if running != "true":
            raise ReleaseError("Existing app is not running; repair it before deployment")
        rollback_image = f"start1921:rollback-{old_id[7:19]}-{time.time_ns()}"
        docker.run(["image", "tag", old_id, rollback_image])
        state: dict[str, Any] = {
            "revision": args.revision,
            "image": args.image,
            "previous_image": rollback_image,
            "previous_image_id": old_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "preparing",
        }

        def record(status: str) -> None:
            state["status"] = status
            atomic_write(state_path, (json.dumps(state, indent=2) + "\n").encode())

        record("preparing")
        print(f"Preparing {args.revision}", flush=True)
        docker.run(["pull", args.image], timeout=600)
        revision = docker.run(
            [
                "image",
                "inspect",
                "--format",
                '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                args.image,
            ]
        )
        if revision != args.revision:
            raise ReleaseError("Image revision label does not match the approved source commit")
        new_id = docker.run(["image", "inspect", "--format", "{{.Id}}", args.image])
        if not IMAGE_ID_PATTERN.fullmatch(new_id):
            raise ReleaseError("Could not identify the candidate image")
        docker.run(
            [
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "python",
                args.image,
                "-c",
                IMAGE_CHECK,
            ]
        )
        docker.dc("config", "--quiet", image=args.image)
        # Validate the candidate against actual production env/mounts without
        # starting the app, publishing ports, starting dependencies or building.
        docker.dc(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--pull",
            "never",
            "--entrypoint",
            "python",
            "app",
            "-c",
            SETTINGS_CHECK,
            image=args.image,
        )

        def keyword_action(action: str, *options: str) -> dict[str, Any]:
            name = ["--name", "start1921-keyword-upgrade"] if action == "upgrade" else []
            result = docker.dc(
                "run", "--rm", "--no-deps", "-T", "--pull", "never", *name,
                "--entrypoint", "python", "app", "/app/deploy/keyword_upgrade.py",
                action, *options, image=args.image, timeout=1200,
            )
            return dict(json.loads(result))

        keyword_before = keyword_action("status")
        previous_generation = int(keyword_before["generation_id"])
        migrate_keyword = keyword_before["needs_upgrade"] is True
        state["previous_keyword_generation"] = previous_generation
        record("deploying")
        try:
            if migrate_keyword:
                print("Rebuilding incompatible keyword index; retaining previous generation",
                      flush=True)
                state["keyword_generation"] = keyword_action("upgrade")["generation_id"]
                record("deploying")
            # Flag the rollout before this command: Compose can fail after stopping app.
            docker.dc(
                "up", "-d", "--no-deps", "--no-build", "--pull", "never", "app", image=args.image
            )
            wait_healthy(docker, args.image, new_id, args.health_timeout)
            atomic_write(env_file, env_content)
            record("healthy")
        except Exception as exc:
            print(f"Release failed ({type(exc).__name__}); restoring {rollback_image}", flush=True)
            with protect_rollback():
                try:
                    if migrate_keyword:
                        # A timed-out Docker client can leave its one-off container
                        # running. Stop it before restoring the active generation.
                        pending = docker.run(
                            ["ps", "-aq", "--filter", "name=^/start1921-keyword-upgrade$"]
                        )
                        if pending:
                            docker.run(["rm", "--force", "start1921-keyword-upgrade"])
                        keyword_action("restore", "--generation", str(previous_generation))
                    docker.dc(
                        "up",
                        "-d",
                        "--no-deps",
                        "--no-build",
                        "--pull",
                        "never",
                        "app",
                        image=rollback_image,
                    )
                    wait_healthy(docker, rollback_image, old_id, args.health_timeout)
                    atomic_write(env_file, image_environment(original_env, rollback_image))
                    record("rolled_back")
                except Exception as rollback_error:
                    print(
                        f"ROLLBACK FAILED ({type(rollback_error).__name__}). "
                        f"Recover app using retained image {rollback_image}; "
                        "inspect server locally.",
                        file=sys.stderr,
                        flush=True,
                    )
                    with contextlib.suppress(OSError):
                        record("rollback_failed")
                    return 2
            print(
                "Previous app image restored and verified; this release remains failed.", flush=True
            )
            return 1
        print(
            f"Release {args.revision} is healthy; current image persisted in {env_file}", flush=True
        )
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--compose", default="/opt/start1921/deploy/compose.yaml")
    parser.add_argument("--env-file", default="/etc/start1921/start1921.env")
    parser.add_argument("--health-timeout", type=float, default=300)
    args = parser.parse_args(argv)
    try:
        return deploy(args)
    except (ReleaseError, OSError, ValueError) as exc:
        # Never include an exception string that might contain secret file content.
        message = str(exc) if isinstance(exc, ReleaseError) else type(exc).__name__
        print(f"Release aborted before rollout: {message}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
