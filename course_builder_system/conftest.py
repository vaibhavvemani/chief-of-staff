"""
pytest conftest — adds the repo root (course_builder_system/) to sys.path so
that top-level modules (steps, integrity, orchestrator, llm, agents.*) can be
imported without installing the package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# course_builder_system/ is this file's directory; add it to sys.path.
REPO_DIR = Path(__file__).resolve().parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))
