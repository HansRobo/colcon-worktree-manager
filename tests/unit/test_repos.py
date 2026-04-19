"""Unit tests for repository discovery utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwm.errors import RepoNotFoundError
from cwm.util.repos import discover_sub_repos, validate_repo_path
from tests.conftest import make_git_repo as _make_git_repo


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
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()

        result = discover_sub_repos(src)
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


class TestValidateRepoPath:
    def test_valid_path_passes(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "pkg_a")
        result = validate_repo_path(src, "pkg_a")
        assert result == src / "pkg_a"

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(RepoNotFoundError, match="pkg_missing"):
            validate_repo_path(src, "pkg_missing")

    def test_non_git_directory_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "not_a_repo").mkdir(parents=True)
        with pytest.raises(RepoNotFoundError, match="not_a_repo"):
            validate_repo_path(src, "not_a_repo")

    def test_nested_path(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        _make_git_repo(src / "core" / "autoware_core")
        result = validate_repo_path(src, "core/autoware_core")
        assert result == src / "core" / "autoware_core"
