"""Run the rollout over pinned-host SSH using temporary registry credentials."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing Actions configuration: {name}")
    return value


def remote_command(directory: str, image: str, revision: str, actor: str) -> str:
    # Values are checked here as well as by the server-side release script.
    if not re.fullmatch(r"/tmp/start1921-release\.[A-Za-z0-9]+", directory):
        raise ValueError("Unexpected remote staging directory")
    if not re.fullmatch(r"ghcr\.io/bibofu/start1921@sha256:[0-9a-f]{64}", image):
        raise ValueError("Expected the start1921 image pinned by digest")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected a full Git commit SHA")
    quote = shlex.quote
    auth = directory + "/docker-auth"
    return "\n".join([
        "set -eu",
        f"sudo -n install -d -m 700 {quote(auth)}",
        f"trap {quote('sudo -n rm -rf -- ' + quote(auth))} EXIT",
        # stdin is the short-lived, read-only job token, never a command argument.
        f"sudo -n docker --config {quote(auth)} login ghcr.io "
        f"--username {quote(actor)} --password-stdin >/dev/null",
        f"sudo -n env DOCKER_CONFIG={quote(auth)} python3 {quote(directory + '/release.py')} "
        f"--image {quote(image)} --revision {quote(revision)} "
        "--compose /opt/start1921/deploy/compose.yaml "
        "--env-file /etc/start1921/start1921.env",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    host, user = required("DEPLOY_HOST"), required("DEPLOY_USER")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise ValueError("Invalid deployment host")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise ValueError("Invalid deployment user")
    port = int(os.environ.get("DEPLOY_PORT", "22"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid SSH port")
    key, known_hosts = required("DEPLOY_SSH_KEY"), required("DEPLOY_KNOWN_HOSTS")
    token, actor = required("GHCR_TOKEN"), required("GHCR_USER")
    target = f"{user}@{host}"
    directory = ""
    with tempfile.TemporaryDirectory(prefix="start1921-ssh-") as local:
        private_key = Path(local) / "identity"
        hosts = Path(local) / "known_hosts"
        private_key.write_text(key + "\n", encoding="utf-8")
        hosts.write_text(known_hosts + "\n", encoding="utf-8")
        private_key.chmod(0o600)
        hosts.chmod(0o600)
        common = ["-i", str(private_key), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                  "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={hosts}",
                  "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15",
                  "-o", "ServerAliveCountMax=4"]
        ssh = ["ssh", *common, "-p", str(port), target]
        try:
            directory = subprocess.check_output(
                [*ssh, "mktemp -d /tmp/start1921-release.XXXXXXXX"], text=True
            ).strip()
            command = remote_command(directory, args.image, args.revision, actor)
            subprocess.run(["scp", *common, "-P", str(port),
                            str(Path(__file__).with_name("release.py")),
                            f"{target}:{directory}/release.py"], check=True)
            result = subprocess.run([*ssh, command], input=token + "\n", text=True)
            return result.returncode
        finally:
            if re.fullmatch(r"/tmp/start1921-release\.[A-Za-z0-9]+", directory):
                # The exact mktemp directory is all that is ever removed.
                subprocess.run([*ssh, f"sudo -n rm -rf -- {shlex.quote(directory)}"],
                               check=False, timeout=30)


if __name__ == "__main__":
    raise SystemExit(main())
