"""
Tests for application startup behavior.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_importing_main_does_not_emit_requests_dependency_warning() -> None:
    """
    Importing the FastAPI app should not trigger Requests dependency warnings.

    This runs the import in a subprocess so we exercise the real startup path
    without mutating the current pytest process state.
    """

    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    script = """
import importlib
import warnings

warnings.filterwarnings(
    "error",
    message=r".*doesn't match a supported version!",
    category=Warning,
)

importlib.import_module("services.api.main")
print("imported main")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "imported main" in result.stdout
