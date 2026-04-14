"""cwm build - smart diff-based colcon build."""

from __future__ import annotations

import os
from pathlib import Path

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import cli
from cwm.core.cdc import ColconDiscoveryController
from cwm.core.config import Config
from cwm.core.dga import DependencyGraphAnalyzer
from cwm.errors import CWMError, NotActivatedError
from cwm.util.colcon_runner import run_colcon_build, run_colcon_build_sourced
from cwm.util.fs import find_project_root


def _resolve_worktree(worktree_branch: str | None) -> tuple[str, Path, Config]:
    """Resolve branch and workspace path from -w flag or current subshell env vars.

    Returns (branch, workspace_path, config).
    """
    root = find_project_root()
    config = Config.load(root)

    if worktree_branch:
        ws_path = config.worktree_ws_path(worktree_branch)
        if not ws_path.exists():
            raise CWMError(
                f"Worktree workspace not found: {ws_path}\n"
                f"Create it first with: cwm worktree add {worktree_branch}"
            )
        return worktree_branch, ws_path, config

    branch = os.environ.get("CWM_WORKTREE")
    ws_str = os.environ.get("CWM_WORKSPACE")
    if not branch or not ws_str:
        raise NotActivatedError(
            "cwm build requires an active CWM workspace or the -w/--worktree flag.\n"
            "  Activate:  source <(cwm activate <branch>)\n"
            "  Or:        cwm build -w <branch>"
        )
    return branch, Path(ws_str), config


@cli.command()
@click.option(
    "-w", "--worktree",
    "worktree_branch",
    default=None,
    metavar="BRANCH",
    shell_complete=complete_worktree_branches,
    help="Build the given worktree without entering a subshell.",
)
@click.option("--dry-run", is_flag=True, help="Show the colcon command without executing.")
@click.option(
    "--no-rdeps",
    is_flag=True,
    help="Skip reverse dependency analysis (unsafe, faster).",
)
# shell_complete suppresses Click's fallback to filesystem completion (compopt -o default),
# which would otherwise surface the workspace's build/ directory as a tab-completion candidate.
@click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED, shell_complete=lambda ctx, param, incomplete: [])
def build(worktree_branch: str | None, dry_run: bool, no_rdeps: bool, colcon_args: tuple[str, ...]) -> None:
    """Build changed packages and their reverse dependencies.

    Must be run with an active workspace (source <(cwm activate <branch>))
    or with -w/--worktree. Any extra arguments after ``--`` are forwarded to colcon build.
    """
    try:
        branch, ws_path, config = _resolve_worktree(worktree_branch)
        src_path = config.worktree_src_path(branch)

        click.echo("Scanning packages...")
        dga = DependencyGraphAnalyzer()
        dga.scan(src_path)
        click.echo(f"  Found {len(dga.packages)} packages")

        click.echo("Detecting changes...")
        cdc = ColconDiscoveryController(src_path)

        from cwm.core.wsm import WorktreeMeta
        meta = WorktreeMeta.load(config.worktree_meta_path(branch))
        changed_files = cdc.get_changed_files_meta(meta.sub_repos, meta.sub_repo_shas)
        changed = cdc.get_changed_packages(dga, changed_files)

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
            symlink_install=config.symlink_install,
        )
        colcon_extra.extend(colcon_args)

        if dry_run:
            click.echo()
            click.echo("Dry run - would execute:")
            click.echo(f"  cd {ws_path}")
            click.echo(f"  colcon build {' '.join(colcon_extra)}")
            return

        click.echo()
        if not worktree_branch:
            run_colcon_build(ws_path, colcon_extra)
        else:
            run_colcon_build_sourced(
                ws_path,
                underlay_install=config.base_install_path,
                overlay_install=config.worktree_install_path(branch),
                extra_args=colcon_extra,
            )
        click.echo()
        click.echo("Build complete.")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
