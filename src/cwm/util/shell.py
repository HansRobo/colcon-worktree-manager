"""Subshell generation for environment variable sandboxing."""

from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path


def _bash_completion_script() -> str:
    """Return the cwm bash completion script using Click's API directly.

    Calling Click's BashComplete.source() avoids subprocess/PATH issues that arise
    when the development version of cwm differs from the system-installed binary.
    Embedding the script statically in the rcfile also avoids timing issues with
    bash-completion resetting completions registered via eval at shell startup.
    Returns an empty string if generation fails so the rcfile is still usable.
    """
    try:
        from click.shell_completion import BashComplete
        from cwm.cli.main import cli
        return BashComplete(cli, {}, "cwm", "_CWM_COMPLETE").source()
    except Exception:
        return ""


def create_rcfile(
    branch: str,
    worktree_ws: Path,
    underlay_install: Path,
    overlay_install: Path,
) -> Path:
    """Generate a temporary bash rcfile that sets up the CWM subshell environment.

    The rcfile:
    1. Sources the user's ~/.bashrc (to preserve aliases, prompt, etc.)
    2. Sources the underlay's setup.bash to establish the base environment
    3. Exports CWM-specific environment variables
    4. Sets a modified PS1 prompt to indicate the active worktree
    5. Embeds the cwm bash completion script directly (no eval at shell startup)
    6. Registers a trap to delete itself on shell exit

    Returns the path to the generated rcfile.
    """
    # Write to a temp file first so we can embed its path in the trap
    fd, rc_path = tempfile.mkstemp(prefix="cwm_rc_", suffix=".bash")

    # Escape all values to prevent shell injection
    q_branch = shlex.quote(branch)
    q_ws = shlex.quote(str(worktree_ws))
    q_underlay = shlex.quote(str(underlay_install))
    q_overlay = shlex.quote(str(overlay_install))
    q_rcpath = shlex.quote(rc_path)

    completion_script = _bash_completion_script()

    rc_content = f"""\
# CWM subshell rcfile - auto-generated, do not edit.
# Self-cleanup on exit
trap 'rm -f {q_rcpath}' EXIT

# Source user's bashrc for aliases, completions, etc.
if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc"
fi

# Source the underlay environment
if [ -f {q_underlay}/setup.bash ]; then
    source {q_underlay}/setup.bash
fi

# Source the overlay environment (if it exists from a previous build)
if [ -f {q_overlay}/local_setup.bash ]; then
    source {q_overlay}/local_setup.bash
fi

# CWM environment markers
export CWM_ACTIVE=1
export CWM_WORKTREE={q_branch}
export CWM_WORKSPACE={q_ws}

# Set working directory to the worktree workspace
cd {q_ws}

# Modified prompt to show the active worktree
if [ -n "$PS1" ]; then
    export PS1="[cwm:{q_branch}] $PS1"
fi

# cwm shell completion - embedded at 'cwm enter' time so it is always active
# regardless of bash-completion initialization order.
{completion_script}

echo ""
echo "=== CWM Worktree: {q_branch} ==="
echo "  Workspace: {q_ws}"
echo "  Underlay:  {q_underlay}"
echo "  Run 'cwm build' to build changed packages."
echo "  Run 'exit' or Ctrl+D to leave."
echo ""
"""

    with os.fdopen(fd, "w") as fh:
        fh.write(rc_content)
    return Path(rc_path)


def exec_subshell(rcfile: Path) -> None:
    """Replace the current process with a bash subshell using *rcfile*.

    This function never returns - it replaces the process via execvp.
    """
    os.execvp("bash", ["bash", "--rcfile", str(rcfile)])
