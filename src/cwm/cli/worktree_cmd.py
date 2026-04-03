"""cwm worktree {add, rm, list} - manage overlay worktrees."""

from __future__ import annotations

import click

from cwm.cli.main import worktree
from cwm.core.config import Config
from cwm.core.wsm import WorktreeStateManager
from cwm.errors import CWMError
from cwm.util.fs import find_project_root


def _load() -> tuple[Config, WorktreeStateManager]:
    """Load config and create a WSM instance from the current directory."""
    root = find_project_root()
    config = Config.load(root)
    return config, WorktreeStateManager(config)


@worktree.command()
@click.argument("branch")
def add(branch: str) -> None:
    """Create a new overlay worktree for BRANCH."""
    try:
        config, wsm = _load()
        ws_path = wsm.create_worktree(branch)
        click.echo(f"Created worktree workspace: {ws_path}")
        click.echo(f"  Source:  {config.worktree_src_path(branch)}")
        click.echo(f"  Build:   {ws_path / 'build'}")
        click.echo(f"  Install: {ws_path / 'install'}")
        click.echo()
        click.echo(f"Enter with: cwm enter {branch}")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


@worktree.command("rm")
@click.argument("branch")
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes.")
def rm(branch: str, force: bool) -> None:
    """Remove the overlay worktree for BRANCH."""
    try:
        _, wsm = _load()
        wsm.remove_worktree(branch, force=force)
        click.echo(f"Removed worktree: {branch}")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


@worktree.command("list")
def ls() -> None:
    """List all managed worktrees."""
    try:
        config, wsm = _load()
        metas = wsm.list_worktrees()
        if not metas:
            click.echo("No worktrees. Create one with: cwm worktree add <branch>")
            return
        for meta in metas:
            ws_path = config.worktree_ws_path(meta.branch)
            status = "exists" if ws_path.exists() else "missing"
            click.echo(f"  {meta.branch}  ({status})  created {meta.created_at}")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
