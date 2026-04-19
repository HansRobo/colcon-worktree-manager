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
    """Sync the tracked repository with the remote and rebuild the base workspace."""
    try:
        root = find_project_root()
        config = Config.load(root)

        if config.repo is None:
            raise CWMError(
                "No repository selected.\n"
                "Run: cwm repo switch <path>"
            )

        repo_path = config.repo_path
        if not repo_path or not repo_path.exists():
            raise CWMError(
                f"Tracked repository not found: {repo_path}\n"
                "Clone your repository into src/ first."
            )

        click.echo(f"Pulling {config.repo}...")
        git.pull(cwd=repo_path)
        click.echo("  Pull complete.")

        if no_build:
            click.echo("Skipping build (--no-build).")
            return

        click.echo("Building base workspace...")
        build_args = []
        if config.symlink_install:
            build_args.append("--symlink-install")
        run_colcon_build(config.project_root, build_args)
        click.echo("Base workspace updated successfully.")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
