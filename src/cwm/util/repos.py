"""Utilities for discovering sub-repositories in a meta-repository workspace."""

from __future__ import annotations

from pathlib import Path

from cwm.errors import SubRepoNotFoundError
from cwm.util.git import is_git_repo


def discover_sub_repos(src_path: Path) -> dict[str, Path]:
    """Recursively discover git repositories under *src_path*.

    Returns a mapping from relative path (relative to *src_path*) to absolute
    path for each sub-repository found.  Only immediate git repository roots
    are returned; nested repositories inside a sub-repo are not traversed.

    Example::

        {
            "core/autoware_core": Path(".../base_ws/src/core/autoware_core"),
            "universe/autoware_universe": Path(".../base_ws/src/universe/autoware_universe"),
        }
    """
    result: dict[str, Path] = {}
    _scan(src_path, src_path, result)
    return dict(sorted(result.items()))


def _scan(root: Path, current: Path, result: dict[str, Path]) -> None:
    """Recursively scan *current* for git repos, recording relative paths."""
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
            # Do not recurse into a git repository
        else:
            _scan(root, child, result)


def validate_sub_repo_paths(src_path: Path, paths: list[str]) -> None:
    """Validate that each path in *paths* points to a git repository under *src_path*.

    Raises :class:`~cwm.errors.SubRepoNotFoundError` for the first invalid path.
    """
    for rel in paths:
        candidate = src_path / rel
        if not candidate.is_dir() or not is_git_repo(candidate):
            raise SubRepoNotFoundError(
                f"Sub-repository not found or not a git repo: {candidate}\n"
                "Run 'vcs import src < your.repos' to populate the workspace."
            )
