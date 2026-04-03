"""cwm base update - sync and rebuild the base workspace."""

from __future__ import annotations

import shutil
import subprocess

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
            if config.is_meta:
                raise CWMError(
                    f"Base workspace source not found: {src_path}\n"
                    "Populate it with: vcs import base_ws/src < your.repos"
                )
            raise CWMError(
                f"Base workspace source not found: {src_path}\n"
                "Clone your repository into base_ws/src/ first."
            )

        if config.is_meta:
            vcs = shutil.which("vcs")
            if vcs is None:
                raise CWMError(
                    "Meta-repository update requires the 'vcs' tool (vcstool).\n"
                    "Install it with: pip install vcstool\n"
                    "Then run: vcs pull base_ws/src"
                )
            click.echo("Pulling sub-repositories with vcs...")
            result = subprocess.run([vcs, "pull", str(src_path)], check=False)
            if result.returncode != 0:
                raise CWMError(f"vcs pull failed with exit code {result.returncode}")
            click.echo("  vcs pull complete.")
        else:
            # Pull latest changes (single-repo mode only)
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
