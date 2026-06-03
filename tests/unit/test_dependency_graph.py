"""Unit tests for the Dependency Graph Analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwm.core.dependency_graph as dg_module
from cwm.core.dag_cache import compute_fingerprint
from cwm.core.dependency_graph import DependencyGraphAnalyzer
from tests.conftest import write_package


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


class TestReverseDepsDepth:
    def test_depth_one_returns_direct_consumers(self, chain_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(chain_ws / "src")
        assert graph.get_reverse_deps({"lib0"}, max_depth=1) == {"lib1"}

    def test_depth_two_returns_two_levels(self, chain_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(chain_ws / "src")
        assert graph.get_reverse_deps({"lib0"}, max_depth=2) == {"lib1", "lib2"}

    def test_depth_none_returns_full_closure(self, chain_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(chain_ws / "src")
        assert graph.get_reverse_deps({"lib0"}, max_depth=None) == {"lib1", "lib2", "lib3"}

    def test_depth_default_matches_full_closure(self, chain_ws: Path) -> None:
        """The default (no max_depth) is unchanged from the full transitive walk."""
        graph = DependencyGraphAnalyzer()
        graph.scan(chain_ws / "src")
        assert graph.get_reverse_deps({"lib0"}) == graph.get_reverse_deps({"lib0"}, max_depth=None)

    def test_depth_beyond_chain_is_full_closure(self, chain_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(chain_ws / "src")
        assert graph.get_reverse_deps({"lib0"}, max_depth=99) == {"lib1", "lib2", "lib3"}


class TestForwardEdges:
    def test_returns_direct_dependencies(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        edges = graph.forward_edges()
        assert edges["perception_node"] == {"core_lib", "msgs"}
        assert edges["core_lib"] == set()

    def test_is_a_copy(self, sample_ws: Path) -> None:
        """Mutating the returned map must not corrupt the internal graph."""
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")
        edges = graph.forward_edges()
        edges["perception_node"].add("bogus")
        assert graph.forward_edges()["perception_node"] == {"core_lib", "msgs"}


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


def _fail_if_parsed(*_args: object, **_kwargs: object) -> None:
    pytest.fail("parse_package called on a cache hit")


class TestDGACache:
    def test_scan_without_cache_dir_unchanged(self, sample_ws: Path) -> None:
        graph = DependencyGraphAnalyzer()
        graph.scan(sample_ws / "src")  # cache_dir omitted -> legacy behaviour
        assert graph.get_reverse_deps({"core_lib"}) == {
            "perception_node",
            "control_node",
        }

    def test_scan_hit_skips_parse_package(
        self, sample_ws: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        first = DependencyGraphAnalyzer()
        first.scan(src, cache_dir=cache)  # cold: parses + stores

        # A second scan of the unchanged tree must not parse any package.xml.
        monkeypatch.setattr(dg_module, "parse_package", _fail_if_parsed)
        second = DependencyGraphAnalyzer()
        second.scan(src, cache_dir=cache)
        assert second.packages == first.packages
        assert second.get_reverse_deps({"core_lib"}) == first.get_reverse_deps({"core_lib"})
        assert second.package_path("core_lib") == src / "core_lib"

    def test_scan_rebuilds_after_edit(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        DependencyGraphAnalyzer().scan(src, cache_dir=cache)

        write_package(src, "standalone", deps=["core_lib"])
        graph = DependencyGraphAnalyzer()
        graph.scan(src, cache_dir=cache)
        # The new edge is reflected, so the cache was invalidated and rebuilt.
        assert graph.get_forward_deps({"standalone"}) == {"core_lib"}

    def test_scan_rebuilds_after_add_remove(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        DependencyGraphAnalyzer().scan(src, cache_dir=cache)

        (src / "standalone" / "package.xml").unlink()
        graph = DependencyGraphAnalyzer()
        graph.scan(src, cache_dir=cache)
        assert "standalone" not in graph.packages

    def test_scan_rebuilds_on_format_version_mismatch(
        self, sample_ws: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        DependencyGraphAnalyzer().scan(src, cache_dir=cache)

        fp = compute_fingerprint(src)
        path = cache / f"{fp}.json"
        data = json.loads(path.read_text())
        data["cache_format_version"] = 999
        path.write_text(json.dumps(data))

        # A bumped format version is a miss -> parse_package must run again.
        calls: list[Path] = []
        real_parse = dg_module.parse_package
        monkeypatch.setattr(
            dg_module,
            "parse_package",
            lambda p, *a, **k: calls.append(p) or real_parse(p, *a, **k),
        )
        DependencyGraphAnalyzer().scan(src, cache_dir=cache)
        assert calls  # rebuilt from source

    def test_scan_falls_back_on_corrupt_cache(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        DependencyGraphAnalyzer().scan(src, cache_dir=cache)

        fp = compute_fingerprint(src)
        (cache / f"{fp}.json").write_text("{garbage")

        graph = DependencyGraphAnalyzer()
        graph.scan(src, cache_dir=cache)  # must not raise
        assert graph.get_reverse_deps({"core_lib"}) == {
            "perception_node",
            "control_node",
        }

    def test_cache_shared_across_identical_src(
        self, sample_ws: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src_a = sample_ws / "src"
        cache = tmp_path / "cache"
        DependencyGraphAnalyzer().scan(src_a, cache_dir=cache)

        # A second worktree with the same packages at a different absolute root
        # shares the cache entry (same fingerprint), without re-parsing.
        src_b = tmp_path / "wt_b" / "src"
        src_b.mkdir(parents=True)
        for pkg_dir in sorted(src_a.iterdir()):
            dest = src_b / pkg_dir.name
            dest.mkdir()
            (dest / "package.xml").write_text((pkg_dir / "package.xml").read_text())

        assert compute_fingerprint(src_a) == compute_fingerprint(src_b)
        monkeypatch.setattr(dg_module, "parse_package", _fail_if_parsed)
        graph = DependencyGraphAnalyzer()
        graph.scan(src_b, cache_dir=cache)
        # Paths are restored against src_b, not the worktree the cache came from.
        assert graph.package_path("core_lib") == src_b / "core_lib"
