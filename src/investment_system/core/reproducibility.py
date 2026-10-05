"""Best-effort build provenance that never makes local workflows depend on Git."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any


def git_metadata(workdir: str | Path | None = None) -> dict[str, Any]:
    """Return commit and worktree state, or nulls when Git cannot be executed."""
    root = Path(workdir or Path.cwd())
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            timeout=3, check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True,
            timeout=3, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "dirty_worktree": None}
    if commit.returncode != 0 or status.returncode != 0:
        return {"git_commit": None, "dirty_worktree": None}
    sha = commit.stdout.strip()
    return {"git_commit": sha or None, "dirty_worktree": bool(status.stdout.strip())}
