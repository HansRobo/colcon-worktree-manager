"""Worktree State Manager - lifecycle management for CWM worktrees."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cwm.core.config import BaseWorkspaceConfig, Config
from cwm.errors import WorktreeExistsError, WorktreeNotFoundError
from cwm.util import git
from cwm.util.fs import ensure_dir


@dataclass
class WorktreeMeta:
    """Persisted metadata for a single worktree."""

    branch: str
    created_at: str
    base_sha: str  # SHA of the base branch when the worktree was created

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            yaml.safe_dump(asdict(self), fh, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> WorktreeMeta:
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return cls(**data)


class WorktreeStateManager:
    """Orchestrates project initialisation and worktree lifecycle."""

    def __init__(self, config: Config) -> None:
        self._cfg = config

    # -- Project initialisation ------------------------------------------------

    @staticmethod
    def init_project(
        project_root: Path,
        *,
        underlay: str = "/opt/ros/jazzy",
        base_branch: str = "main",
    ) -> Config:
        """Initialise a new CWM project at *project_root*.

        Creates .cwm/, base_ws/ directory structure and writes config.yaml.
        The caller is expected to populate base_ws/src/ with the repository
        clone separately.
        """
        config = Config(
            underlay=underlay,
            base_ws=BaseWorkspaceConfig(branch=base_branch),
            project_root=project_root,
        )

        # Create directory scaffolding
        ensure_dir(config.cwm_dir / "worktrees")
        ensure_dir(config.cwm_dir / "cache")
        ensure_dir(config.base_ws_path / "src")
        ensure_dir(config.base_ws_path / "build")
        ensure_dir(config.base_ws_path / "install")
        ensure_dir(config.base_ws_path / "log")
        ensure_dir(config.worktrees_path)

        config.save()
        return config

    # -- Worktree lifecycle ----------------------------------------------------

    def create_worktree(self, branch: str) -> Path:
        """Create a new overlay worktree for *branch*.

        Returns the workspace root path (worktrees/<branch>_ws/).
        """
        ws_path = self._cfg.worktree_ws_path(branch)
        src_path = self._cfg.worktree_src_path(branch)

        if ws_path.exists():
            raise WorktreeExistsError(
                f"Worktree workspace already exists: {ws_path}"
            )

        # Create workspace directories
        ensure_dir(ws_path / "build")
        ensure_dir(ws_path / "install")
        ensure_dir(ws_path / "log")

        # Add git worktree
        git.worktree_add(
            src_path,
            branch,
            create_branch=True,
            cwd=self._cfg.base_src_path,
        )

        # Save metadata
        meta = WorktreeMeta(
            branch=branch,
            created_at=datetime.now(timezone.utc).isoformat(),
            base_sha=git.get_head_sha(cwd=self._cfg.base_src_path),
        )
        meta.save(self._cfg.worktree_meta_path(branch))

        return ws_path

    def remove_worktree(self, branch: str, *, force: bool = False) -> None:
        """Remove an overlay worktree and its build artifacts."""
        ws_path = self._cfg.worktree_ws_path(branch)
        src_path = self._cfg.worktree_src_path(branch)

        if not ws_path.exists():
            raise WorktreeNotFoundError(
                f"Worktree workspace not found: {ws_path}"
            )

        # Remove the git worktree
        if src_path.exists():
            git.worktree_remove(src_path, force=force, cwd=self._cfg.base_src_path)

        # Remove workspace directory tree
        shutil.rmtree(ws_path)

        # Remove metadata
        self._cfg.worktree_meta_path(branch).unlink(missing_ok=True)

    def list_worktrees(self) -> list[WorktreeMeta]:
        """Return metadata for all managed worktrees."""
        meta_dir = self._cfg.cwm_dir / "worktrees"
        if not meta_dir.exists():
            return []
        metas: list[WorktreeMeta] = []
        for path in sorted(meta_dir.glob("*.yaml")):
            metas.append(WorktreeMeta.load(path))
        return metas

    def get_worktree_meta(self, branch: str) -> WorktreeMeta:
        """Load metadata for a specific worktree."""
        meta_path = self._cfg.worktree_meta_path(branch)
        if not meta_path.exists():
            raise WorktreeNotFoundError(
                f"No metadata for worktree '{branch}'"
            )
        return WorktreeMeta.load(meta_path)
