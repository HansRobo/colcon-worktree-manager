"""Unit tests for the Dependency Graph Analyzer."""

from __future__ import annotations

from pathlib import Path

from cwm.core.dga import DependencyGraphAnalyzer


class TestDGAScan:
    def test_discovers_all_packages(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        assert dga.packages == {
            "core_lib",
            "msgs",
            "perception_node",
            "control_node",
            "standalone",
        }

    def test_package_paths(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        assert dga.package_path("core_lib") == sample_ws / "src" / "core_lib"


class TestReverseDepsBFS:
    def test_single_core_change(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        rdeps = dga.get_reverse_deps({"core_lib"})
        assert rdeps == {"perception_node", "control_node"}

    def test_msgs_change(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        rdeps = dga.get_reverse_deps({"msgs"})
        assert rdeps == {"perception_node", "control_node"}

    def test_leaf_change_no_rdeps(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        rdeps = dga.get_reverse_deps({"perception_node"})
        assert rdeps == set()

    def test_standalone_change_no_rdeps(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        rdeps = dga.get_reverse_deps({"standalone"})
        assert rdeps == set()

    def test_multiple_changes(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        rdeps = dga.get_reverse_deps({"core_lib", "msgs"})
        assert rdeps == {"perception_node", "control_node"}


class TestTopologicalSort:
    def test_full_rebuild_order(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        order = dga.topological_sort(dga.packages)
        # core_lib and msgs must come before perception_node and control_node
        assert order.index("core_lib") < order.index("perception_node")
        assert order.index("core_lib") < order.index("control_node")
        assert order.index("msgs") < order.index("perception_node")
        assert order.index("msgs") < order.index("control_node")

    def test_subset_order(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        order = dga.topological_sort({"core_lib", "perception_node"})
        assert order == ["core_lib", "perception_node"]


class TestForwardDeps:
    def test_perception_node_deps(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        deps = dga.get_forward_deps({"perception_node"})
        assert deps == {"core_lib", "msgs"}

    def test_core_lib_no_forward_deps(self, sample_ws: Path) -> None:
        dga = DependencyGraphAnalyzer()
        dga.scan(sample_ws / "src")
        deps = dga.get_forward_deps({"core_lib"})
        assert deps == set()
