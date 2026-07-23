"""Restarting process supervisor for deterministic browser acceptance."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ROOT = Path(
    tempfile.mkdtemp(prefix="course-builder-browser-acceptance-supervisor-")
)

stopping = False
child: subprocess.Popen | None = None


def _stop(_signum: int, _frame: object) -> None:
    global stopping
    stopping = True
    if child is not None and child.poll() is None:
        child.terminate()


def main() -> int:
    global child
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    environment = dict(os.environ)
    environment["COURSE_BUILDER_BROWSER_ACCEPTANCE_ROOT"] = str(ACCEPTANCE_ROOT)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "tests.browser_acceptance_server:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
        "--no-access-log",
    ]
    try:
        while not stopping:
            child = subprocess.Popen(command, cwd=REPO_ROOT, env=environment)
            child.wait()
            if not stopping:
                time.sleep(0.10)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        shutil.rmtree(ACCEPTANCE_ROOT, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
