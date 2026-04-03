"""CWM CLI entry point and top-level command groups."""

from __future__ import annotations

import click

from cwm import __version__


@click.group()
@click.version_option(version=__version__, prog_name="cwm")
def cli() -> None:
    """Colcon Worktree Manager - parallel ROS 2 development with git worktrees."""


@cli.group()
def worktree() -> None:
    """Manage worktree overlay workspaces."""


@cli.group()
def base() -> None:
    """Manage the base (underlay) workspace."""


# Import subcommands so they register with Click groups.
# The imports are intentionally at the bottom to avoid circular dependencies.
from cwm.cli.init_cmd import init  # noqa: E402, F401
from cwm.cli.worktree_cmd import add, ls, rm  # noqa: E402, F401
from cwm.cli.focus_cmd import focus  # noqa: E402, F401
from cwm.cli.build_cmd import build  # noqa: E402, F401
from cwm.cli.enter_cmd import enter  # noqa: E402, F401
from cwm.cli.base_cmd import update  # noqa: E402, F401
from cwm.cli.clean_cmd import clean  # noqa: E402, F401
