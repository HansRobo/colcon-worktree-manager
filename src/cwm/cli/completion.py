"""Shell completion callbacks for the cwm CLI."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable

import click
from click.shell_completion import CompletionItem


@lru_cache(maxsize=1)
def _load_config_and_manager():
    from cwm.core.config import Config
    from cwm.core.worktree_state import WorktreeStateManager
    from cwm.util.filesystem import find_project_root

    root = find_project_root()
    config = Config.load(root)
    return config, WorktreeStateManager(config)


def _match(items: Iterable[str], incomplete: str) -> list[CompletionItem]:
    return [CompletionItem(s) for s in items if s.startswith(incomplete)]


def suppress_completion(ctx: click.Context, param: click.Parameter, incomplete: str) -> list:
    """Return no completions, suppressing Click's fallback to filesystem completion.

    Used on variadic ``colcon_args`` so tab-completion does not surface the
    workspace's build/ directory (compopt -o default).
    """
    return []


def complete_worktree_branches(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with existing worktree branch names."""
    try:
        _, manager = _load_config_and_manager()
        return _match((m.branch for m in manager.list_worktrees()), incomplete)
    except Exception:
        return []


def complete_git_branches(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with git branch names from the tracked repository."""
    try:
        from cwm.util.git import list_branches

        config, _ = _load_config_and_manager()
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
        config, manager = _load_config_and_manager()
        items.extend(m.branch for m in manager.list_worktrees())
        branch = os.environ.get("CWM_WORKTREE")
        if os.environ.get("CWM_WORKSPACE") and branch:
            try:
                meta = manager.get_worktree_meta(branch)
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
        _, manager = _load_config_and_manager()
        target = ctx.params.get("target")
        if not target:
            return []
        meta = manager.get_worktree_meta(target)
        if meta.repo:
            return _match([meta.repo_name], incomplete)
        return []
    except Exception:
        return []
