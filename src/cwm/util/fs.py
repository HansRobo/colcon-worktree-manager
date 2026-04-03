"""Filesystem utility functions for CWM."""

from __future__ import annotations

from pathlib import Path

from cwm.errors import ConfigNotFoundError


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find the directory containing .cwm/.

    Raises ConfigNotFoundError if no .cwm/ directory is found before reaching /.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / ".cwm").is_dir():
            return current
        parent = current.parent
        if parent == current:
            raise ConfigNotFoundError(
                "No .cwm/ directory found. Run 'cwm init' first."
            )
        current = parent


def ensure_dir(path: Path) -> Path:
    """Create *path* and all parents if they don't exist. Returns *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path
