import subprocess

from investment_system.core.reproducibility import git_metadata


def test_git_metadata_is_nullable_when_git_is_unavailable(monkeypatch, tmp_path) -> None:
    def unavailable(*args, **kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(subprocess, "run", unavailable)
    assert git_metadata(tmp_path) == {"git_commit": None, "dirty_worktree": None}
