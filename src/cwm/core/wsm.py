"""Worktree State Manager - lifecycle management for CWM worktrees."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cwm.core.config import Config
from cwm.errors import (
    BranchNameCollisionError,
    GitError,
    NoRepoSelectedError,
    WorktreeExistsError,
    WorktreeNotFoundError,
)
from cwm.util import git
from cwm.util.fs import ensure_dir


@dataclass
class WorktreeMeta:
    """Persisted metadata for a single worktree."""

    branch: str
    created_at: str
    repo: str         # relative path under src/ of the tracked repo at creation time
    base_sha: str
    base_branch: str = ""  # branch of the repo when the worktree was created

    @property
    def repo_name(self) -> str:
        return Path(self.repo).name if self.repo else ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            yaml.safe_dump(
                {
                    "branch": self.branch,
                    "created_at": self.created_at,
                    "repo": self.repo,
                    "base_sha": self.base_sha,
                    "base_branch": self.base_branch,
                },
                fh,
                default_flow_style=False,
            )

    @classmethod
    def load(cls, path: Path) -> WorktreeMeta:
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return cls(
            branch=data["branch"],
            created_at=data.get("created_at", ""),
            repo=data.get("repo", ""),
            base_sha=data.get("base_sha", ""),
            base_branch=data.get("base_branch", ""),
        )


class WorktreeStateManager:
    """Orchestrates project initialisation and worktree lifecycle."""

    def __init__(self, config: Config) -> None:
        self._cfg = config

    # -- Project initialisation ------------------------------------------------

    @staticmethod
    def init_project(
        project_root: Path,
        *,
        underlay: str,
        repo: str | None = None,
    ) -> Config:
        """Initialise a new CWM project at *project_root*.

        Creates .cwm/ metadata directories and worktrees/ directory.
        The project root is treated as the base colcon workspace; an existing
        src/ tree is adopted as-is.  *repo* is the relative path (under src/)
        of the git repository to track.
        """
        config = Config(
            underlay=underlay,
            repo=repo,
            project_root=project_root,
        )

        ensure_dir(config.cwm_dir / "worktrees")
        ensure_dir(config.cwm_dir / "cache")
        config.ensure_worktrees_ignore_marker()

        config.save()
        return config

    # -- Worktree lifecycle ----------------------------------------------------

    def create_worktree(self, branch: str) -> Path:
        """Create a new overlay worktree for *branch*.

        Uses the repository tracked in the config.  Returns the workspace root
        path (worktrees/<branch>_ws/).
        """
        if self._cfg.repo is None:
            raise NoRepoSelectedError(
                "No repository selected. Run 'cwm repo switch <path>' first."
            )

        safe_name = self._cfg.safe_branch_name(branch)
        for existing in self.list_worktrees():
            if existing.branch != branch and self._cfg.safe_branch_name(existing.branch) == safe_name:
                raise BranchNameCollisionError(
                    f"Branch '{branch}' conflicts with existing worktree '{existing.branch}' "
                    f"(both map to '{safe_name}_ws'). Use a different branch name."
                )

        repo_rel = self._cfg.repo
        base_repo = self._cfg.base_src_path / repo_rel
        repo_name = self._cfg.repo_name
        ws_path = self._cfg.worktree_ws_path(branch)

        if ws_path.exists():
            raise WorktreeExistsError(f"Worktree workspace already exists: {ws_path}")

        self._cfg.ensure_worktrees_ignore_marker()
        ensure_dir(ws_path / "build")
        ensure_dir(ws_path / "install")
        ensure_dir(ws_path / "log")
        checkout = ws_path / "src" / repo_name
        ensure_dir(checkout.parent)

        git.worktree_add(checkout, branch, create_branch=True, cwd=base_repo)

        try:
            base_sha = git.get_head_sha(cwd=base_repo)
        except GitError:
            base_sha = ""
        try:
            base_branch = git.get_current_branch(cwd=base_repo)
        except GitError:
            base_branch = ""

        WorktreeMeta(
            branch=branch,
            created_at=datetime.now(timezone.utc).isoformat(),
            repo=repo_rel,
            base_sha=base_sha,
            base_branch=base_branch,
        ).save(self._cfg.worktree_meta_path(branch))

        return ws_path

    def remove_worktree(
        self,
        branch: str,
        *,
        force: bool = False,
        delete_branch: bool = False,
    ) -> None:
        """Remove an overlay worktree and its build artifacts.

        Idempotent: safe to call even if the workspace directory was already
        manually deleted.  Always runs 'git worktree prune' to clean up stale
        git-side references.
        """
        meta_path = self._cfg.worktree_meta_path(branch)
        ws_path = self._cfg.worktree_ws_path(branch)
        meta = WorktreeMeta.load(meta_path) if meta_path.exists() else None

        repo_rel = meta.repo if (meta and meta.repo) else self._cfg.repo
        if repo_rel is None:
            raise NoRepoSelectedError(
                "Cannot determine which repository this worktree belongs to. "
                "Run 'cwm repo switch <path>' to set the tracked repository."
            )

        base_repo = self._cfg.base_src_path / repo_rel
        checkout = ws_path / "src" / Path(repo_rel).name

        if checkout.exists():
            try:
                git.worktree_remove(checkout, force=force, cwd=base_repo)
            except GitError:
                if not force:
                    raise

        if base_repo.is_dir():
            try:
                git.worktree_prune(cwd=base_repo)
            except GitError:
                pass

        if ws_path.exists():
            shutil.rmtree(ws_path)

        meta_path.unlink(missing_ok=True)

        if delete_branch and meta:
            try:
                git.branch_delete(meta.branch, force=True, cwd=base_repo)
            except GitError:
                pass

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
            raise WorktreeNotFoundError(f"No metadata for worktree '{branch}'")
        return WorktreeMeta.load(meta_path)

    def prune_stale(self, branches: list[str] | None = None) -> list[str]:
        """Remove metadata for worktrees whose workspace directory no longer exists.

        Also runs 'git worktree prune' to clean up stale git worktree entries.
        Returns the list of pruned branch names.
        """
        if branches is None:
            branches = [
                meta.branch for meta in self.list_worktrees()
                if not self._cfg.worktree_ws_path(meta.branch).exists()
            ]

        for branch in branches:
            self._cfg.worktree_meta_path(branch).unlink(missing_ok=True)

        if self._cfg.repo_path and self._cfg.repo_path.exists():
            try:
                git.worktree_prune(cwd=self._cfg.repo_path)
            except GitError:
                pass

        return branches
