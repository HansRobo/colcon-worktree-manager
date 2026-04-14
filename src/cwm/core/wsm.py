"""Worktree State Manager - lifecycle management for CWM worktrees."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from cwm.core.config import Config
from cwm.errors import BranchNameCollisionError, GitError, WorktreeNotFoundError
from cwm.util import git
from cwm.util.fs import ensure_dir


@dataclass
class WorktreeMeta:
    """Persisted metadata for a single worktree."""

    branch: str
    created_at: str
    base_sha: str
    sub_repos: list = field(default_factory=list)
    sub_repo_shas: dict = field(default_factory=dict)
    sub_repo_branches: dict = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            yaml.safe_dump(asdict(self), fh, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> WorktreeMeta:
        with open(path) as fh:
            data = yaml.safe_load(fh)
        data.pop("mode", None)
        data.setdefault("sub_repos", [])
        data.setdefault("sub_repo_shas", {})
        data.setdefault("sub_repo_branches", {})
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
        underlay: str,
    ) -> Config:
        """Initialise a new CWM project at *project_root*.

        Creates .cwm/ metadata directories and worktrees/ directory.
        The project root is treated as the base colcon workspace; an existing
        src/ tree is adopted as-is.
        """
        config = Config(
            underlay=underlay,
            project_root=project_root,
        )

        # Create CWM metadata dirs and the overlay worktrees directory
        ensure_dir(config.cwm_dir / "worktrees")
        ensure_dir(config.cwm_dir / "cache")
        ensure_dir(config.worktrees_path)

        config.save()
        return config

    # -- Worktree lifecycle ----------------------------------------------------

    def create_worktree(
        self,
        branch: str,
        sub_repos: list[str],
    ) -> Path:
        """Create a new overlay worktree for *branch*.

        *sub_repos* is a list of sub-repository paths (relative to
        ``base_ws/src/``) to add as git worktrees.

        Returns the workspace root path (worktrees/<branch>_ws/).
        """
        # Detect branch name collision (e.g. feature/foo vs feature-foo → same directory)
        safe_name = self._cfg.safe_branch_name(branch)
        for existing in self.list_worktrees():
            if existing.branch != branch and self._cfg.safe_branch_name(existing.branch) == safe_name:
                raise BranchNameCollisionError(
                    f"Branch '{branch}' conflicts with existing worktree '{existing.branch}' "
                    f"(both map to '{safe_name}_ws'). Use a different branch name."
                )

        from cwm.core.meta_wsm import MetaWorkspaceManager
        return MetaWorkspaceManager(self._cfg).create_worktree(branch, sub_repos)

    def remove_worktree(self, branch: str, *, force: bool = False) -> None:
        """Remove an overlay worktree and its build artifacts."""
        from cwm.core.meta_wsm import MetaWorkspaceManager
        MetaWorkspaceManager(self._cfg).remove_worktree(branch, force=force)

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

    def prune_stale(self, branches: list[str] | None = None) -> list[str]:
        """Remove metadata for worktrees whose workspace directory no longer exists.

        If *branches* is provided, only those branches are pruned (skips the scan).
        Also runs ``git worktree prune`` on the base repository to clean up stale
        git worktree entries.  Returns the list of pruned branch names.
        """
        if branches is None:
            branches = [
                meta.branch for meta in self.list_worktrees()
                if not self._cfg.worktree_ws_path(meta.branch).exists()
            ]

        for branch in branches:
            self._cfg.worktree_meta_path(branch).unlink(missing_ok=True)

        if self._cfg.base_src_path.exists():
            try:
                git.worktree_prune(cwd=self._cfg.base_src_path)
            except GitError:
                pass

        return branches

    def update_base_sha(self, branch: str) -> tuple[str, str]:
        """Update the change-detection baseline SHA(s) for *branch* to the current merge-base.

        Returns (old_sha, new_sha).  In meta mode each sub-repo SHA is updated.
        """
        meta_path = self._cfg.worktree_meta_path(branch)
        if not meta_path.exists():
            raise WorktreeNotFoundError(f"No metadata for worktree '{branch}'")
        meta = WorktreeMeta.load(meta_path)

        old_sha = next(iter(meta.sub_repo_shas.values()), meta.base_sha)
        new_shas: dict[str, str] = {}
        for rel in meta.sub_repos:
            sub_src = self._cfg.base_src_path / rel
            try:
                new_shas[rel] = git.get_head_sha(cwd=sub_src)
            except GitError:
                new_shas[rel] = meta.sub_repo_shas.get(rel, "")
        meta.sub_repo_shas = new_shas
        new_sha = next(iter(new_shas.values()), old_sha)

        meta.save(meta_path)
        return old_sha, new_sha
