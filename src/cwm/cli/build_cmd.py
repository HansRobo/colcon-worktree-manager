"""cwm ws build - smart diff-based colcon build."""

from __future__ import annotations

import os
from pathlib import Path

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import ws
from cwm.core.cdc import ColconDiscoveryController
from cwm.core.changeset import compute_changeset
from cwm.core.config import Config
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
            "cwm ws build requires an active CWM workspace or the -w/--worktree flag.\n"
            "  Activate:  source <(cwm activate <branch>)\n"
            "  Or:        cwm ws build -w <branch>"
        )
    return branch, Path(ws_str), config


@ws.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
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
        cs = compute_changeset(config, branch, no_rdeps=no_rdeps)
        click.echo(f"  Found {cs.package_count} packages")

        click.echo("Detecting changes...")
        if not cs.changed:
            click.echo("No changed packages detected. Nothing to build.")
            return

        click.echo(f"  Changed: {', '.join(sorted(cs.changed))}")
        if cs.affected:
            click.echo(f"  Affected (reverse deps): {', '.join(sorted(cs.affected))}")
        click.echo(f"  Build order: {' -> '.join(cs.build_order)}")

        cdc = ColconDiscoveryController(src_path)
        colcon_extra = cdc.generate_build_args(
            cs.changed,
            cs.affected,
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
