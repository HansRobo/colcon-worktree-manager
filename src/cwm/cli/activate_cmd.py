"""cwm activate - output a shell activation script for a worktree."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import cli
from cwm.core.config import Config
from cwm.errors import CWMError
from cwm.util.fs import find_project_root


# Environment variables that ROS/colcon sourcing will mutate and that the
# generated deactivate() function must restore.
_SNAPSHOT_VARS = (
    "PATH",
    "LD_LIBRARY_PATH",
    "PYTHONPATH",
    "CMAKE_PREFIX_PATH",
    "AMENT_PREFIX_PATH",
    "COLCON_PREFIX_PATH",
    "ROS_DISTRO",
    "ROS_VERSION",
    "ROS_PYTHON_VERSION",
    "ROS_LOCALHOST_ONLY",
)

_TTY_HINT = """\
cwm activate requires shell integration to mutate the current shell.

  Set up once (add to ~/.bashrc):
    eval "$(cwm shell-init)"

  Then use directly:
    cwm activate <branch>   # activate a specific worktree
    cwm activate            # interactive selection
    cwm deactivate          # restore previous environment
"""


def _bash_completion_script() -> str:
    """Return the cwm bash completion script using Click's API directly."""
    try:
        from click.shell_completion import BashComplete
        return BashComplete(cli, {}, "cwm", "_CWM_COMPLETE").source()
    except Exception:
        return ""


def generate_activate_script(
    branch: str,
    project_root: str,
    workspace: str,
    underlay: str,
    base_install: str,
    overlay_install: str,
) -> str:
    """Return a bash activation script for the given worktree.

    Intended to be consumed via: source <(cwm activate <branch>)
    """
    q_branch = shlex.quote(branch)
    q_root = shlex.quote(project_root)
    q_workspace = shlex.quote(workspace)
    q_underlay = shlex.quote(underlay)
    q_base_install = shlex.quote(base_install)
    q_overlay_install = shlex.quote(overlay_install)

    # Build snapshot/restore blocks for the env vars ROS sourcing mutates.
    save_lines = []
    restore_lines = []
    for var in _SNAPSHOT_VARS:
        save_lines.append(
            f'    if [ -n "${{{var}+x}}" ]; then\n'
            f'        export _CWM_OLD_{var}="${{{var}}}"\n'
            f'    else\n'
            f'        unset _CWM_OLD_{var}\n'
            f'        export _CWM_WAS_UNSET_{var}=1\n'
            f'    fi'
        )
        restore_lines.append(
            f'    if [ -n "${{_CWM_WAS_UNSET_{var}+x}}" ]; then\n'
            f'        unset {var}\n'
            f'        unset _CWM_WAS_UNSET_{var}\n'
            f'    elif [ -n "${{_CWM_OLD_{var}+x}}" ]; then\n'
            f'        export {var}="${{_CWM_OLD_{var}}}"\n'
            f'        unset _CWM_OLD_{var}\n'
            f'    fi'
        )

    save_block = "\n".join(save_lines)
    restore_block = "\n".join(restore_lines)

    completion_script = _bash_completion_script()

    return f"""\
# cwm activation script - source this file, do not execute it directly.
# Usage: source <(cwm activate {q_branch})

# Auto-deactivate any currently active workspace before activating a new one.
if [ -n "${{CWM_ACTIVE+x}}" ]; then
    if type deactivate >/dev/null 2>&1; then
        deactivate
    fi
fi

# Snapshot environment variables that ROS/colcon sourcing will mutate.
{save_block}
export _CWM_OLD_PS1="${{PS1:-}}"

# Source ROS 2 distro underlay.
if [ -f {q_underlay}/setup.bash ]; then
    source {q_underlay}/setup.bash
fi

# Source base workspace install.
if [ -f {q_base_install}/setup.bash ]; then
    source {q_base_install}/setup.bash
fi

# Source overlay workspace (skipped silently before first build).
if [ -f {q_overlay_install}/local_setup.bash ]; then
    source {q_overlay_install}/local_setup.bash
fi

# Export CWM workspace markers.
export CWM_ACTIVE=1
export CWM_PROJECT_ROOT={q_root}
export CWM_WORKTREE={q_branch}
export CWM_WORKSPACE={q_workspace}

# Modify the shell prompt.
if [ -n "${{PS1+x}}" ]; then
    export PS1="[cwm:{q_branch}] ${{PS1}}"
fi

# Define the deactivate function that undoes everything above.
deactivate() {{
{restore_block}
    if [ -n "${{_CWM_OLD_PS1+x}}" ]; then
        export PS1="${{_CWM_OLD_PS1}}"
        unset _CWM_OLD_PS1
    fi
    unset CWM_ACTIVE CWM_PROJECT_ROOT CWM_WORKTREE CWM_WORKSPACE
    unset -f deactivate
}}

# cwm shell completion - embedded at activation time.
{completion_script}

echo ""
echo "=== CWM Worktree: {q_branch} ==="
echo "  Workspace: {q_workspace}"
echo "  Run 'cwm ws build' to build changed packages."
echo "  Run 'deactivate' to restore the previous environment."
echo ""
"""


def generate_create_and_activate_script(
    branch: str,
    project_root: str,
    workspace: str,
    underlay: str,
    base_install: str,
    overlay_install: str,
) -> str:
    """Return a bash script that creates a worktree then activates it."""
    q_branch = shlex.quote(branch)
    activate_script = generate_activate_script(
        branch=branch,
        project_root=project_root,
        workspace=workspace,
        underlay=underlay,
        base_install=base_install,
        overlay_install=overlay_install,
    )
    return f"""\
# Create the worktree, then activate it.
cwm worktree add {q_branch} || exit 1
{activate_script}"""


def _list_existing_worktrees(config: Config) -> list[str]:
    """Return branch names of existing worktrees, sorted."""
    from cwm.core.wsm import WorktreeStateManager
    wsm = WorktreeStateManager(config)
    return [m.branch for m in wsm.list_worktrees()]


def _interactive_select(config: Config) -> tuple[str, bool] | None:
    """Show an interactive menu on /dev/tty and return (branch, is_new).

    Returns None if the user cancels.
    is_new=True means the worktree does not exist yet and must be created.
    """
    existing = _list_existing_worktrees(config)

    try:
        tty = open("/dev/tty", "r+")
    except OSError:
        raise click.ClickException(
            "Cannot open /dev/tty for interactive selection. "
            "Provide a branch name: cwm activate <branch>"
        )

    with tty:
        tty.write("\n=== CWM Activate ===\n\n")

        options: list[tuple[str, bool]] = []  # (label, is_new)
        for b in existing:
            options.append((b, False))
        options.append(("[Create new worktree]", True))

        for i, (label, _) in enumerate(options, 1):
            tty.write(f"  {i}. {label}\n")
        tty.write("  0. Cancel\n")
        tty.write("\nSelect: ")
        tty.flush()
        line = tty.readline().strip()

        try:
            idx = int(line)
        except ValueError:
            return None

        if idx == 0 or not 1 <= idx <= len(options):
            return None

        label, is_new = options[idx - 1]

        if not is_new:
            return label, False

        tty.write("New branch name: ")
        tty.flush()
        new_branch = tty.readline().strip()

    if not new_branch:
        return None

    return new_branch, True


@cli.command()
@click.argument("branch", required=False, default=None, shell_complete=complete_worktree_branches)
def activate(branch: str | None) -> None:
    """Output a shell activation script for the BRANCH worktree.

    With a branch name, outputs the activation script directly:

    \\b
        source <(cwm activate <branch>)

    Without a branch name, shows an interactive menu to pick an existing
    worktree or create a new one:

    \\b
        source <(cwm activate)

    The script sets CWM_ACTIVE, CWM_PROJECT_ROOT, CWM_WORKTREE, CWM_WORKSPACE,
    sources the ROS 2 underlay and workspace overlays, and defines a
    'deactivate' shell function to undo all changes.
    """
    if sys.stdout.isatty():
        raise click.ClickException(_TTY_HINT.rstrip())

    try:
        root = find_project_root()
        config = Config.load(root)

        is_new = False
        if branch is None:
            result = _interactive_select(config)
            if result is None:
                # User cancelled — output a no-op script so source <(...) succeeds silently.
                click.echo("# cwm activate: cancelled")
                return
            branch, is_new = result
        else:
            ws_path = config.worktree_ws_path(branch)
            if not ws_path.exists():
                raise CWMError(
                    f"Worktree workspace not found: {ws_path}\n"
                    f"Create it first with: cwm worktree add {branch}"
                )

        ws_path = config.worktree_ws_path(branch)

        if is_new:
            script = generate_create_and_activate_script(
                branch=branch,
                project_root=str(root),
                workspace=str(ws_path),
                underlay=config.underlay,
                base_install=str(config.base_install_path),
                overlay_install=str(config.worktree_install_path(branch)),
            )
        else:
            script = generate_activate_script(
                branch=branch,
                project_root=str(root),
                workspace=str(ws_path),
                underlay=config.underlay,
                base_install=str(config.base_install_path),
                overlay_install=str(config.worktree_install_path(branch)),
            )

        click.echo(script, nl=False)

    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
