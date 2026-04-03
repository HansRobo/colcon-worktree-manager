"""cwm build - smart diff-based colcon build."""

from __future__ import annotations

import os
from pathlib import Path

import click

from cwm.cli.main import cli
from cwm.core.cdc import ColconDiscoveryController
from cwm.core.config import Config
from cwm.core.dga import DependencyGraphAnalyzer
from cwm.errors import CWMError, NotInSubshellError
from cwm.util.colcon_runner import run_colcon_build
from cwm.util.fs import find_project_root


def _require_subshell() -> tuple[str, Path]:
    """Verify we are inside a CWM subshell.

    Returns (branch_name, workspace_path).
    """
    branch = os.environ.get("CWM_WORKTREE")
    ws_str = os.environ.get("CWM_WORKSPACE")
    if not branch or not ws_str:
        raise NotInSubshellError(
            "cwm build must be run inside a CWM subshell. Use 'cwm enter <branch>' first."
        )
    return branch, Path(ws_str)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show the colcon command without executing.")
@click.option(
    "--no-rdeps",
    is_flag=True,
    help="Skip reverse dependency analysis (unsafe, faster).",
)
@click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED)
def build(dry_run: bool, no_rdeps: bool, colcon_args: tuple[str, ...]) -> None:
    """Build changed packages and their reverse dependencies.

    Any extra arguments after ``--`` are forwarded to colcon build.
    """
    try:
        branch, ws_path = _require_subshell()
        root = find_project_root()
        config = Config.load(root)

        src_path = config.worktree_src_path(branch)

        click.echo("Scanning packages...")
        dga = DependencyGraphAnalyzer()
        dga.scan(src_path)
        click.echo(f"  Found {len(dga.packages)} packages")

        click.echo("Detecting changes...")
        cdc = ColconDiscoveryController(src_path, config.base_ws.branch)

        if config.is_meta:
            from cwm.core.wsm import WorktreeMeta
            meta = WorktreeMeta.load(config.worktree_meta_path(branch))
            changed_files = cdc.get_changed_files_meta(meta.sub_repos, meta.sub_repo_shas)
            changed = cdc.get_changed_packages(dga, changed_files)
        else:
            changed = cdc.get_changed_packages(dga)

        if not changed:
            click.echo("No changed packages detected. Nothing to build.")
            return

        click.echo(f"  Changed: {', '.join(sorted(changed))}")

        # Compute reverse dependencies to prevent ABI/ODR violations
        if no_rdeps:
            affected: set[str] = set()
        else:
            affected = dga.get_reverse_deps(changed)
            if affected:
                click.echo(f"  Affected (reverse deps): {', '.join(sorted(affected))}")

        all_build = changed | affected
        build_order = dga.topological_sort(all_build)
        click.echo(f"  Build order: {' -> '.join(build_order)}")

        colcon_extra = cdc.generate_build_args(
            changed,
            affected,
            symlink_install=config.base_ws.symlink_install,
        )
        colcon_extra.extend(colcon_args)

        if dry_run:
            click.echo()
            click.echo("Dry run - would execute:")
            click.echo(f"  cd {ws_path}")
            click.echo(f"  colcon build {' '.join(colcon_extra)}")
            return

        click.echo()
        run_colcon_build(ws_path, colcon_extra)
        click.echo()
        click.echo("Build complete.")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
