"""cwm worktree {add, rm, list, focus} - manage overlay worktrees."""

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
@click.option(
    "--repos",
    "repos",
    multiple=True,
    metavar="PATH",
    help=(
        "Sub-repository path (relative to base_ws/src/) to include as a git worktree. "
        "Required in meta mode. May be specified multiple times."
    ),
)
def add(branch: str, repos: tuple[str, ...]) -> None:
    """Create a new overlay worktree for BRANCH."""
    try:
        config, wsm = _load()

        if config.is_meta and not repos:
            # Show available sub-repos to help the user
            from cwm.util.repos import discover_sub_repos
            available = discover_sub_repos(config.base_src_path)
            if available:
                click.echo("Available sub-repositories in base_ws/src/:")
                for rel in sorted(available):
                    click.echo(f"  {rel}")
                click.echo()
            raise click.ClickException(
                "Meta-repository mode requires --repos to specify which "
                "sub-repositories to work on.\n"
                "Example: cwm worktree add <branch> --repos core/autoware_core"
            )

        if not config.is_meta and repos:
            raise click.ClickException(
                "--repos is only valid in meta-repository mode (cwm init --meta)."
            )

        sub_repos = list(repos) or None
        ws_path = wsm.create_worktree(branch, sub_repos=sub_repos)
        click.echo(f"Created worktree workspace: {ws_path}")
        click.echo(f"  Source:  {config.worktree_src_path(branch)}")
        click.echo(f"  Build:   {ws_path / 'build'}")
        click.echo(f"  Install: {ws_path / 'install'}")
        if sub_repos:
            click.echo(f"  Sub-repos: {', '.join(sub_repos)}")
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
            if meta.is_meta and meta.sub_repos:
                for rel in meta.sub_repos:
                    click.echo(f"    - {rel}")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
