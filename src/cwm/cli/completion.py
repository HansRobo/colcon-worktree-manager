"""Shell completion callbacks for the cwm CLI."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable

import click
from click.shell_completion import CompletionItem


@lru_cache(maxsize=1)
def _load_config_and_wsm():
    from cwm.core.config import Config
    from cwm.core.wsm import WorktreeStateManager
    from cwm.util.fs import find_project_root

    root = find_project_root()
    config = Config.load(root)
    return config, WorktreeStateManager(config)


def _match(items: Iterable[str], incomplete: str) -> list[CompletionItem]:
    return [CompletionItem(s) for s in items if s.startswith(incomplete)]


def complete_worktree_branches(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with existing worktree branch names."""
    try:
        _, wsm = _load_config_and_wsm()
        return _match((m.branch for m in wsm.list_worktrees()), incomplete)
    except Exception:
        return []


def complete_git_branches(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with git branch names from the tracked repository."""
    try:
        from cwm.util.git import list_branches

        config, _ = _load_config_and_wsm()
        cwd = config.repo_path or config.project_root
        return _match(list_branches(cwd=cwd, include_remote=True), incomplete)
    except Exception:
        return []


def complete_distros(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with available ROS 2 distro paths under /opt/ros/."""
    try:
        from cwm.util.ros_env import list_available_distros

        return _match(list_available_distros(), incomplete)
    except Exception:
        return []


def complete_cd_targets(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete cwm cd first argument: 'base', branch names, and active repo name."""
    items = ["base"]
    try:
        config, wsm = _load_config_and_wsm()
        items.extend(m.branch for m in wsm.list_worktrees())
        branch = os.environ.get("CWM_WORKTREE")
        if os.environ.get("CWM_WORKSPACE") and branch:
            try:
                meta = wsm.get_worktree_meta(branch)
                if meta.repo:
                    items.append(meta.repo_name)
            except Exception:
                pass
    except Exception:
        pass
    return _match(items, incomplete)


def complete_cd_repos(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete cwm cd second argument with the repo name for the branch in ctx.params['target']."""
    try:
        _, wsm = _load_config_and_wsm()
        target = ctx.params.get("target")
        if not target:
            return []
        meta = wsm.get_worktree_meta(target)
        if meta.repo:
            return _match([meta.repo_name], incomplete)
        return []
    except Exception:
        return []
