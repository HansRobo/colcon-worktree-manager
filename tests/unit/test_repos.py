"""Unit tests for sub-repository discovery utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cwm.errors import SubRepoNotFoundError
from cwm.util.repos import discover_sub_repos, validate_sub_repo_paths


def _make_git_repo(path: Path) -> None:
    """Initialise a minimal git repository at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
        cwd=path,
        env={
            "HOME": str(path),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@t.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@t.com",
            **__import__("os").environ,
        },
    )


class TestDiscoverSubRepos:
    def test_finds_top_level_repos(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "pkg_a")
        _make_git_repo(src / "pkg_b")

        result = discover_sub_repos(src)
        assert set(result.keys()) == {"pkg_a", "pkg_b"}

    def test_finds_nested_repos(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "core" / "autoware_core")
        _make_git_repo(src / "universe" / "autoware_universe")

        result = discover_sub_repos(src)
        assert set(result.keys()) == {
            "core/autoware_core",
            "universe/autoware_universe",
        }

    def test_does_not_recurse_into_git_repos(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        outer = src / "outer"
        _make_git_repo(outer)
        # Create a directory inside the git repo that looks like a nested repo
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()

        result = discover_sub_repos(src)
        # Only the outer repo should appear
        assert set(result.keys()) == {"outer"}

    def test_empty_src(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        assert discover_sub_repos(src) == {}

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "pkg_a")

        result = discover_sub_repos(src)
        assert result["pkg_a"].is_absolute()

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / ".hidden_repo")
        _make_git_repo(src / "visible_repo")

        result = discover_sub_repos(src)
        assert set(result.keys()) == {"visible_repo"}


class TestValidateSubRepoPaths:
    def test_valid_paths_pass(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "pkg_a")
        # Should not raise
        validate_sub_repo_paths(src, ["pkg_a"])

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(SubRepoNotFoundError, match="pkg_missing"):
            validate_sub_repo_paths(src, ["pkg_missing"])

    def test_non_git_directory_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "not_a_repo").mkdir(parents=True)
        with pytest.raises(SubRepoNotFoundError, match="not_a_repo"):
            validate_sub_repo_paths(src, ["not_a_repo"])

    def test_nested_path(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "core" / "autoware_core")
        # Should not raise
        validate_sub_repo_paths(src, ["core/autoware_core"])
