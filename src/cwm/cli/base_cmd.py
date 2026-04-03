"""cwm base update - sync and rebuild the base workspace."""

from __future__ import annotations

import click

from cwm.cli.main import base
from cwm.core.config import Config
from cwm.errors import CWMError
from cwm.util import git
from cwm.util.colcon_runner import run_colcon_build
from cwm.util.fs import find_project_root


@base.command()
@click.option(
    "--no-build",
    is_flag=True,
    help="Only pull the latest changes without building.",
)
def update(no_build: bool) -> None:
    """Sync the base workspace with the main branch and rebuild."""
    try:
        root = find_project_root()
        config = Config.load(root)
        src_path = config.base_src_path

        if not src_path.exists():
            raise CWMError(
                f"Base workspace source not found: {src_path}\n"
                "Clone your repository into base_ws/src/ first."
            )

        # Pull latest changes
        click.echo(f"Pulling latest changes on branch '{config.base_ws.branch}'...")
        git.pull(cwd=src_path)
        click.echo("  Pull complete.")

        if no_build:
            click.echo("Skipping build (--no-build).")
            return

        # Build base workspace
        click.echo("Building base workspace...")
        build_args = []
        if config.base_ws.symlink_install:
            build_args.append("--symlink-install")
        run_colcon_build(config.base_ws_path, build_args)
        click.echo("Base workspace updated successfully.")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
