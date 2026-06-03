"""cwm inspect changed - dry-preview changed packages and their ABI rebuild set."""

from __future__ import annotations

import json

import click

from cwm.cli._workspace import resolve_worktree
from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import inspect
from cwm.core.changeset import compute_changeset
from cwm.errors import CWMError


@inspect.command()
@click.option(
    "-w", "--worktree",
    "worktree_branch",
    default=None,
    metavar="BRANCH",
    shell_complete=complete_worktree_branches,
    help="Inspect the given worktree without entering a subshell.",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (for scripting/agents).")
def changed(worktree_branch: str | None, as_json: bool) -> None:
    """Show changed packages and their reverse-dependency rebuild set.

    Runs the same change-detection pipeline as ``cwm ws build`` but builds
    nothing, so agents and humans can preview the build scope. Requires an
    active workspace (source <(cwm activate <branch>)) or -w/--worktree.
    """
    try:
        branch, _ws_path, config = resolve_worktree(worktree_branch, command="inspect changed")
        changeset = compute_changeset(config, branch)
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps({
            "changed": sorted(changeset.changed),
            "affected": sorted(changeset.affected),
            "build_order": changeset.build_order,
            "package_count": changeset.package_count,
        }, indent=2))
        return

    click.echo(f"Packages scanned: {changeset.package_count}")
    if not changeset.changed:
        click.echo("No changed packages detected.")
        return

    click.echo(f"Changed: {', '.join(sorted(changeset.changed))}")
    if changeset.affected:
        click.echo(f"Affected (reverse deps): {', '.join(sorted(changeset.affected))}")
    else:
        click.echo("Affected (reverse deps): none")
    click.echo(f"Build order: {' -> '.join(changeset.build_order)}")
