"""cwm ws status - show overall state of base workspace and all worktrees."""

from __future__ import annotations

import json

import click

from cwm.cli.main import ws
from cwm.core.config import Config
from cwm.errors import CWMError, GitError
from cwm.util import git
from cwm.util.fs import find_project_root
from cwm.util.repos import discover_sub_repos


@ws.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (for scripting/agents).")
def status(as_json: bool) -> None:
    """Show the state of the base workspace and all worktrees."""
    try:
        root = find_project_root()
        config = Config.load(root)
        from cwm.core.wsm import WorktreeStateManager
        wsm = WorktreeStateManager(config)

        base_info = _collect_base(config)
        worktrees_info = _collect_worktrees(config, wsm)

        if as_json:
            click.echo(json.dumps({"base": base_info, "worktrees": worktrees_info}, indent=2))
            return

        _print_human(base_info, worktrees_info)

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


def _collect_base(config: Config) -> dict:
    setup_bash = config.base_install_path / "setup.bash"
    built = setup_bash.exists()

    dirty = False
    if config.base_src_path.exists():
        for abs_path in discover_sub_repos(config.base_src_path).values():
            try:
                if git.is_dirty(cwd=abs_path):
                    dirty = True
                    break
            except GitError:
                pass

    return {
        "built": built,
        "dirty": dirty,
    }


def _collect_worktrees(config: Config, wsm) -> list[dict]:
    metas = wsm.list_worktrees()
    result = []
    for meta in metas:
        ws_path = config.worktree_ws_path(meta.branch)
        exists = ws_path.exists()
        built = (config.worktree_install_path(meta.branch) / "local_setup.bash").exists()

        dirty = False
        ahead = 0
        if exists:
            for rel in meta.sub_repos:
                sub_path = config.worktree_src_path(meta.branch) / rel
                if not sub_path.is_dir():
                    continue
                if not dirty:
                    try:
                        if git.is_dirty(cwd=sub_path):
                            dirty = True
                    except GitError:
                        pass
                base_branch = meta.sub_repo_branches.get(rel)
                if base_branch:
                    try:
                        ahead = max(ahead, git.commits_ahead(base_branch, cwd=sub_path))
                    except GitError:
                        pass

        entry: dict = {
            "branch": meta.branch,
            "exists": exists,
            "built": built,
            "dirty": dirty,
            "ahead": ahead,
            "created_at": meta.created_at,
        }
        if meta.sub_repos:
            entry["sub_repos"] = meta.sub_repos
        result.append(entry)
    return result


def _print_human(base: dict, worktrees: list[dict]) -> None:
    built_mark = click.style("built", fg="green") if base["built"] else click.style("not built", fg="yellow")
    dirty_mark = click.style(" dirty", fg="red") if base["dirty"] else ""
    click.echo(f"Base workspace  {built_mark}{dirty_mark}")

    if not worktrees:
        click.echo()
        click.echo("No worktrees. Create one with: cwm worktree add <branch>")
        return

    click.echo()
    click.echo("Worktrees:")
    for wt in worktrees:
        if not wt["exists"]:
            status_str = click.style("missing", fg="red")
        elif wt["built"]:
            status_str = click.style("built", fg="green")
        else:
            status_str = click.style("not built", fg="yellow")

        dirty_str = click.style(" dirty", fg="red") if wt["dirty"] else ""
        ahead_str = f"  +{wt['ahead']} commit(s)" if wt["ahead"] else ""

        click.echo(f"  {wt['branch']}  {status_str}{dirty_str}{ahead_str}")
        if wt.get("sub_repos"):
            for sr in wt["sub_repos"]:
                click.echo(f"    - {sr}")
