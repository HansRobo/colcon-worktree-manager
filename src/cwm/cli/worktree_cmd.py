"""cwm worktree {add, remove, list, prune} - manage overlay worktrees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn

import click

from cwm.cli.completion import complete_git_branches, complete_worktree_branches
from cwm.cli.main import worktree
from cwm.core.config import Config
from cwm.core.wsm import WorktreeStateManager
from cwm.errors import CWMError
from cwm.util.fs import find_project_root


def _load() -> tuple[Config, WorktreeStateManager]:
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
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def add(branch: str, as_json: bool) -> None:
    """Create a new overlay worktree for BRANCH."""
    try:
        config, wsm = _load()
        ws_path = wsm.create_worktree(branch)
        repo_name = Path(config.repo).name if config.repo else ""
        src_path = config.worktree_src_path(branch) / repo_name

        if as_json:
            _json_ok({
                "branch": branch,
                "ws_path": str(ws_path),
                "src_path": str(src_path),
                "repo": config.repo,
            })
        else:
            click.echo(f"Created worktree workspace: {ws_path}")
            click.echo(f"  Repo:    {config.repo}")
            click.echo(f"  Source:  {src_path}")
            click.echo(f"  Build:   {ws_path / 'build'}")
            click.echo(f"  Install: {ws_path / 'install'}")
            click.echo()
            click.echo(f"Activate with: source <(cwm activate {branch})")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


@worktree.command("remove")
@click.argument("branch", shell_complete=complete_worktree_branches)
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes.")
@click.option("--delete-branch", is_flag=True, help="Also delete the git branch after removing the worktree.")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def remove(branch: str, force: bool, delete_branch: bool, as_json: bool) -> None:
    """Remove the overlay worktree for BRANCH."""
    try:
        config, wsm = _load()
        if not force and not as_json:
            ws_path = config.worktree_ws_path(branch)
            click.echo("This will permanently remove:")
            click.echo(f"  Branch:    {branch}")
            click.echo(f"  Workspace: {ws_path}")
            if delete_branch:
                click.echo("  (git branch will also be deleted)")
            click.confirm("Continue?", abort=True)
        wsm.remove_worktree(branch, force=force, delete_branch=delete_branch)

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
def list_worktrees_cmd(as_json: bool) -> None:
    """List all managed worktrees."""
    try:
        config, wsm = _load()
        metas = wsm.list_worktrees()

        if as_json:
            items = []
            for meta in metas:
                ws_path = config.worktree_ws_path(meta.branch)
                items.append({
                    "branch": meta.branch,
                    "repo": meta.repo,
                    "ws_path": str(ws_path),
                    "exists": ws_path.exists(),
                    "created_at": meta.created_at,
                    "base_sha": meta.base_sha,
                })
            _json_ok({"worktrees": items})
            return

        if not metas:
            click.echo("No worktrees. Create one with: cwm worktree add <branch>")
            return
        for meta in metas:
            ws_path = config.worktree_ws_path(meta.branch)
            status = "exists" if ws_path.exists() else click.style("missing", fg="red")
            repo_str = f"  [{meta.repo}]" if meta.repo else ""
            click.echo(f"  {meta.branch}  ({status}){repo_str}  created {meta.created_at}")
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
