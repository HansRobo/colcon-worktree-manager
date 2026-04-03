"""cwm enter - launch a sandboxed subshell for a worktree."""

from __future__ import annotations

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import cli
from cwm.core.config import Config
from cwm.errors import CWMError
from cwm.util.fs import find_project_root
from cwm.util.shell import create_rcfile, exec_subshell


@cli.command()
@click.argument("branch", shell_complete=complete_worktree_branches)
def enter(branch: str) -> None:
    """Enter a sandboxed subshell for the BRANCH worktree.

    The subshell sources the underlay (base_ws) environment and sets
    CWM-specific variables. Use 'exit' or Ctrl+D to leave.
    """
    try:
        root = find_project_root()
        config = Config.load(root)

        ws_path = config.worktree_ws_path(branch)
        if not ws_path.exists():
            raise CWMError(
                f"Worktree workspace not found: {ws_path}\n"
                f"Create it first with: cwm worktree add {branch}"
            )

        base_setup = config.base_install_path / "setup.bash"
        if not base_setup.exists():
            click.echo(
                click.style(
                    "Warning: base workspace has not been built. Environment will be incomplete.\n"
                    f"  Run: cd {config.base_ws_path} && colcon build --symlink-install",
                    fg="yellow",
                ),
                err=True,
            )
        elif not (config.worktree_install_path(branch) / "local_setup.bash").exists():
            click.echo(
                click.style(
                    f"Note: worktree '{branch}' has not been built yet. Run 'cwm build' after entering.",
                    fg="cyan",
                ),
                err=True,
            )

        rcfile = create_rcfile(
            branch=branch,
            worktree_ws=ws_path,
            underlay_install=config.base_install_path,
            overlay_install=config.worktree_install_path(branch),
        )

        # This replaces the current process - never returns
        exec_subshell(rcfile)

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
