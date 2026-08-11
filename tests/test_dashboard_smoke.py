from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_streamlit_dashboard_starts_and_serves_healthcheck() -> None:
    port = _unused_port()
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "apps/dashboard/app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = time.monotonic() + 30
        health_url = f"http://127.0.0.1:{port}/_stcore/health"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout is not None else ""
                raise AssertionError(f"Streamlit exited before healthcheck responded:\n{output}")
            try:
                with urlopen(health_url, timeout=1) as response:
                    body = response.read().decode("utf-8", errors="replace")
                assert response.status == 200
                assert body == "ok"
                return
            except URLError:
                time.sleep(0.5)

        output = process.stdout.read() if process.stdout is not None else ""
        raise AssertionError(f"Streamlit healthcheck did not respond within 30 seconds:\n{output}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
