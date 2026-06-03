"""cwm ws test / cwm ws test-result - smart diff-based colcon test."""

from __future__ import annotations

import click

from cwm.cli._workspace import resolve_worktree, run_workspace_colcon
from cwm.cli.completion import complete_worktree_branches, suppress_completion
from cwm.cli.main import ws
from cwm.errors import CWMError
from cwm.util.colcon_runner import run_colcon_test_result


@ws.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.option(
    "-w", "--worktree",
    "worktree_branch",
    default=None,
    metavar="BRANCH",
    shell_complete=complete_worktree_branches,
    help="Test the given worktree without entering a subshell.",
)
@click.option("--dry-run", is_flag=True, help="Show the colcon command without executing.")
@click.option(
    "--no-rdeps",
    is_flag=True,
    help="Skip reverse dependency analysis (test changed packages only).",
)
@click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED, shell_complete=suppress_completion)
def test(worktree_branch: str | None, dry_run: bool, no_rdeps: bool, colcon_args: tuple[str, ...]) -> None:
    """Run tests for changed packages and their reverse dependencies.

    Must be run with an active workspace (source <(cwm activate <branch>))
    or with -w/--worktree. Any extra arguments are forwarded to colcon test.

    Note: ``colcon test`` exits 0 even when tests fail; run ``cwm ws test-result``
    afterwards to get the pass/fail summary and a meaningful exit code.
    """
    try:
        run_workspace_colcon(
            "test",
            worktree_branch=worktree_branch,
            no_rdeps=no_rdeps,
            dry_run=dry_run,
            colcon_args=colcon_args,
            generate_args=lambda cdc, cs, _config: cdc.generate_test_args(cs.changed, cs.affected),
            done_message="Tests finished. Run 'cwm ws test-result' to view the summary and pass/fail status.",
        )
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


@ws.command(
    name="test-result",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "-w", "--worktree",
    "worktree_branch",
    default=None,
    metavar="BRANCH",
    shell_complete=complete_worktree_branches,
    help="Inspect the given worktree without entering a subshell.",
)
@click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED, shell_complete=suppress_completion)
def test_result(worktree_branch: str | None, colcon_args: tuple[str, ...]) -> None:
    """Show the test result summary and exit non-zero if any test failed.

    Runs ``colcon test-result --all --return-code-on-test-failure`` so that
    agents and CI can detect real test failures (which ``colcon test`` hides
    behind a zero exit code). Reads the build artifacts only, so no environment
    sourcing is required.
    """
    try:
        _branch, ws_path, _config = resolve_worktree(worktree_branch, command="ws test-result")
        run_colcon_test_result(ws_path, list(colcon_args))
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
