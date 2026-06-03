"""Filesystem utility functions for CWM."""

from __future__ import annotations

import os
from pathlib import Path

from cwm.errors import ConfigNotFoundError


def find_project_root(start: Path | None = None) -> Path:
    """Return the CWM project root (directory containing .cwm/).

    Resolution order:
    1. If CWM_PROJECT_ROOT is set and points to a valid .cwm/ directory, return it.
       This lets activated workspaces work from any cwd, like Python virtual environments.
    2. Walk up from *start* (default: cwd) looking for .cwm/.
    3. Raise ConfigNotFoundError.
    """
    env_root = os.environ.get("CWM_PROJECT_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if (p / ".cwm").is_dir():
            return p

    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".cwm").is_dir():
            return current
        parent = current.parent
        if parent == current:
            raise ConfigNotFoundError(
                "No .cwm/ directory found. "
                "Run 'cwm init' to create a project, "
                "or 'source <(cwm activate <branch>)' to activate a workspace."
            )
        current = parent


def ensure_dir(path: Path) -> Path:
    """Create *path* and all parents if they don't exist. Returns *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path
