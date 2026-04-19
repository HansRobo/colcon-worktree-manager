"""Utilities for discovering repositories in a colcon workspace."""

from __future__ import annotations

from pathlib import Path

from cwm.errors import RepoNotFoundError
from cwm.util.git import is_git_repo


def discover_sub_repos(src_path: Path) -> dict[str, Path]:
    """Recursively discover git repositories under *src_path*.

    Returns a mapping from relative path (relative to *src_path*) to absolute
    path for each repository found.  Only immediate git repository roots are
    returned; nested repositories inside a repo are not traversed.
    """
    result: dict[str, Path] = {}
    _scan(src_path, src_path, result)
    return dict(sorted(result.items()))


def _scan(root: Path, current: Path, result: dict[str, Path]) -> None:
    if not current.is_dir():
        return
    for child in sorted(current.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if is_git_repo(child):
            rel = str(child.relative_to(root))
            result[rel] = child
        else:
            _scan(root, child, result)


def validate_repo_path(src_path: Path, rel: str) -> Path:
    """Validate that *rel* points to a git repository under *src_path*.

    Returns the absolute path on success.
    Raises :class:`~cwm.errors.RepoNotFoundError` if the path is invalid.
    """
    candidate = src_path / rel
    if not candidate.is_dir() or not is_git_repo(candidate):
        raise RepoNotFoundError(
            f"Repository not found or not a git repo: {candidate}\n"
            "Run 'vcs import src < your.repos' to populate the workspace."
        )
    return candidate
