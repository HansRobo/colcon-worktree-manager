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

# Walk up from $PWD looking for .cwm/.  No reliance on CWM_ACTIVE so that an
# activated shell which has cd'd into an unrelated repo does not hijack git.
# Guards against fixed-point dirname (e.g. dirname '.' -> '.') by breaking when
# the parent stops changing.
__cwm_in_project() {
    local dir prev
    dir="$PWD"
    while [[ -n "$dir" ]]; do
        [[ -d "$dir/.cwm" ]] && return 0
        [[ "$dir" == "/" ]] && return 1
        prev="$dir"
        dir="$(dirname "$dir")"
        [[ "$dir" == "$prev" ]] && return 1
    done
    return 1
}

# Return success if the real git subcommand is 'worktree', skipping any leading
# global options.  Options that take a separate value ('-C <path>', '-c <kv>',
# '--git-dir <path>', ...) are skipped in pairs so the value is not mistaken for
# the subcommand; otherwise 'git -C <path> worktree ...' would slip through.
__cwm_git_has_worktree() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -C|-c|--git-dir|--work-tree|--namespace|--super-prefix)
                shift 2 || return 1 ;;
            -*) shift ;;
            worktree) return 0 ;;
            *) return 1 ;;
        esac
    done
    return 1
}

# Intercept 'git worktree' inside CWM projects and forward to the CWM hook.
# All other git invocations (and 'git worktree' outside a CWM project) fall
# through to the real binary via 'command git'.
git() {
    if __cwm_in_project; then
        # Fast path: a bare 'git worktree ...' strips the subcommand token.
        if [[ "$1" == "worktree" ]]; then
            shift
            command cwm worktree __git_hook "$@"
            return $?
        fi
        # Behind leading global options (e.g. 'git -C <path> worktree ...'),
        # forward the original arguments unshifted so the hook can refuse
        # repository-retargeting options instead of letting them slip through.
        if __cwm_git_has_worktree "$@"; then
            command cwm worktree __git_hook "$@"
            return $?
        fi
    fi
    command git "$@"
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
