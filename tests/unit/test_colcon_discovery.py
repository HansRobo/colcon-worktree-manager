"""Unit tests for the Colcon Discovery Controller."""

from __future__ import annotations

from pathlib import Path

from cwm.core.colcon_discovery import ColconDiscoveryController
from cwm.core.dependency_graph import DependencyGraphAnalyzer


class TestGenerateBuildArgs:
    def test_single_changed_pkg(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        args = discovery.generate_build_args({"pkg_a"}, set())
        assert "--packages-select" in args
        assert "pkg_a" in args
        assert "--allow-overriding" in args
        assert "--symlink-install" in args

    def test_changed_and_affected(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        args = discovery.generate_build_args({"core_lib"}, {"perception_node", "control_node"})
        # All three should appear in both --packages-select and --allow-overriding
        select_idx = args.index("--packages-select")
        override_idx = args.index("--allow-overriding")
        # Packages between --packages-select and --allow-overriding
        selected = set(args[select_idx + 1 : override_idx])
        assert selected == {"control_node", "core_lib", "perception_node"}

    def test_no_symlink_install(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        args = discovery.generate_build_args({"pkg_a"}, set(), symlink_install=False)
        assert "--symlink-install" not in args

    def test_empty_returns_empty(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        args = discovery.generate_build_args(set(), set())
        assert args == []


class TestGenerateTestArgs:
    def test_packages_select_only(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        args = discovery.generate_test_args({"core_lib"}, {"perception_node"})
        assert args == ["--packages-select", "core_lib", "perception_node"]
        # test has no build-only flags
        assert "--allow-overriding" not in args
        assert "--symlink-install" not in args

    def test_empty_returns_empty(self) -> None:
        discovery = ColconDiscoveryController(Path("/fake"))
        assert discovery.generate_test_args(set(), set()) == []


class TestIgnoreMarkers:
    def test_place_and_remove_markers(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        discovery = ColconDiscoveryController(sample_ws / "src")

        keep = {"core_lib", "perception_node"}
        markers = discovery.place_ignore_markers(graph, keep)

        # Markers should be placed for packages NOT in keep
        marker_parents = {m.parent.name for m in markers}
        assert "core_lib" not in marker_parents
        assert "perception_node" not in marker_parents
        assert "msgs" in marker_parents
        assert "control_node" in marker_parents
        assert "standalone" in marker_parents

        # All markers exist
        for m in markers:
            assert m.exists()
            assert m.name == "COLCON_IGNORE"

        # Cleanup
        ColconDiscoveryController.remove_ignore_markers(markers)
        for m in markers:
            assert not m.exists()
