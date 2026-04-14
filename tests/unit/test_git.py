"""Unit tests for git utility wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwm.util.git import get_toplevel, get_current_branch, worktree_list
from tests.conftest import make_git_repo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    make_git_repo(tmp_path)
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
