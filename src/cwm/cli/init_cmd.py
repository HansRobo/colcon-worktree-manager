"""cwm init - initialise a CWM project."""

from __future__ import annotations

import sys
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
@click.option(
    "--repo",
    "repo_path",
    default=None,
    metavar="PATH",
    help="Repository to track (relative to src/). Auto-detected if omitted.",
)
def init(underlay: str, repo_path: str | None) -> None:
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

    # Determine which repo to track
    selected_repo: str | None = None
    if repo_path is not None:
        from cwm.util.repos import validate_repo_path
        from cwm.errors import RepoNotFoundError
        try:
            validate_repo_path(src_path, repo_path)
            selected_repo = repo_path
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc)) from exc
    elif has_existing_src:
        from cwm.util.repos import discover_sub_repos
        found = discover_sub_repos(src_path)
        if len(found) == 1:
            selected_repo = next(iter(found))
        elif len(found) > 1:
            selected_repo = _prompt_repo_selection(found)

    config = WorktreeStateManager.init_project(
        project_root,
        underlay=underlay,
        repo=selected_repo,
    )

    if has_existing_src:
        click.echo(f"Adopted existing workspace at {project_root}")
    else:
        click.echo(f"Initialised CWM project at {project_root}")
    click.echo(f"  Underlay:      {config.underlay}")
    click.echo(f"  Worktrees dir: {config.worktrees_path}")
    if config.repo:
        click.echo(f"  Tracked repo:  {config.repo}")
    click.echo()
    click.echo("Next steps:")
    if has_existing_src:
        if config.repo is None:
            click.echo("  0. Select a repository: cwm repo switch <path>")
        click.echo("  1. Create a worktree:   cwm worktree add <branch>")
        click.echo("  2. Activate:            source <(cwm activate <branch>)")
        click.echo("  3. Build:               cwm build")
    else:
        click.echo("  1. Clone your repository into src/")
        click.echo("  2. Select it:           cwm repo switch <path>")
        click.echo("  3. Build the base:      colcon build --symlink-install")
        click.echo("  4. Create a worktree:   cwm worktree add <branch>")


def _prompt_repo_selection(found: dict) -> str | None:
    """Interactively prompt the user to pick one repository from *found*.

    Returns the selected relative path, or None if non-interactive.
    """
    available = sorted(found.keys())
    if not sys.stdin.isatty():
        click.echo("Multiple repositories found in src/. Use --repo to specify one:", err=True)
        for rel in available:
            click.echo(f"  {rel}", err=True)
        raise click.ClickException(
            "Cannot auto-select repository in non-interactive mode.\n"
            "Use: cwm init --repo <path>"
        )

    click.echo("Multiple repositories found in src/:")
    for i, rel in enumerate(available, 1):
        click.echo(f"  [{i}] {rel}")
    click.echo()
    raw = click.prompt("Select repository (number, or press Enter to skip)")
    if not raw.strip():
        return None
    try:
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(available):
            return available[idx]
        raise click.ClickException(f"Invalid selection: {raw.strip()}")
    except ValueError:
        raise click.ClickException(f"Invalid input: {raw.strip()!r}")
