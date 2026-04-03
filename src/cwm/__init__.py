"""Colcon Worktree Manager - parallel ROS 2 development with git worktrees."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("colcon-worktree-manager")
except PackageNotFoundError:
    __version__ = "unknown"
