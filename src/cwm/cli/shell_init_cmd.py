"""cwm shell-init - output the shell integration function for .bashrc."""

from __future__ import annotations

import click

from cwm.cli.main import cli

_SHELL_FUNCTION = """\
# cwm shell integration - allows 'cwm activate' to mutate the current shell.
# Add to ~/.bashrc:  eval "$(cwm shell-init)"
cwm() {
    case "$1" in
        activate)
            eval "$(command cwm "$@")"
            ;;
        deactivate)
            if declare -f deactivate >/dev/null 2>&1; then
                deactivate
            else
                echo "cwm: no active workspace to deactivate" >&2
                return 1
            fi
            ;;
        *)
            command cwm "$@"
            ;;
    esac
}
"""


@cli.command("shell-init")
def shell_init() -> None:
    """Output the shell integration function for .bashrc.

    Add the following line to your ~/.bashrc (or ~/.zshrc):

    \\b
        eval "$(cwm shell-init)"

    This defines a 'cwm' shell function that makes 'cwm activate' and
    'cwm deactivate' work directly without 'source <(...)'.
    """
    click.echo(_SHELL_FUNCTION, nl=False)
