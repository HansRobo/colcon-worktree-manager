"""Meta-repository workspace manager - lifecycle management for meta-mode worktrees."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from cwm.core.config import Config
from cwm.core.wsm import WorktreeMeta
from cwm.errors import GitError, SubRepoNotFoundError, WorktreeExistsError, WorktreeNotFoundError
from cwm.util import git
from cwm.util.fs import ensure_dir
from cwm.util.repos import validate_sub_repo_paths


class MetaWorkspaceManager:
    """Orchestrates worktree lifecycle for meta-repository workspaces.

    In meta mode the worktree ``src/`` directory contains only the sub-repos
    the developer intends to modify, each added as an independent git worktree
    from its counterpart in ``base_ws/src/``.  All other packages are provided
    through the base workspace ``install/`` directory which is sourced as an
    intermediate underlay.
    """

    def __init__(self, config: Config) -> None:
        self._cfg = config

    # -- Worktree lifecycle ----------------------------------------------------

    def create_worktree(self, branch: str, sub_repo_paths: list[str]) -> Path:
        """Create a new overlay worktree workspace for *branch*.

        Only the sub-repositories listed in *sub_repo_paths* (relative to
        ``base_ws/src/``) are added as git worktrees.  All other packages are
        provided by the base install.

        Returns the workspace root path (``worktrees/<branch>_ws/``).
        """
        ws_path = self._cfg.worktree_ws_path(branch)
        if ws_path.exists():
            raise WorktreeExistsError(
                f"Worktree workspace already exists: {ws_path}"
            )

        base_src = self._cfg.base_src_path
        validate_sub_repo_paths(base_src, sub_repo_paths)

        # Create workspace scaffold
        ensure_dir(ws_path / "build")
        ensure_dir(ws_path / "install")
        ensure_dir(ws_path / "log")
        ensure_dir(ws_path / "src")

        sub_repo_shas: dict[str, str] = {}
        for rel in sub_repo_paths:
            self._add_sub_repo_worktree(branch, rel, sub_repo_shas)

        try:
            meta_sha = git.get_head_sha(cwd=self._cfg.project_root)
        except GitError:
            meta_sha = ""

        meta = WorktreeMeta(
            branch=branch,
            created_at=datetime.now(timezone.utc).isoformat(),
            base_sha=meta_sha,
            mode="meta",
            sub_repos=list(sub_repo_paths),
            sub_repo_shas=sub_repo_shas,
        )
        meta.save(self._cfg.worktree_meta_path(branch))
        return ws_path

    def remove_worktree(self, branch: str, *, force: bool = False) -> None:
        """Remove an overlay worktree and its build artifacts."""
        ws_path = self._cfg.worktree_ws_path(branch)
        if not ws_path.exists():
            raise WorktreeNotFoundError(
                f"Worktree workspace not found: {ws_path}"
            )

        meta = WorktreeMeta.load(self._cfg.worktree_meta_path(branch))
        base_src = self._cfg.base_src_path

        for rel in meta.sub_repos:
            worktree_sub = ws_path / "src" / rel
            if worktree_sub.exists():
                git.worktree_remove(worktree_sub, force=force, cwd=base_src / rel)

        shutil.rmtree(ws_path)
        self._cfg.worktree_meta_path(branch).unlink(missing_ok=True)

    def add_sub_repo(self, branch: str, sub_repo_path: str) -> None:
        """Add a sub-repository worktree to an existing workspace.

        *sub_repo_path* is the path relative to ``base_ws/src/``.
        """
        ws_path = self._cfg.worktree_ws_path(branch)
        if not ws_path.exists():
            raise WorktreeNotFoundError(
                f"Worktree workspace not found: {ws_path}"
            )

        meta_path = self._cfg.worktree_meta_path(branch)
        meta = WorktreeMeta.load(meta_path)

        if sub_repo_path in meta.sub_repos:
            raise WorktreeExistsError(
                f"Sub-repository '{sub_repo_path}' is already in worktree '{branch}'"
            )

        validate_sub_repo_paths(self._cfg.base_src_path, [sub_repo_path])

        self._add_sub_repo_worktree(branch, sub_repo_path, meta.sub_repo_shas)
        meta.sub_repos.append(sub_repo_path)
        meta.save(meta_path)

    def remove_sub_repo(self, branch: str, sub_repo_path: str) -> None:
        """Remove a sub-repository worktree from an existing workspace.

        The git worktree is removed but other workspace directories are kept.
        """
        ws_path = self._cfg.worktree_ws_path(branch)
        if not ws_path.exists():
            raise WorktreeNotFoundError(
                f"Worktree workspace not found: {ws_path}"
            )

        meta_path = self._cfg.worktree_meta_path(branch)
        meta = WorktreeMeta.load(meta_path)

        if sub_repo_path not in meta.sub_repos:
            raise SubRepoNotFoundError(
                f"Sub-repository '{sub_repo_path}' is not in worktree '{branch}'"
            )

        worktree_sub = ws_path / "src" / sub_repo_path
        base_sub = self._cfg.base_src_path / sub_repo_path
        if worktree_sub.exists():
            git.worktree_remove(worktree_sub, cwd=base_sub)

        meta.sub_repos.remove(sub_repo_path)
        meta.sub_repo_shas.pop(sub_repo_path, None)
        meta.save(meta_path)

    # -- Internal helpers ------------------------------------------------------

    def _add_sub_repo_worktree(
        self,
        branch: str,
        rel: str,
        sub_repo_shas: dict[str, str],
    ) -> None:
        """Create a git worktree for a single sub-repository.

        Creates the parent directory structure if needed, then runs
        ``git worktree add`` from the base sub-repo directory.
        """
        ws_path = self._cfg.worktree_ws_path(branch)
        target = ws_path / "src" / rel
        base_sub = self._cfg.base_src_path / rel

        # Ensure parent directory exists (e.g., src/core/)
        ensure_dir(target.parent)

        git.worktree_add(target, branch, create_branch=True, cwd=base_sub)
        sub_repo_shas[rel] = git.get_head_sha(cwd=base_sub)
