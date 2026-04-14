"""CWM CLI entry point and top-level command groups."""

from __future__ import annotations

import os
from pathlib import Path

import click

from cwm import __version__
from cwm.errors import CWMError, NotActivatedError
from cwm.util.colcon_runner import run_colcon


class HelpfulCommand(click.Command):
    """Command that shows full help on usage errors instead of 'Try --help'."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.UsageError as e:
            click.echo(ctx.get_help(), err=True)
            click.echo(err=True)
            click.secho(f"Error: {e.format_message()}", fg="red", err=True)
            ctx.exit(2)


class HelpfulGroup(click.Group):
    """Group that shows full help on usage errors instead of 'Try --help'."""

    command_class = HelpfulCommand
    group_class = type  # Subgroups use the same class

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.UsageError as e:
            click.echo(ctx.get_help(), err=True)
            click.echo(err=True)
            click.secho(f"Error: {e.format_message()}", fg="red", err=True)
            ctx.exit(2)

    def get_command(self, ctx: click.Context, name: str) -> click.BaseCommand | None:
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd
        return _make_colcon_passthrough(name)

    def resolve_command(self, ctx: click.Context, args: list[str]):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as e:
            click.echo(ctx.get_help(), err=True)
            click.echo(err=True)
            click.secho(f"Error: {e.format_message()}", fg="red", err=True)
            ctx.exit(2)


def _make_colcon_passthrough(verb: str) -> click.Command:
    """Return a Click command that forwards ``cwm <verb> [args...]`` to ``colcon <verb> [args...]``.

    The workspace is taken from the active CWM environment variables set by
    ``cwm activate``.  Raises NotActivatedError when no workspace is active.
    """

    @click.command(
        name=verb,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
        help=f"Forward to ``colcon {verb}`` in the active worktree workspace.",
    )
    @click.argument("colcon_args", nargs=-1, type=click.UNPROCESSED)
    def _passthrough(colcon_args: tuple[str, ...]) -> None:
        try:
            ws_str = os.environ.get("CWM_WORKSPACE")
            if not ws_str:
                raise NotActivatedError(
                    f"cwm {verb} requires an active CWM workspace.\n"
                    "  Activate:  source <(cwm activate <branch>)"
                )
            run_colcon(verb, Path(ws_str), list(colcon_args))
        except CWMError as exc:
            raise click.ClickException(str(exc)) from exc

    return _passthrough


@click.group(cls=HelpfulGroup)
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
from cwm.cli.worktree_cmd import add, ls, prune, rebase, rm  # noqa: E402, F401
from cwm.cli.focus_cmd import focus  # noqa: E402, F401
from cwm.cli.build_cmd import build  # noqa: E402, F401
from cwm.cli.activate_cmd import activate  # noqa: E402, F401
from cwm.cli.shell_init_cmd import shell_init  # noqa: E402, F401
from cwm.cli.base_cmd import update  # noqa: E402, F401
from cwm.cli.clean_cmd import clean  # noqa: E402, F401
from cwm.cli.status_cmd import status  # noqa: E402, F401
from cwm.cli.env_cmd import env  # noqa: E402, F401
from cwm.cli.detect_cmd import detect  # noqa: E402, F401
