"""cwm init - initialise a CWM project."""

from __future__ import annotations

from pathlib import Path

import click

from cwm.cli.completion import complete_distros
from cwm.cli.main import cli
from cwm.core.config import CONFIG_DIR
from cwm.core.wsm import WorktreeStateManager
from cwm.util.ros_env import ROS_INSTALL_BASE, detect_system_underlay, list_available_distros


@cli.command()
@click.option(
    "--underlay",
    default=None,
    shell_complete=complete_distros,
    help="Path to an additional ROS 2 underlay (auto-detected if omitted).",
)
def init(underlay: str) -> None:
    """Initialise a CWM project in the current directory.

    The current directory is treated as the base colcon workspace.
    If src/ already contains repositories, they are adopted as-is.
    """
    project_root = Path.cwd().resolve()

    if (project_root / CONFIG_DIR).is_dir():
        raise click.ClickException(
            f"CWM project already initialised at {project_root}"
        )

    if underlay is None:
        available = list_available_distros()
        detected = detect_system_underlay(available)
        if detected is None:
            if available:
                hint = f"Found: {', '.join(available)}. Use --underlay to specify one."
            else:
                hint = f"No ROS 2 installation found under {ROS_INSTALL_BASE}. Use --underlay to specify the path."
            raise click.ClickException(f"Could not auto-detect ROS 2 underlay. {hint}")
        underlay = detected
        click.echo(f"Auto-detected ROS 2 underlay: {underlay}")

    underlay_path = Path(underlay)
    if not underlay_path.is_dir():
        raise click.ClickException(f"Underlay path does not exist: {underlay}")

    src_path = project_root / "src"
    has_existing_src = src_path.is_dir() and any(src_path.iterdir())

    config = WorktreeStateManager.init_project(
        project_root,
        underlay=underlay,
    )

    if has_existing_src:
        click.echo(f"Adopted existing workspace at {project_root}")
    else:
        click.echo(f"Initialised CWM project at {project_root}")
    click.echo(f"  Underlay:      {config.underlay}")
    click.echo(f"  Worktrees dir: {config.worktrees_path}")
    click.echo()
    click.echo("Next steps:")
    if has_existing_src:
        click.echo("  1. Create a worktree: cwm worktree add <branch>")
        click.echo("  2. Activate the environment: source <(cwm activate <branch>)")
        click.echo("  3. Build changed packages: cwm build")
    else:
        click.echo("  1. Clone your repositories into src/")
        click.echo("  2. Build the base workspace: colcon build --symlink-install")
        click.echo("  3. Create a worktree: cwm worktree add <branch>")
