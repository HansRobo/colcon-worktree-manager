"""Thin wrappers around git subprocess calls."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from cwm.errors import GitError


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the CompletedProcess result."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )
    except subprocess.CalledProcessError as exc:
        raise GitError(
            f"git {' '.join(args)} failed (rc={exc.returncode}): {exc.stderr.strip()}"
        ) from exc


# -- Repository queries -------------------------------------------------------


def is_git_repo(path: Path) -> bool:
    """Return True if *path* is the root of a git repository."""
    return (path / ".git").exists()


def get_toplevel(cwd: Path | None = None) -> Path:
    """Return the absolute path of the repository root."""
    result = _run(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(result.stdout.strip())


def get_current_branch(cwd: Path | None = None) -> str:
    """Return the name of the currently checked-out branch."""
    result = _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def get_merge_base(ref_a: str, ref_b: str, *, cwd: Path | None = None) -> str:
    """Return the merge-base commit hash between two refs."""
    result = _run(["merge-base", ref_a, ref_b], cwd=cwd)
    return result.stdout.strip()


def diff_name_only(
    base_ref: str,
    *,
    cwd: Path | None = None,
) -> list[str]:
    """Return the list of file paths changed between *base_ref* and HEAD."""
    result = _run(["diff", "--name-only", base_ref], cwd=cwd)
    return [line for line in result.stdout.splitlines() if line]


def get_head_sha(cwd: Path | None = None) -> str:
    """Return the full SHA of HEAD."""
    result = _run(["rev-parse", "HEAD"], cwd=cwd)
    return result.stdout.strip()


# -- Worktree management ------------------------------------------------------


@dataclass
class WorktreeInfo:
    """Parsed output of a single git worktree entry."""

    path: Path
    head: str
    branch: str | None  # None for detached HEAD


def branch_exists(branch: str, *, cwd: Path | None = None) -> bool:
    """Check whether a local branch exists."""
    result = _run(
        ["rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def pull(*, cwd: Path | None = None) -> None:
    """Run ``git pull`` in *cwd*."""
    _run(["pull"], cwd=cwd)


def worktree_add(
    path: Path,
    branch: str,
    *,
    create_branch: bool = True,
    cwd: Path | None = None,
) -> None:
    """Run ``git worktree add``.

    If *create_branch* is True and the branch does not exist yet, it will be
    created with ``-b``.
    """
    exists = branch_exists(branch, cwd=cwd)
    args = ["worktree", "add"]
    if create_branch and not exists:
        args += ["-b", branch, str(path)]
    else:
        args += [str(path), branch]
    _run(args, cwd=cwd)


def worktree_remove(path: Path, *, force: bool = False, cwd: Path | None = None) -> None:
    """Run ``git worktree remove``."""
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    _run(args, cwd=cwd)


def worktree_list(cwd: Path | None = None) -> list[WorktreeInfo]:
    """Parse ``git worktree list --porcelain`` and return structured data."""
    result = _run(["worktree", "list", "--porcelain"], cwd=cwd)

    def _make_entry(fields: dict[str, str]) -> WorktreeInfo | None:
        if "worktree" not in fields:
            return None
        branch_raw = fields.get("branch")
        return WorktreeInfo(
            path=Path(fields["worktree"]),
            head=fields.get("HEAD", ""),
            branch=branch_raw.removeprefix("refs/heads/") if branch_raw else None,
        )

    entries: list[WorktreeInfo] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line:
            entry = _make_entry(current)
            if entry:
                entries.append(entry)
            current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line.split(" ", 1)[1]
        elif line.startswith("HEAD "):
            current["HEAD"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]

    # Handle last entry (no trailing blank line)
    entry = _make_entry(current)
    if entry:
        entries.append(entry)
    return entries
