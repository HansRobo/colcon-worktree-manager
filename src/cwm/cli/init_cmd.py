"""cwm init - initialise a CWM project."""

from __future__ import annotations

from pathlib import Path

import click

from cwm.cli.main import cli
from cwm.core.config import CONFIG_DIR
from cwm.core.wsm import WorktreeStateManager
from cwm.util import git


@cli.command()
@click.option(
    "--underlay",
    default="/opt/ros/jazzy",
    show_default=True,
    help="Path to the ROS 2 underlay installation.",
)
@click.option(
    "--base-branch",
    default="main",
    show_default=True,
    help="Branch to use for the base workspace.",
)
def init(underlay: str, base_branch: str) -> None:
    """Initialise a CWM project in the current directory."""
    project_root = Path.cwd().resolve()

    # Guard: already initialised?
    if (project_root / CONFIG_DIR).is_dir():
        raise click.ClickException(
            f"CWM project already initialised at {project_root}"
        )

    # Validate underlay
    underlay_path = Path(underlay)
    if not underlay_path.is_dir():
        raise click.ClickException(f"Underlay path does not exist: {underlay}")

    # We expect to be inside a git repository (or the user will clone into base_ws/src)
    try:
        repo_root = git.get_toplevel(project_root)
    except Exception:
        repo_root = None

    config = WorktreeStateManager.init_project(
        project_root,
        underlay=underlay,
        base_branch=base_branch,
    )

    click.echo(f"Initialised CWM project at {project_root}")
    click.echo(f"  Underlay:       {config.underlay}")
    click.echo(f"  Base workspace: {config.base_ws_path}")
    click.echo(f"  Worktrees dir:  {config.worktrees_path}")
    if repo_root:
        click.echo(f"  Git repository: {repo_root}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Clone or symlink your ROS 2 source into base_ws/src/")
    click.echo("  2. Build the base workspace: cd base_ws && colcon build --symlink-install")
    click.echo("  3. Create a worktree: cwm worktree add <branch-name>")
