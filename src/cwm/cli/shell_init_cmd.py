"""cwm shell-init - output the shell integration function for .bashrc."""

from __future__ import annotations

import click

from cwm.cli.main import cli

_SHELL_FUNCTION = """\
# cwm shell integration - allows 'cwm activate', 'cwm cd', and 'cwm switch' to work in-shell.
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
        cd)
            shift
            local __cwm_path __cwm_ret
            __cwm_path="$(command cwm __cd-resolve "$@")"
            __cwm_ret=$?
            if [ $__cwm_ret -ne 0 ]; then
                echo "$__cwm_path" >&2
                return $__cwm_ret
            fi
            cd "$__cwm_path"
            ;;
        switch)
            local __cwm_branch __cwm_path __cwm_ret
            __cwm_branch="$2"
            shift 2
            eval "$(command cwm activate "$__cwm_branch")" || return $?
            __cwm_path="$(command cwm __cd-resolve --auto-subrepo "$@")"
            __cwm_ret=$?
            if [ $__cwm_ret -ne 0 ]; then
                echo "$__cwm_path" >&2
                return $__cwm_ret
            fi
            cd "$__cwm_path"
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

    This defines a 'cwm' shell function that makes 'cwm activate',
    'cwm deactivate', 'cwm cd', and 'cwm switch' work directly in the shell.
    """
    click.echo(_SHELL_FUNCTION, nl=False)
