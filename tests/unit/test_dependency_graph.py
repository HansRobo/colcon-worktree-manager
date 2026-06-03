"""Unit tests for the Dependency Graph Analyzer."""

from __future__ import annotations

from pathlib import Path

from cwm.core.dependency_graph import DependencyGraphAnalyzer


class TestDGAScan:
    def test_discovers_all_packages(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        assert graph.packages == {
            "core_lib",
            "msgs",
            "perception_node",
            "control_node",
            "standalone",
        }

    def test_package_paths(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        assert graph.package_path("core_lib") == sample_ws / "src" / "core_lib"


class TestReverseDepsBFS:
    def test_single_core_change(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        rdeps = graph.get_reverse_deps({"core_lib"})
        assert rdeps == {"perception_node", "control_node"}

    def test_msgs_change(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        rdeps = graph.get_reverse_deps({"msgs"})
        assert rdeps == {"perception_node", "control_node"}

    def test_leaf_change_no_rdeps(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        rdeps = graph.get_reverse_deps({"perception_node"})
        assert rdeps == set()

    def test_standalone_change_no_rdeps(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        rdeps = graph.get_reverse_deps({"standalone"})
        assert rdeps == set()

    def test_multiple_changes(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        rdeps = graph.get_reverse_deps({"core_lib", "msgs"})
        assert rdeps == {"perception_node", "control_node"}


class TestTopologicalSort:
    def test_full_rebuild_order(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        order = graph.topological_sort(graph.packages)
        # core_lib and msgs must come before perception_node and control_node
        assert order.index("core_lib") < order.index("perception_node")
        assert order.index("core_lib") < order.index("control_node")
        assert order.index("msgs") < order.index("perception_node")
        assert order.index("msgs") < order.index("control_node")

    def test_subset_order(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        order = graph.topological_sort({"core_lib", "perception_node"})
        assert order == ["core_lib", "perception_node"]


class TestForwardDeps:
    def test_perception_node_deps(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        deps = graph.get_forward_deps({"perception_node"})
        assert deps == {"core_lib", "msgs"}

    def test_core_lib_no_forward_deps(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        deps = graph.get_forward_deps({"core_lib"})
        assert deps == set()


class TestExecDependExclusion:
    """exec-only dependencies are excluded from the ABI rebuild graph."""

    def test_abi_consumers_are_affected(self, mixed_deps_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(mixed_deps_ws / "src")
        # build_depend, <depend>, and build_export_depend all form ABI edges
        rdeps = graph.get_reverse_deps({"lib_abi"})
        assert rdeps == {"abi_consumer", "shared_consumer", "export_consumer"}

    def test_exec_only_consumer_not_affected(self, mixed_deps_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(mixed_deps_ws / "src")
        # exec_consumer depends on lib_runtime via <exec_depend> only -> dropped
        assert graph.get_reverse_deps({"lib_runtime"}) == set()

    def test_depend_tag_kept_as_abi_edge(self, mixed_deps_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(mixed_deps_ws / "src")
        # <depend> also expands to exec_depends but must survive via build_depends
        assert graph.get_forward_deps({"shared_consumer"}) == {"lib_abi"}

    def test_exec_only_has_no_forward_edge(self, mixed_deps_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(mixed_deps_ws / "src")
        assert graph.get_forward_deps({"exec_consumer"}) == set()
