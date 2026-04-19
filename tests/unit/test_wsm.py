"""Unit tests for WorktreeStateManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cwm.core.config import COLCON_IGNORE, Config
from cwm.core.wsm import WorktreeMeta, WorktreeStateManager
from cwm.errors import (
    NoRepoSelectedError,
    WorktreeExistsError,
    WorktreeNotFoundError,
)
from tests.conftest import make_git_repo


@pytest.fixture
def project(tmp_path: Path) -> Config:
    """Minimal project with one git repo under src/."""
    root = tmp_path / "project"
    root.mkdir()

    config = Config(
        underlay="/opt/ros/jazzy",
        repo="my_repo",
        project_root=root,
    )
    for d in [
        config.cwm_dir / "worktrees",
        config.cwm_dir / "cache",
        config.worktrees_path,
    ]:
        d.mkdir(parents=True)

    make_git_repo(config.base_src_path / "my_repo")
    config.save()
    return config


class TestCreateWorktree:
    def test_creates_workspace_dirs(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        ws = wsm.create_worktree("feature-fix")

        assert (ws / "build").is_dir()
        assert (ws / "install").is_dir()
        assert (ws / "log").is_dir()

    def test_creates_git_worktree(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")

        checkout = project.worktree_ws_path("feature-fix") / "src" / "my_repo"
        assert checkout.is_dir()
        assert (checkout / ".git").exists()

    def test_saves_metadata(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")

        meta = WorktreeMeta.load(project.worktree_meta_path("feature-fix"))
        assert meta.branch == "feature-fix"
        assert meta.repo == "my_repo"
        assert meta.base_sha != ""
        assert meta.base_branch == "main"

    def test_raises_if_already_exists(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")
        with pytest.raises(WorktreeExistsError):
            wsm.create_worktree("feature-fix")

    def test_raises_when_no_repo_selected(self, tmp_path: Path) -> None:
        root = tmp_path / "no_repo"
        root.mkdir()
        config = Config(underlay="/opt/ros/jazzy", repo=None, project_root=root)
        (config.cwm_dir / "worktrees").mkdir(parents=True)
        wsm = WorktreeStateManager(config)
        with pytest.raises(NoRepoSelectedError):
            wsm.create_worktree("feature-fix")

    def test_places_colcon_ignore_marker(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")
        assert (project.worktrees_path / COLCON_IGNORE).is_file()


class TestRemoveWorktree:
    def test_removes_workspace_and_meta(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")
        ws = project.worktree_ws_path("feature-fix")

        wsm.remove_worktree("feature-fix")

        assert not ws.exists()
        assert not project.worktree_meta_path("feature-fix").exists()

    def test_idempotent_when_checkout_already_deleted(self, project: Config) -> None:
        """Core bug fix: remove must not fail when ws_path was manually deleted."""
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")
        ws = project.worktree_ws_path("feature-fix")

        import shutil
        shutil.rmtree(ws)

        # Must not raise WorktreeNotFoundError
        wsm.remove_worktree("feature-fix")

        assert not project.worktree_meta_path("feature-fix").exists()

    def test_idempotent_when_meta_already_deleted(self, project: Config) -> None:
        """Remove must clean up git side even if meta is missing."""
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")
        meta_path = project.worktree_meta_path("feature-fix")
        meta_path.unlink()

        # Must not raise; git worktree remove + prune should run
        wsm.remove_worktree("feature-fix")

        assert not project.worktree_ws_path("feature-fix").exists()

    def test_remove_calls_git_prune(self, project: Config) -> None:
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")

        with patch("cwm.util.git.worktree_prune") as mock_prune:
            wsm.remove_worktree("feature-fix")

        mock_prune.assert_called_once()

    def test_delete_branch_flag(self, project: Config) -> None:
        from cwm.util import git as gitutil
        wsm = WorktreeStateManager(project)
        wsm.create_worktree("feature-fix")

        wsm.remove_worktree("feature-fix", delete_branch=True)

        assert not gitutil.branch_exists("feature-fix", cwd=project.base_src_path / "my_repo")
