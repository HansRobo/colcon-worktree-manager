"""Unit tests for the meta-repository workspace manager."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from cwm.core.config import BaseWorkspaceConfig, Config
from cwm.core.meta_wsm import MetaWorkspaceManager
from cwm.core.wsm import WorktreeMeta
from cwm.errors import SubRepoNotFoundError, WorktreeExistsError, WorktreeNotFoundError

# Minimal git identity environment for subprocess calls
_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "t@t.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "t@t.com",
}


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=_GIT_ENV)


def _make_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], path)
    _git(["commit", "--allow-empty", "-m", "init"], path)


@pytest.fixture
def meta_project(tmp_path: Path) -> Config:
    """Create a minimal meta-mode project with two sub-repos in base_ws/src/."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    config = Config(
        underlay="/opt/ros/jazzy",
        base_ws=BaseWorkspaceConfig(branch="main"),
        project_root=project_root,
    )

    # Create directory scaffolding (mirrors WorktreeStateManager.init_project)
    for d in [
        config.cwm_dir / "worktrees",
        config.cwm_dir / "cache",
        config.base_ws_path / "build",
        config.base_ws_path / "install",
        config.base_ws_path / "log",
        config.worktrees_path,
    ]:
        d.mkdir(parents=True)

    # Create two sub-repos under base_ws/src/
    _make_git_repo(config.base_src_path / "core" / "pkg_a")
    _make_git_repo(config.base_src_path / "core" / "pkg_b")

    config.save()
    return config


class TestCreateWorktree:
    def test_creates_workspace_dirs(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        ws = mgr.create_worktree("feature-fix", ["core/pkg_a"])

        assert (ws / "build").is_dir()
        assert (ws / "install").is_dir()
        assert (ws / "log").is_dir()

    def test_creates_sub_repo_worktree(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])

        sub = meta_project.worktree_ws_path("feature-fix") / "src" / "core" / "pkg_a"
        assert sub.is_dir()
        assert (sub / ".git").exists()

    def test_saves_metadata(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])

        meta = WorktreeMeta.load(meta_project.worktree_meta_path("feature-fix"))
        assert meta.branch == "feature-fix"
        assert "core/pkg_a" in meta.sub_repos
        assert "core/pkg_a" in meta.sub_repo_shas

    def test_raises_if_already_exists(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        with pytest.raises(WorktreeExistsError):
            mgr.create_worktree("feature-fix", ["core/pkg_b"])

    def test_raises_for_invalid_sub_repo(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        with pytest.raises(SubRepoNotFoundError, match="nonexistent"):
            mgr.create_worktree("feature-fix", ["nonexistent/pkg"])


class TestRemoveWorktree:
    def test_removes_workspace(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        ws = meta_project.worktree_ws_path("feature-fix")

        mgr.remove_worktree("feature-fix")
        assert not ws.exists()

    def test_removes_metadata(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        mgr.remove_worktree("feature-fix")

        assert not meta_project.worktree_meta_path("feature-fix").exists()

    def test_raises_if_not_exists(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        with pytest.raises(WorktreeNotFoundError):
            mgr.remove_worktree("nonexistent")


class TestAddSubRepo:
    def test_adds_sub_repo(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        mgr.add_sub_repo("feature-fix", "core/pkg_b")

        meta = WorktreeMeta.load(meta_project.worktree_meta_path("feature-fix"))
        assert "core/pkg_b" in meta.sub_repos

        sub = meta_project.worktree_ws_path("feature-fix") / "src" / "core" / "pkg_b"
        assert sub.is_dir()

    def test_raises_if_already_present(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        with pytest.raises(WorktreeExistsError):
            mgr.add_sub_repo("feature-fix", "core/pkg_a")


class TestRemoveSubRepo:
    def test_removes_sub_repo(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a", "core/pkg_b"])
        mgr.remove_sub_repo("feature-fix", "core/pkg_b")

        meta = WorktreeMeta.load(meta_project.worktree_meta_path("feature-fix"))
        assert "core/pkg_b" not in meta.sub_repos
        assert "core/pkg_a" in meta.sub_repos

    def test_raises_if_not_in_worktree(self, meta_project: Config) -> None:
        mgr = MetaWorkspaceManager(meta_project)
        mgr.create_worktree("feature-fix", ["core/pkg_a"])
        with pytest.raises(SubRepoNotFoundError):
            mgr.remove_sub_repo("feature-fix", "core/pkg_b")
