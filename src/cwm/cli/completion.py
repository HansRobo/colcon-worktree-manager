"""Shell completion callbacks for the cwm CLI."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import click
from click.shell_completion import CompletionItem


# -- Cached loader (per process, safe for completion) ------------------------


@lru_cache(maxsize=1)
def _load_config_and_wsm():
    """Load Config and WSM once per completion invocation."""
    from cwm.core.config import Config
    from cwm.core.wsm import WorktreeStateManager
    from cwm.util.fs import find_project_root

    root = find_project_root()
    config = Config.load(root)
    return config, WorktreeStateManager(config)


# -- Internal helper ---------------------------------------------------------


def _match(items: Iterable[str], incomplete: str) -> list[CompletionItem]:
    return [CompletionItem(s) for s in items if s.startswith(incomplete)]


# -- Completion callbacks ----------------------------------------------------


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
    """Complete with git branch names (local + remote) for creating a new worktree."""
    try:
        from cwm.util.git import list_branches

        config, _ = _load_config_and_wsm()
        return _match(list_branches(cwd=config.project_root, include_remote=True), incomplete)
    except Exception:
        return []


def complete_sub_repos(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with discovered sub-repo relative paths under base_ws/src/."""
    try:
        from cwm.util.repos import discover_sub_repos

        config, _ = _load_config_and_wsm()
        return _match(discover_sub_repos(config.base_src_path), incomplete)
    except Exception:
        return []


def complete_worktree_sub_repos(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete with sub-repos active in the worktree named by ctx.params['branch']."""
    try:
        _, wsm = _load_config_and_wsm()
        branch = ctx.params.get("branch")
        if not branch:
            return []
        meta = wsm.get_worktree_meta(branch)
        return _match(meta.sub_repos or [], incomplete)
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
