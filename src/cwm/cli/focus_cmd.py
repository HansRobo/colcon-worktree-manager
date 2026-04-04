"""cwm worktree focus - add or remove sub-repo worktrees from an existing workspace."""

from __future__ import annotations

import click

from cwm.cli.completion import complete_sub_repos, complete_worktree_branches, complete_worktree_sub_repos
from cwm.cli.main import worktree
from cwm.core.config import Config
from cwm.core.meta_wsm import MetaWorkspaceManager
from cwm.core.wsm import WorktreeMeta
from cwm.errors import CWMError
from cwm.util.fs import find_project_root


def _load_meta() -> tuple[Config, MetaWorkspaceManager]:
    """Load config and create a MetaWorkspaceManager."""
    root = find_project_root()
    config = Config.load(root)
    return config, MetaWorkspaceManager(config)


@worktree.command("focus")
@click.argument("branch", shell_complete=complete_worktree_branches)
@click.option("--add", "add_repo", metavar="PATH", shell_complete=complete_sub_repos, help="Add a sub-repository worktree.")
@click.option("--rm", "rm_repo", metavar="PATH", shell_complete=complete_worktree_sub_repos, help="Remove a sub-repository worktree.")
@click.option("--list", "list_repos", is_flag=True, help="List active sub-repositories.")
def focus(branch: str, add_repo: str | None, rm_repo: str | None, list_repos: bool) -> None:
    """Add, remove, or list sub-repository worktrees for BRANCH.

    \b
    Examples:
      cwm worktree focus feature-fix --list
      cwm worktree focus feature-fix --add universe/autoware_universe
      cwm worktree focus feature-fix --rm universe/autoware_universe
    """
    if not any([add_repo, rm_repo, list_repos]):
        raise click.UsageError("Specify --add, --rm, or --list.")

    try:
        config, mgr = _load_meta()
        meta_path = config.worktree_meta_path(branch)

        if list_repos:
            meta = WorktreeMeta.load(meta_path)
            if not meta.sub_repos:
                click.echo(f"No sub-repositories in worktree '{branch}'.")
            else:
                click.echo(f"Sub-repositories in worktree '{branch}':")
                for rel in meta.sub_repos:
                    click.echo(f"  {rel}")

        if add_repo:
            mgr.add_sub_repo(branch, add_repo)
            click.echo(f"Added sub-repository worktree: {add_repo}")

        if rm_repo:
            mgr.remove_sub_repo(branch, rm_repo)
            click.echo(f"Removed sub-repository worktree: {rm_repo}")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
