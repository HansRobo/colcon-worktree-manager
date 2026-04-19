"""cwm repo {show, switch} - manage the tracked git repository."""

from __future__ import annotations

import click

from cwm.cli.main import cli
from cwm.core.config import Config
from cwm.errors import CWMError
from cwm.util import git
from cwm.util.fs import find_project_root
from cwm.util.repos import discover_sub_repos, validate_repo_path


@cli.group()
def repo() -> None:
    """Manage the tracked git repository for this CWM project."""


repo.command_order = ["show", "switch"]


@repo.command("show")
def show() -> None:
    """Show the currently tracked git repository."""
    try:
        root = find_project_root()
        config = Config.load(root)

        if config.repo is None:
            click.echo("No repository selected.")
            click.echo("Run: cwm repo switch <path>")
            return

        click.echo(f"Tracked repository: {config.repo}")
        repo_path = config.repo_path
        if repo_path and repo_path.exists():
            try:
                branch = git.get_current_branch(cwd=repo_path)
                sha = git.get_head_sha(cwd=repo_path)
                click.echo(f"  Branch: {branch}")
                click.echo(f"  HEAD:   {sha[:12]}")
            except CWMError:
                pass
        else:
            click.secho(f"  Warning: path does not exist: {repo_path}", fg="yellow")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


@repo.command("switch")
@click.argument("path")
def switch(path: str) -> None:
    """Switch the tracked repository to PATH (relative to src/).

    PATH should be a git repository under the src/ directory, e.g.
    'autoware.universe' or 'core/autoware_core'.
    """
    try:
        root = find_project_root()
        config = Config.load(root)

        if not config.base_src_path.exists():
            raise CWMError(
                f"src/ directory not found at {config.base_src_path}\n"
                "Clone your repository into src/ first."
            )

        validate_repo_path(config.base_src_path, path)

        old_repo = config.repo
        config.repo = path
        config.save()

        if old_repo and old_repo != path:
            click.echo(f"Switched tracked repository: {old_repo} → {path}")
        else:
            click.echo(f"Tracked repository set to: {path}")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


def _complete_repos(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list:
    from click.shell_completion import CompletionItem
    try:
        from cwm.util.fs import find_project_root
        root = find_project_root()
        config = Config.load(root)
        repos = discover_sub_repos(config.base_src_path)
        return [CompletionItem(r) for r in repos if r.startswith(incomplete)]
    except Exception:
        return []


switch.params[0].shell_complete = _complete_repos  # type: ignore[attr-defined]
