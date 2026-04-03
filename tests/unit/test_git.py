"""Unit tests for git utility wrappers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cwm.util.git import get_toplevel, get_current_branch, worktree_list


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t",
             "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    return tmp_path


class TestGetToplevel:
    def test_returns_repo_root(self, git_repo: Path) -> None:
        result = get_toplevel(git_repo)
        assert result == git_repo


class TestGetCurrentBranch:
    def test_returns_branch_name(self, git_repo: Path) -> None:
        # Default branch after git init (usually master or main)
        branch = get_current_branch(git_repo)
        assert isinstance(branch, str)
        assert len(branch) > 0


class TestWorktreeList:
    def test_single_worktree(self, git_repo: Path) -> None:
        entries = worktree_list(git_repo)
        assert len(entries) == 1
        assert entries[0].path == git_repo
