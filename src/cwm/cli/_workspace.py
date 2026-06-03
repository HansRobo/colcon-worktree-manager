"""Shared helpers for diff-based workspace subcommands (``ws build`` / ``ws test``)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import click

from cwm.core.colcon_discovery import ColconDiscoveryController
from cwm.core.changeset import Changeset, compute_changeset
from cwm.core.config import Config
from cwm.errors import CWMError, NotActivatedError
from cwm.util.colcon_runner import run_colcon, run_colcon_sourced
from cwm.util.filesystem import find_project_root


def resolve_worktree(worktree_branch: str | None, *, command: str) -> tuple[str, Path, Config]:
    """Resolve (branch, workspace_path, config) from the -w flag or active env vars.

    With *worktree_branch* set, the workspace is resolved from config. Otherwise
    the current subshell's ``CWM_WORKTREE`` / ``CWM_WORKSPACE`` (set by
    ``cwm activate``) are used. *command* (e.g. "ws build", "ws test") is
    interpolated into the NotActivatedError hint so each subcommand prints an
    accurate message.
    """
    root = find_project_root()
    config = Config.load(root)

    if worktree_branch:
        ws_path = config.worktree_ws_path(worktree_branch)
        if not ws_path.exists():
            raise CWMError(
                f"Worktree workspace not found: {ws_path}\n"
                f"Create it first with: cwm worktree add {worktree_branch}"
            )
        return worktree_branch, ws_path, config

    branch = os.environ.get("CWM_WORKTREE")
    ws_str = os.environ.get("CWM_WORKSPACE")
    if not branch or not ws_str:
        raise NotActivatedError(
            f"cwm {command} requires an active CWM workspace or the -w/--worktree flag.\n"
            "  Activate:  source <(cwm activate <branch>)\n"
            f"  Or:        cwm {command} -w <branch>"
        )
    return branch, Path(ws_str), config


def run_workspace_colcon(
    subcommand: str,
    *,
    worktree_branch: str | None,
    no_rdeps: bool,
    dry_run: bool,
    colcon_args: tuple[str, ...],
    generate_args: Callable[[ColconDiscoveryController, Changeset, Config], list[str]],
    show_build_order: bool = False,
    done_message: str,
    rdeps_depth: int | None = None,
) -> None:
    """Run a diff-based ``colcon <subcommand>`` over a worktree's change set.

    Resolves the target worktree, scans for changed packages (plus ABI reverse
    deps unless *no_rdeps*, bounded to *rdeps_depth* levels when given),
    delegates colcon argument generation to *generate_args*, and either prints
    the command (*dry_run*) or runs it — inheriting the active environment, or
    sourcing underlay+overlay for ``-w``.
    """
    branch, ws_path, config = resolve_worktree(worktree_branch, command=f"ws {subcommand}")
    src_path = config.worktree_src_path(branch)

    click.echo("Scanning packages...")
    changeset = compute_changeset(config, branch, no_rdeps=no_rdeps, rdeps_depth=rdeps_depth)
    click.echo(f"  Found {changeset.package_count} packages")

    click.echo("Detecting changes...")
    if not changeset.changed:
        click.echo(f"No changed packages detected. Nothing to {subcommand}.")
        return

    click.echo(f"  Changed: {', '.join(sorted(changeset.changed))}")
    if changeset.affected:
        click.echo(f"  Affected (reverse deps): {', '.join(sorted(changeset.affected))}")
    if show_build_order:
        click.echo(f"  Build order: {' -> '.join(changeset.build_order)}")

    discovery = ColconDiscoveryController(src_path)
    colcon_extra = generate_args(discovery, changeset, config)
    colcon_extra.extend(colcon_args)

    if dry_run:
        click.echo()
        click.echo("Dry run - would execute:")
        click.echo(f"  cd {ws_path}")
        click.echo(f"  colcon {subcommand} {' '.join(colcon_extra)}")
        return

    click.echo()
    if not worktree_branch:
        run_colcon(subcommand, ws_path, colcon_extra)
    else:
        run_colcon_sourced(
            subcommand,
            ws_path,
            config.base_install_path,
            config.worktree_install_path(branch),
            colcon_extra,
        )
    click.echo()
    click.echo(done_message)
