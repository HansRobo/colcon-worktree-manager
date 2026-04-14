"""cwm clean - clean overlay build artifacts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import cli
from cwm.core.config import Config
from cwm.errors import CWMError, NotActivatedError
from cwm.util.fs import find_project_root

ARTIFACT_DIRS = ("build", "install", "log")


@cli.command()
@click.option(
    "-w", "--worktree",
    "worktree_branch",
    default=None,
    metavar="BRANCH",
    shell_complete=complete_worktree_branches,
    help="Clean the given worktree without entering a subshell.",
)
@click.option("--all", "clean_all", is_flag=True, help="Clean all worktree workspaces.")
@click.option("--base", "clean_base", is_flag=True, help="Also clean the base workspace (only with --all).")
def clean(worktree_branch: str | None, clean_all: bool, clean_base: bool) -> None:
    """Clean build artifacts (build/, install/, log/).

    Must be run with an active workspace (source <(cwm activate <branch>)),
    or use -w/--worktree to specify a branch, or --all to clean every worktree.
    """
    try:
        root = find_project_root()
        config = Config.load(root)

        targets: list[tuple[str, list[Path]]] = []

        if clean_all:
            if config.worktrees_path.exists():
                for ws_dir in sorted(config.worktrees_path.iterdir()):
                    if ws_dir.is_dir() and ws_dir.name.endswith("_ws"):
                        targets.append((ws_dir.name, _artifact_dirs(ws_dir)))
            if clean_base:
                targets.append(("base", _artifact_dirs(config.project_root)))
        elif worktree_branch:
            ws_path = config.worktree_ws_path(worktree_branch)
            targets.append((worktree_branch, _artifact_dirs(ws_path)))
        else:
            branch = os.environ.get("CWM_WORKTREE")
            if not branch:
                raise NotActivatedError(
                    "cwm clean requires an active CWM workspace, the -w/--worktree flag, "
                    "or --all.\n"
                    "  Activate:  source <(cwm activate <branch>)\n"
                    "  Or:        cwm clean -w <branch>"
                )
            targets.append((branch, _artifact_dirs(config.worktree_ws_path(branch))))

        if not targets:
            click.echo("Nothing to clean.")
            return

        for name, dirs in targets:
            for d in dirs:
                if d.is_dir():
                    click.echo(f"  Removing {d}")
                    shutil.rmtree(d)
            click.echo(f"  Cleaned: {name}")

        click.echo("Clean complete.")

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc


def _artifact_dirs(ws_path: Path) -> list[Path]:
    """Return build artifact directory paths for a workspace."""
    return [ws_path / name for name in ARTIFACT_DIRS]
