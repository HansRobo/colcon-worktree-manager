"""Colcon subprocess invocation."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from cwm.errors import ColconError


def run_colcon(
    subcommand: str,
    workspace: Path,
    extra_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Execute a colcon subcommand in *workspace* and stream output.

    Returns the process exit code. Raises ColconError on non-zero exit.
    """
    cmd = ["colcon", subcommand]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        cwd=workspace,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        raise ColconError(
            f"colcon {subcommand} failed with exit code {result.returncode}"
        )
    return result.returncode


def run_colcon_build(
    workspace: Path,
    extra_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Execute ``colcon build`` in *workspace* and stream output to stdout."""
    return run_colcon("build", workspace, extra_args, env=env)


def run_colcon_build_sourced(
    workspace: Path,
    underlay_install: Path,
    overlay_install: Path | None,
    extra_args: list[str] | None = None,
) -> int:
    """Execute ``colcon build`` in *workspace* after sourcing the ROS 2 environment.

    Sources *underlay_install*/setup.bash (and *overlay_install*/local_setup.bash
    if it exists) inside a bash subshell so the calling process environment is
    not modified.

    Raises ColconError on non-zero exit.
    """
    source_cmds = [f"source {shlex.quote(str(underlay_install / 'setup.bash'))}"]
    local_setup = overlay_install / "local_setup.bash" if overlay_install else None
    if local_setup and local_setup.exists():
        source_cmds.append(f"source {shlex.quote(str(local_setup))}")

    colcon_cmd = ["colcon", "build"]
    if extra_args:
        colcon_cmd.extend(extra_args)

    # Build a shell command that sources the environment then runs colcon
    shell_script = " && ".join(source_cmds) + " && " + " ".join(colcon_cmd)

    result = subprocess.run(
        ["bash", "-c", shell_script],
        cwd=workspace,
        env=os.environ.copy(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if result.returncode != 0:
        raise ColconError(f"colcon build failed with exit code {result.returncode}")
    return result.returncode


def run_colcon_test(
    workspace: Path,
    extra_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Execute ``colcon test`` in *workspace* and stream output."""
    return run_colcon("test", workspace, extra_args, env=env)
