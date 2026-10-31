"""Exercise the rollout transaction against a fake Docker process and HTTP service."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deployment_release", ROOT / "deploy/release.py")
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)

REVISION = "a" * 40
OLD_ID = "sha256:" + "1" * 64
NEW_ID = "sha256:" + "2" * 64
IMAGE = "ghcr.io/bibofu/start1921@sha256:" + "3" * 64
FAKE_DOCKER = r"""
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ['FAKE_DOCKER_STATE'])
state = json.loads(state_path.read_text())
arguments = sys.argv[1:]
image = os.environ.get('START1921_APP_IMAGE')
state['commands'].append({'args': arguments, 'image': image,
                          'docker_config': os.environ.get('DOCKER_CONFIG')})
def finish(text='', code=0):
    temporary = state_path.with_suffix('.next')
    temporary.write_text(json.dumps(state))
    os.replace(temporary, state_path)
    if text:
        print(text)
    sys.exit(code)

if arguments[0] == 'compose':
    assert arguments[1:3] == ['--project-name', 'start1921']
    command = arguments[7:]
    if command == ['ps', '-q', 'app']:
        finish('app-container' if state['current_id'] else '')
    if command == ['config', '--quiet']:
        finish(code=1 if state.get('config_fail') else 0)
    assert command == ['up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'app']
    if image == state['candidate']:
        state['current_id'] = state['old_id'] if state.get('wrong_image') else state['new_id']
        finish(code=1 if state.get('up_fail') else 0)
    assert image.startswith('start1921:rollback-')
    if state.get('rollback_fail'):
        finish(code=1)
    state['current_id'] = state['old_id']
    finish()
if arguments[0] == 'inspect':
    finish(state['current_id'] + ' true healthy')
if arguments[:2] == ['image', 'tag']:
    assert arguments[2] == state['old_id']
    state['rollback_tag'] = arguments[3]
    finish()
if arguments[0] == 'pull':
    finish(code=1 if state.get('pull_fail') else 0)
if arguments[:2] == ['image', 'inspect']:
    finish(state['new_id'] if arguments[3] == '{{.Id}}' else state['revision'])
if arguments[0] == 'run':
    assert arguments[1:6] == ['--rm', '--network', 'none', '--entrypoint', 'python']
    finish(code=1 if state.get('asset_fail') else 0)
raise AssertionError(arguments)
"""


class Server:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.requests: list[str] = []

    def data(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())  # type: ignore[no-any-return]

    def update(self, **values: Any) -> None:
        state = self.data()
        state.update(values)
        self.path.write_text(json.dumps(state))

    def ups(self) -> list[dict[str, Any]]:
        return [item for item in self.data()["commands"] if "up" in item["args"]]


@pytest.fixture
def deployment(work_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    env_file = work_path / "start1921.env"
    original = b"# protected\nSTART1921_APP_IMAGE=start1921:old\nDEEPSEEK_API_KEY=private-test\n"
    env_file.write_bytes(original)
    compose = work_path / "compose.yaml"
    compose.write_text("name: start1921\n")
    state_file = work_path / "docker-state.json"
    state_file.write_text(
        json.dumps(
            {
                "current_id": OLD_ID,
                "old_id": OLD_ID,
                "new_id": NEW_ID,
                "candidate": IMAGE,
                "revision": REVISION,
                "commands": [],
            }
        )
    )
    fake_docker = work_path / "docker.py"
    fake_docker.write_text(FAKE_DOCKER)
    server = Server(state_file)

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            server.requests.append(self.path)
            state = server.data()
            vector = not (state["current_id"] == NEW_ID and state.get("vector_unready"))
            if self.path == "/api/health":
                payload = {
                    "status": "ok",
                    "database_ready": True,
                    "indexes": {"keyword": True, "vector": True},
                }
            else:
                # HTTP 200 and ready alone must not mask a broken vector index.
                payload = {
                    "status": "ready",
                    "components": {
                        "database": True,
                        "keyword": True,
                        "vector": vector,
                    },
                }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, _format: str, *args: Any) -> None:
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(state_file))
    monkeypatch.setenv("DOCKER_CONFIG", "temporary-registry-credentials")
    monkeypatch.setattr(release, "DOCKER_COMMAND", [sys.executable, str(fake_docker)])
    monkeypatch.setattr(release, "BASE_URL", f"http://127.0.0.1:{httpd.server_port}")
    if os.name != "posix":
        monkeypatch.setattr(release, "deployment_lock", lambda _path: contextlib.nullcontext())
    args = [
        "--image",
        IMAGE,
        "--revision",
        REVISION,
        "--compose",
        str(compose),
        "--env-file",
        str(env_file),
        "--health-timeout",
        "1.0",
    ]
    try:
        yield {
            "args": args,
            "env": env_file,
            "original": original,
            "server": server,
            "state": env_file.parent / "release-state.json",
        }
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_release_persists_immutable_image_after_real_readiness(deployment: dict[str, Any]) -> None:
    assert release.main(deployment["args"]) == 0
    server = deployment["server"]
    assert server.data()["current_id"] == NEW_ID
    assert len(server.ups()) == 1
    assert server.requests == ["/api/health", "/api/ready"]
    assert f"START1921_APP_IMAGE={IMAGE}" in deployment["env"].read_text()
    assert "DEEPSEEK_API_KEY=private-test" in deployment["env"].read_text()
    assert json.loads(deployment["state"].read_text())["status"] == "healthy"
    assert all(
        item["docker_config"] == "temporary-registry-credentials"
        for item in server.data()["commands"]
    )


@pytest.mark.parametrize("failure", ["pull_fail", "config_fail", "asset_fail"])
def test_preflight_failure_keeps_running_app_and_env(
    deployment: dict[str, Any],
    failure: str,
) -> None:
    server = deployment["server"]
    server.update(**{failure: True})
    assert release.main(deployment["args"]) == 1
    assert server.data()["current_id"] == OLD_ID
    assert server.ups() == []
    assert deployment["env"].read_bytes() == deployment["original"]


def test_mismatched_revision_is_rejected_before_switch(deployment: dict[str, Any]) -> None:
    deployment["server"].update(revision="b" * 40)
    assert release.main(deployment["args"]) == 1
    assert deployment["server"].ups() == []


@pytest.mark.parametrize("failure", ["vector_unready", "up_fail", "wrong_image"])
def test_failed_rollout_restores_exact_previous_image(
    deployment: dict[str, Any],
    failure: str,
) -> None:
    server = deployment["server"]
    server.update(**{failure: True})
    assert release.main(deployment["args"]) == 1
    state = server.data()
    assert state["current_id"] == OLD_ID
    assert [item["image"] for item in server.ups()] == [IMAGE, state["rollback_tag"]]
    assert state["rollback_tag"] in deployment["env"].read_text()
    assert "DEEPSEEK_API_KEY=private-test" in deployment["env"].read_text()
    assert json.loads(deployment["state"].read_text())["status"] == "rolled_back"


def test_rollback_failure_is_reported_and_retains_recovery_image(
    deployment: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = deployment["server"]
    server.update(vector_unready=True, rollback_fail=True)
    assert release.main(deployment["args"]) == 2
    assert "ROLLBACK FAILED" in capsys.readouterr().err
    state = json.loads(deployment["state"].read_text())
    assert state["status"] == "rollback_failed"
    assert state["previous_image"] == server.data()["rollback_tag"]
    assert state["previous_image_id"] == OLD_ID


def test_persistence_failure_also_rolls_back(
    deployment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    atomic_write = release.atomic_write

    def fail_new_env(path: Path, content: bytes) -> None:
        if path == deployment["env"].resolve() and IMAGE.encode() in content:
            raise OSError("simulated read-only env")
        atomic_write(path, content)

    monkeypatch.setattr(release, "atomic_write", fail_new_env)
    assert release.main(deployment["args"]) == 1
    assert deployment["server"].data()["current_id"] == OLD_ID
    assert "START1921_APP_IMAGE=start1921:rollback-" in deployment["env"].read_text()


def test_initial_deployment_is_refused(deployment: dict[str, Any]) -> None:
    deployment["server"].update(current_id=None)
    assert release.main(deployment["args"]) == 1
    assert deployment["server"].ups() == []


def test_failure_after_env_commit_restores_previous_image_configuration(
    deployment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    atomic_write = release.atomic_write
    observed_new_env = False

    def fail_final_record(path: Path, content: bytes) -> None:
        nonlocal observed_new_env
        if path == deployment["state"].resolve() and json.loads(content)["status"] == "healthy":
            observed_new_env = IMAGE in deployment["env"].read_text()
            raise OSError("simulated journal disk error")
        atomic_write(path, content)

    monkeypatch.setattr(release, "atomic_write", fail_final_record)
    assert release.main(deployment["args"]) == 1
    assert observed_new_env
    assert deployment["server"].data()["current_id"] == OLD_ID
    assert IMAGE not in deployment["env"].read_text()
    assert "START1921_APP_IMAGE=start1921:rollback-" in deployment["env"].read_text()


def test_signal_during_readiness_is_not_swallowed(
    deployment: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_ready = release.api_ready
    interrupted = False

    def interrupt_once(path: str, timeout: float) -> dict[str, Any]:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            signal.raise_signal(signal.SIGTERM)
        return api_ready(path, timeout)  # type: ignore[no-any-return]

    monkeypatch.setattr(release, "api_ready", interrupt_once)
    assert release.main(deployment["args"]) == 1
    assert deployment["server"].data()["current_id"] == OLD_ID
    assert json.loads(deployment["state"].read_text())["status"] == "rolled_back"


@pytest.mark.skipif(os.name != "posix", reason="The production lock uses Linux flock")
def test_competing_process_cannot_enter_deployment(work_path: Path) -> None:
    lock_path = work_path / "release.lock"
    child = """import importlib.util, sys
s = importlib.util.spec_from_file_location('release', sys.argv[1])
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
try:
    with m.deployment_lock(__import__('pathlib').Path(sys.argv[2])):
        sys.exit(0)
except m.ReleaseError:
    sys.exit(23)
"""
    with release.deployment_lock(lock_path):
        result = subprocess.run(
            [sys.executable, "-c", child, str(ROOT / "deploy/release.py"), str(lock_path)],
            check=False,
            timeout=10,
        )
    assert result.returncode == 23


def test_invalid_image_is_rejected_without_docker(deployment: dict[str, Any]) -> None:
    arguments = deployment["args"].copy()
    arguments[1] = "ghcr.io/bibofu/start1921:latest"
    assert release.main(arguments) == 1
    assert deployment["server"].data()["commands"] == []


def test_env_replacement_removes_duplicate_tags_without_changing_secrets() -> None:
    original = b"# x\r\nexport START1921_APP_IMAGE=old\r\nTOKEN='a=b'\r\nSTART1921_APP_IMAGE=older"
    updated = release.image_environment(original, IMAGE)
    assert updated.count(b"START1921_APP_IMAGE=") == 1
    assert b"TOKEN='a=b'\r\n" in updated
    assert updated.endswith(f"START1921_APP_IMAGE={IMAGE}\r\n".encode())
