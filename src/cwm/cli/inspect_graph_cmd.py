"""cwm inspect graph - show the package dependency DAG (scan-only)."""

from __future__ import annotations

import json

import click

from cwm.cli._workspace import resolve_worktree
from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import inspect
from cwm.core.dependency_graph import DependencyGraphAnalyzer
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
def graph(worktree_branch: str | None, as_json: bool) -> None:
    """Show the workspace package dependency graph (build/build_export edges).

    Scans the worktree ``src/`` and prints each package with its direct
    dependencies. Builds nothing. Requires an active workspace
    (source <(cwm activate <branch>)) or -w/--worktree.
    """
    try:
        branch, _ws_path, config = resolve_worktree(worktree_branch, command="inspect graph")
        src_path = config.worktree_src_path(branch)
        analyzer = DependencyGraphAnalyzer()
        analyzer.scan(src_path, cache_dir=config.dag_cache_dir)
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc

    edges = analyzer.forward_edges()

    if as_json:
        click.echo(json.dumps({
            "packages": {
                name: {"depends_on": sorted(edges[name])} for name in sorted(edges)
            }
        }, indent=2))
        return

    click.echo(f"Packages: {len(edges)}")
    for name in sorted(edges):
        deps = sorted(edges[name])
        if deps:
            click.echo(f"  {name} -> {', '.join(deps)}")
        else:
            click.echo(f"  {name}")
