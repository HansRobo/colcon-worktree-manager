"""cwm worktree {add, rm, list, focus} - manage overlay worktrees."""

from __future__ import annotations

import sys

import click

from cwm.cli.completion import complete_git_branches, complete_sub_repos, complete_worktree_branches
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
@click.argument("branch", shell_complete=complete_git_branches)
@click.option(
    "--repos",
    "repos",
    multiple=True,
    metavar="PATH",
    shell_complete=complete_sub_repos,
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
            from cwm.util.repos import discover_sub_repos
            available = sorted(discover_sub_repos(config.base_src_path))
            if not available:
                raise click.ClickException(
                    "No sub-repositories found in base_ws/src/.\n"
                    "Populate it first: vcs import base_ws/src < your.repos"
                )
            if sys.stdin.isatty():
                click.echo("Available sub-repositories in base_ws/src/:")
                for i, rel in enumerate(available, 1):
                    click.echo(f"  [{i}] {rel}")
                click.echo()
                raw = click.prompt(
                    "Select sub-repositories (comma-separated numbers, e.g. 1,3)"
                )
                selected: list[str] = []
                for token in raw.split(","):
                    token = token.strip()
                    try:
                        idx = int(token) - 1
                        if 0 <= idx < len(available):
                            selected.append(available[idx])
                        else:
                            raise click.ClickException(f"Invalid selection: {token}")
                    except ValueError:
                        raise click.ClickException(f"Invalid input: {token!r}")
                if not selected:
                    raise click.ClickException("No sub-repositories selected.")
                repos = tuple(selected)
            else:
                click.echo("Available sub-repositories in base_ws/src/:", err=True)
                for rel in available:
                    click.echo(f"  {rel}", err=True)
                click.echo(err=True)
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
@click.argument("branch", shell_complete=complete_worktree_branches)
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes. Skips confirmation.")
def rm(branch: str, force: bool) -> None:
    """Remove the overlay worktree for BRANCH."""
    try:
        config, wsm = _load()
        if not force:
            ws_path = config.worktree_ws_path(branch)
            click.echo("This will permanently remove:")
            click.echo(f"  Branch:    {branch}")
            click.echo(f"  Workspace: {ws_path}")
            click.confirm("Continue?", abort=True)
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


@worktree.command("prune")
@click.option("--force", is_flag=True, help="Remove stale metadata without confirmation.")
def prune(force: bool) -> None:
    """Remove metadata for worktrees whose workspace directory no longer exists.

    Also runs 'git worktree prune' to clean up stale git worktree entries.
    """
    try:
        config, wsm = _load()
        metas = wsm.list_worktrees()
        stale_branches = [m.branch for m in metas if not config.worktree_ws_path(m.branch).exists()]

        if not stale_branches:
            click.echo("No stale worktrees found.")
            return

        click.echo("Stale worktrees (workspace directory missing):")
        for branch in stale_branches:
            click.echo(f"  {branch}")
        click.echo()

        if not force:
            click.confirm("Remove stale metadata?", abort=True)

        pruned = wsm.prune_stale(stale_branches)
        for branch in pruned:
            click.echo(f"  Pruned: {branch}")
        click.echo(f"Pruned {len(pruned)} stale worktree(s).")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


@worktree.command("rebase")
@click.argument("branch", shell_complete=complete_worktree_branches)
def rebase(branch: str) -> None:
    """Update the change-detection baseline for BRANCH to the current HEAD.

    This does NOT perform a git rebase. It resets the SHA used by 'cwm build'
    to detect which packages changed, useful after rebasing or long-running branches.
    """
    try:
        _, wsm = _load()
        old_sha, new_sha = wsm.update_base_sha(branch)
        if old_sha == new_sha:
            click.echo(f"Baseline already up to date: {new_sha[:12]}")
        else:
            click.echo(f"Updated baseline for '{branch}':")
            click.echo(f"  {old_sha[:12]} → {new_sha[:12]}")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
