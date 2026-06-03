"""Dependency Graph Analyzer - build DAG from package.xml and compute reverse deps."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from pathlib import Path

from catkin_pkg.package import parse_package

# Directories that never contain workspace source packages.
SKIP_DIRS = {"build", "install", "log", ".git"}


def iter_package_xmls(src_path: Path) -> Iterator[tuple[Path, Path]]:
    """Yield ``(package.xml path, path relative to src_path)`` for every
    workspace package under *src_path*, in deterministic order.

    Single source of truth for the workspace walk, shared by graph
    construction and :func:`cwm.core.dag_cache.compute_fingerprint` so both
    visit exactly the same set of files.
    """
    for pkg_xml in sorted(src_path.rglob("package.xml")):
        rel = pkg_xml.relative_to(src_path)
        if SKIP_DIRS.intersection(rel.parts):
            continue
        yield pkg_xml, rel


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

    def scan(self, src_path: Path, *, cache_dir: Path | None = None) -> None:
        """Discover packages under *src_path* and build the dependency graph.

        When *cache_dir* is given, a serialised graph is loaded from it if the
        ``package.xml`` fingerprint matches (skipping the expensive XML parse);
        otherwise the graph is rebuilt and stored for next time. With
        *cache_dir* ``None`` the graph is always rebuilt from disk.
        """
        if cache_dir is None:
            self._rebuild_from_src(src_path)
            return

        # Local import to break the dependency_graph <-> dag_cache import cycle.
        from cwm.core import dag_cache

        fingerprint = dag_cache.compute_fingerprint(src_path)
        cached = dag_cache.load_cached_graph(cache_dir, src_path, fingerprint)
        if cached is not None:
            self._pkg_paths = cached._pkg_paths
            self._forward = cached._forward
            self._reverse = cached._reverse
            return

        self._rebuild_from_src(src_path)
        dag_cache.store_cached_graph(cache_dir, fingerprint, self, src_path)

    def _rebuild_from_src(self, src_path: Path) -> None:
        """Walk *src_path* to discover packages and build the dependency graph.

        Each directory containing a ``package.xml`` is treated as a ROS
        package. Edges are built from ``build_depends`` and
        ``build_export_depends`` only -- the ABI-relevant dependencies that
        require a consumer rebuild when a dependency changes. ``exec_depends``
        are runtime-only and intentionally excluded: a runtime dependency
        changing does not affect a consumer's ABI. (The ``<depend>`` tag is
        expanded by catkin_pkg into all three lists, so packages declared with
        ``<depend>`` stay tracked via ``build_depends``.)
        """
        self._pkg_paths.clear()
        self._forward.clear()
        self._reverse.clear()

        # Single-pass: discover all packages and collect raw dependency names
        parsed: list[tuple[str, list[str]]] = []
        for pkg_xml, _rel in iter_package_xmls(src_path):
            pkg = parse_package(pkg_xml)
            self._pkg_paths[pkg.name] = pkg_xml.parent
            self._forward[pkg.name] = set()
            self._reverse.setdefault(pkg.name, set())
            raw_deps = [
                d.name for d in pkg.build_depends + pkg.build_export_depends
            ]
            parsed.append((pkg.name, raw_deps))

        # Populate forward and reverse edges (workspace-internal only)
        workspace_names = set(self._pkg_paths)
        for pkg_name, raw_deps in parsed:
            deps = {d for d in raw_deps if d in workspace_names}
            self._forward[pkg_name] = deps
            for dep_name in deps:
                self._reverse[dep_name].add(pkg_name)

    # -- Serialisation ---------------------------------------------------------

    def to_dict(self, src_path: Path) -> dict:
        """Serialise the graph to a plain dict keyed by package name.

        Package directories are stored relative to *src_path* so the cache can
        be shared across worktrees that hold the same packages at different
        absolute locations. The reverse edges are derived from the forward
        edges on load and therefore not stored.
        """
        return {
            "packages": {
                name: {
                    "path": self._pkg_paths[name].relative_to(src_path).as_posix(),
                    "forward": sorted(self._forward.get(name, ())),
                }
                for name in sorted(self._pkg_paths)
            }
        }

    @classmethod
    def from_dict(cls, data: dict, src_path: Path) -> DependencyGraphAnalyzer:
        """Reconstruct a graph from :meth:`to_dict` output rooted at *src_path*."""
        graph = cls()
        packages = data["packages"]
        for name, entry in packages.items():
            graph._pkg_paths[name] = src_path / entry["path"]
            graph._forward[name] = set(entry["forward"])
            graph._reverse.setdefault(name, set())
        # Rebuild reverse edges from forward edges.
        for name, deps in graph._forward.items():
            for dep in deps:
                graph._reverse.setdefault(dep, set()).add(name)
        return graph

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

    def get_reverse_deps(self, packages: set[str], *, max_depth: int | None = None) -> set[str]:
        """Return packages that transitively depend on *packages*.

        This is the "affected set" - all packages that need to be rebuilt
        when any package in *packages* changes, to maintain ABI safety.
        Only build/build_export dependents are tracked (see :meth:`scan`), so
        runtime-only (``exec_depends``) consumers are NOT included here.
        Does NOT include *packages* themselves.

        With *max_depth* set, the breadth-first walk is bounded to that many
        levels of reverse edges (``max_depth=1`` returns only direct consumers).
        ``max_depth=None`` walks the full transitive closure (default).
        """
        visited: set[str] = set()
        # Level-by-level BFS so depth can be bounded; frontier holds one level.
        frontier: set[str] = set(packages)
        depth = 0
        while frontier and (max_depth is None or depth < max_depth):
            next_frontier: set[str] = set()
            for pkg in frontier:
                for rdep in self._reverse.get(pkg, ()):
                    if rdep not in visited and rdep not in packages:
                        visited.add(rdep)
                        next_frontier.add(rdep)
            frontier = next_frontier
            depth += 1
        return visited

    def forward_edges(self) -> dict[str, set[str]]:
        """Return a copy of the forward adjacency (package -> direct deps).

        Public accessor for read-only consumers (e.g. ``cwm inspect graph``)
        so the internal ``_forward`` map is not exposed or mutated.
        """
        return {name: set(deps) for name, deps in self._forward.items()}

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
