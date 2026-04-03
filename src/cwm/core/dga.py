"""Dependency Graph Analyzer - build DAG from package.xml and compute reverse deps."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from catkin_pkg.package import parse_package


class DependencyGraphAnalyzer:
    """Builds and queries a package dependency DAG for a ROS 2 workspace.

    The graph is constructed by scanning all ``package.xml`` files under a
    source directory. Only workspace-internal dependencies are tracked
    (system/external packages are ignored).
    """

    def __init__(self) -> None:
        # package name -> directory containing package.xml
        self._pkg_paths: dict[str, Path] = {}
        # forward edges: package -> set of packages it depends on
        self._forward: dict[str, set[str]] = {}
        # reverse edges: package -> set of packages that depend on it
        self._reverse: dict[str, set[str]] = {}

    @property
    def packages(self) -> set[str]:
        """All known package names in the graph."""
        return set(self._pkg_paths)

    def package_path(self, name: str) -> Path:
        """Return the source directory for *name*."""
        return self._pkg_paths[name]

    # -- Graph construction ----------------------------------------------------

    def scan(self, src_path: Path) -> None:
        """Walk *src_path* to discover packages and build the dependency graph.

        Each directory containing a ``package.xml`` is treated as a ROS
        package. Dependencies are extracted from ``build_depends``,
        ``exec_depends``, and ``build_export_depends`` fields (the
        ``<depend>`` tag is automatically expanded by catkin_pkg).
        """
        self._pkg_paths.clear()
        self._forward.clear()
        self._reverse.clear()

        _SKIP_DIRS = {"build", "install", "log", ".git"}

        # Single-pass: discover all packages and collect raw dependency names
        parsed: list[tuple[str, list[str]]] = []
        for pkg_xml in sorted(src_path.rglob("package.xml")):
            rel = pkg_xml.relative_to(src_path)
            if _SKIP_DIRS.intersection(rel.parts):
                continue
            pkg = parse_package(pkg_xml)
            self._pkg_paths[pkg.name] = pkg_xml.parent
            self._forward[pkg.name] = set()
            self._reverse.setdefault(pkg.name, set())
            raw_deps = [
                d.name
                for d in pkg.build_depends + pkg.exec_depends + pkg.build_export_depends
            ]
            parsed.append((pkg.name, raw_deps))

        # Populate forward and reverse edges (workspace-internal only)
        workspace_names = set(self._pkg_paths)
        for pkg_name, raw_deps in parsed:
            deps = {d for d in raw_deps if d in workspace_names}
            self._forward[pkg_name] = deps
            for dep_name in deps:
                self._reverse[dep_name].add(pkg_name)

    # -- Queries ---------------------------------------------------------------

    def get_forward_deps(self, packages: set[str]) -> set[str]:
        """Return all transitive dependencies of *packages* (not including themselves)."""
        visited: set[str] = set()
        queue: deque[str] = deque(packages)
        while queue:
            pkg = queue.popleft()
            for dep in self._forward.get(pkg, ()):
                if dep not in visited and dep not in packages:
                    visited.add(dep)
                    queue.append(dep)
        return visited

    def get_reverse_deps(self, packages: set[str]) -> set[str]:
        """Return all packages that transitively depend on *packages*.

        This is the "affected set" - all packages that need to be rebuilt
        when any package in *packages* changes, to maintain ABI safety.
        Does NOT include *packages* themselves.
        """
        visited: set[str] = set()
        queue: deque[str] = deque(packages)
        while queue:
            pkg = queue.popleft()
            for rdep in self._reverse.get(pkg, ()):
                if rdep not in visited and rdep not in packages:
                    visited.add(rdep)
                    queue.append(rdep)
        return visited

    def topological_sort(self, packages: set[str]) -> list[str]:
        """Return a topological ordering of *packages* (dependencies first).

        Only considers edges within the *packages* subset.
        """
        # Build sub-graph in-degree map
        in_degree: dict[str, int] = {p: 0 for p in packages}
        sub_edges: dict[str, list[str]] = {p: [] for p in packages}
        for pkg in packages:
            for dep in self._forward.get(pkg, ()):
                if dep in packages:
                    in_degree[pkg] += 1
                    sub_edges[dep].append(pkg)

        # Kahn's algorithm
        queue: deque[str] = deque(p for p, d in in_degree.items() if d == 0)
        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            for successor in sub_edges[node]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if len(result) != len(packages):
            # Cycle detected - return what we have (shouldn't happen in valid ROS pkgs)
            remaining = packages - set(result)
            result.extend(sorted(remaining))
        return result
