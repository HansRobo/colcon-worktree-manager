"""cwm worktree {add, rm, list, focus} - manage overlay worktrees."""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

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


def _json_fail(msg: str) -> NoReturn:
    click.echo(json.dumps({"ok": False, "error": msg}))
    raise SystemExit(1)


def _json_ok(payload: dict[str, Any]) -> None:
    click.echo(json.dumps({"ok": True, **payload}))


@worktree.command()
@click.argument("branch", shell_complete=complete_git_branches)
@click.option(
    "--repos",
    "repos",
    multiple=True,
    metavar="PATH",
    shell_complete=complete_sub_repos,
    help=(
        "Sub-repository path (relative to src/) to include as a git worktree. "
        "May be specified multiple times. Auto-detected if omitted."
    ),
)
@click.option("--all-repos", is_flag=True, help="Automatically select all repositories in src/.")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def add(branch: str, repos: tuple[str, ...], all_repos: bool, as_json: bool) -> None:
    """Create a new overlay worktree for BRANCH."""
    try:
        config, wsm = _load()

        if repos and all_repos:
            msg = "--repos and --all-repos are mutually exclusive."
            if as_json:
                _json_fail(msg)
            raise click.ClickException(msg)

        if not repos:
            from cwm.util.repos import discover_sub_repos
            available = sorted(discover_sub_repos(config.base_src_path))
            if not available:
                msg = (
                    "No repositories found in src/.\n"
                    "Clone your repositories into src/ first."
                )
                if as_json:
                    _json_fail(msg)
                raise click.ClickException(msg)
            if len(available) == 1 or all_repos:
                repos = tuple(available)
            elif sys.stdin.isatty() and not as_json:
                click.echo("Available repositories in src/:")
                for i, rel in enumerate(available, 1):
                    click.echo(f"  [{i}] {rel}")
                click.echo()
                raw = click.prompt(
                    "Select repositories (comma-separated numbers, e.g. 1,3)"
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
                    raise click.ClickException("No repositories selected.")
                repos = tuple(selected)
            else:
                msg = (
                    "Multiple repositories found. Use --repos to specify which "
                    "repositories to work on, or --all-repos to select all.\n"
                    "Example: cwm worktree add <branch> --repos <repo-path>"
                )
                if as_json:
                    _json_fail(msg)
                click.echo("Available repositories in src/:", err=True)
                for rel in available:
                    click.echo(f"  {rel}", err=True)
                click.echo(err=True)
                raise click.ClickException(msg)

        sub_repos = list(repos)
        ws_path = wsm.create_worktree(branch, sub_repos=sub_repos)

        if as_json:
            _json_ok({
                "branch": branch,
                "ws_path": str(ws_path),
                "src_path": str(config.worktree_src_path(branch)),
                "sub_repos": sub_repos,
            })
        else:
            click.echo(f"Created worktree workspace: {ws_path}")
            click.echo(f"  Source:  {config.worktree_src_path(branch)}")
            click.echo(f"  Build:   {ws_path / 'build'}")
            click.echo(f"  Install: {ws_path / 'install'}")
            click.echo(f"  Repos:   {', '.join(sub_repos)}")
            click.echo()
            click.echo(f"Activate with: source <(cwm activate {branch})")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


@worktree.command("rm")
@click.argument("branch", shell_complete=complete_worktree_branches)
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes. Skips confirmation.")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def rm(branch: str, force: bool, as_json: bool) -> None:
    """Remove the overlay worktree for BRANCH."""
    try:
        config, wsm = _load()
        if not force and not as_json:
            ws_path = config.worktree_ws_path(branch)
            click.echo("This will permanently remove:")
            click.echo(f"  Branch:    {branch}")
            click.echo(f"  Workspace: {ws_path}")
            click.confirm("Continue?", abort=True)
        wsm.remove_worktree(branch, force=force)

        if as_json:
            _json_ok({"branch": branch})
        else:
            click.echo(f"Removed worktree: {branch}")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


@worktree.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def ls(as_json: bool) -> None:
    """List all managed worktrees."""
    try:
        config, wsm = _load()
        metas = wsm.list_worktrees()

        if as_json:
            worktrees = []
            for meta in metas:
                ws_path = config.worktree_ws_path(meta.branch)
                worktrees.append({
                    "branch": meta.branch,
                    "ws_path": str(ws_path),
                    "exists": ws_path.exists(),
                    "sub_repos": meta.sub_repos,
                    "created_at": meta.created_at,
                    "base_sha": meta.base_sha,
                })
            _json_ok({"worktrees": worktrees})
            return

        if not metas:
            click.echo("No worktrees. Create one with: cwm worktree add <branch>")
            return
        for meta in metas:
            ws_path = config.worktree_ws_path(meta.branch)
            status = "exists" if ws_path.exists() else "missing"
            click.echo(f"  {meta.branch}  ({status})  created {meta.created_at}")
            if meta.sub_repos:
                for rel in meta.sub_repos:
                    click.echo(f"    - {rel}")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
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
