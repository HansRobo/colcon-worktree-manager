"""Changeset computation - diff-based package selection for colcon.

Extracts the change-detection pipeline (scan -> changed -> reverse deps ->
topological sort) shared by ``ws build`` and, in later releases, ``ws test``
and ``inspect changed``.  Kept free of any CLI/click dependency so it can be
reused across commands; callers own the user-facing output.
"""

from __future__ import annotations

from dataclasses import dataclass

from cwm.core.colcon_discovery import ColconDiscoveryController
from cwm.core.config import Config
from cwm.core.dependency_graph import DependencyGraphAnalyzer
from cwm.core.worktree_state import WorktreeMeta


@dataclass
class Changeset:
    """Result of analysing which packages changed and must be rebuilt."""

    package_count: int
    changed: set[str]
    affected: set[str]
    build_order: list[str]


def compute_changeset(config: Config, branch: str, *, no_rdeps: bool = False) -> Changeset:
    """Detect changed packages in *branch*'s worktree and their rebuild order.

    Scans the worktree ``src/`` for ROS packages, diffs the tracked repo against
    the SHA recorded at worktree creation, maps changed files to packages, and
    (unless *no_rdeps*) adds reverse dependencies for ABI safety.  The combined
    set is returned in topological build order.
    """
    src_path = config.worktree_src_path(branch)

    graph = DependencyGraphAnalyzer()
    graph.scan(src_path, cache_dir=config.dag_cache_dir)

    discovery = ColconDiscoveryController(src_path)
    meta = WorktreeMeta.load(config.worktree_meta_path(branch))
    changed_files = discovery.get_changed_files_meta(
        [meta.repo_name], {meta.repo_name: meta.base_sha}
    )
    changed = discovery.get_changed_packages(graph, changed_files)

    affected: set[str] = set() if no_rdeps else graph.get_reverse_deps(changed)
    build_order = graph.topological_sort(changed | affected)

    return Changeset(
        package_count=len(graph.packages),
        changed=changed,
        affected=affected,
        build_order=build_order,
    )
