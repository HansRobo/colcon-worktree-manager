"""cwm ws build - smart diff-based colcon build."""

from __future__ import annotations

import click

from cwm.cli._workspace import run_workspace_colcon
from cwm.cli.completion import complete_worktree_branches, suppress_completion
from cwm.cli.main import ws
from cwm.errors import CWMError


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
@click.option(
    "--rdeps-depth",
    type=int,
    default=None,
    metavar="N",
    help="Limit reverse dependency rebuild to N levels (1 = direct consumers only).",
)
@click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED, shell_complete=suppress_completion)
def build(
    worktree_branch: str | None,
    dry_run: bool,
    no_rdeps: bool,
    rdeps_depth: int | None,
    colcon_args: tuple[str, ...],
) -> None:
    """Build changed packages and their reverse dependencies.

    Must be run with an active workspace (source <(cwm activate <branch>))
    or with -w/--worktree. Any extra arguments after ``--`` are forwarded to colcon build.
    """
    if no_rdeps and rdeps_depth is not None:
        raise click.UsageError("--no-rdeps and --rdeps-depth are mutually exclusive.")
    elif rdeps_depth is not None and rdeps_depth < 1:
        raise click.UsageError("--rdeps-depth must be 1 or greater.")
    try:
        run_workspace_colcon(
            "build",
            worktree_branch=worktree_branch,
            no_rdeps=no_rdeps,
            rdeps_depth=rdeps_depth,
            dry_run=dry_run,
            colcon_args=colcon_args,
            generate_args=lambda discovery, changeset, config: discovery.generate_build_args(
                changeset.changed, changeset.affected, symlink_install=config.symlink_install
            ),
            show_build_order=True,
            done_message="Build complete.",
        )
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
