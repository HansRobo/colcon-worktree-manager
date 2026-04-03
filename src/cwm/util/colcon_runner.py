"""Colcon subprocess invocation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cwm.errors import ColconError


def _run_colcon(
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
    return _run_colcon("build", workspace, extra_args, env=env)


def run_colcon_test(
    workspace: Path,
    extra_args: list[str] | None = None,
    *,
    env: dict[str, str] | None = None,
) -> int:
    """Execute ``colcon test`` in *workspace* and stream output."""
    return _run_colcon("test", workspace, extra_args, env=env)
