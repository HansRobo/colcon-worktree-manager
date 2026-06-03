"""Unit tests for the DAG cache (fingerprint + load/store)."""

from __future__ import annotations

import json
from pathlib import Path

from cwm.core.dag_cache import (
    CACHE_FORMAT_VERSION,
    compute_fingerprint,
    load_cached_graph,
    store_cached_graph,
)
from cwm.core.dependency_graph import DependencyGraphAnalyzer
from tests.conftest import write_package


class TestFingerprint:
    def test_stable(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        assert compute_fingerprint(src) == compute_fingerprint(src)

    def test_changes_on_edit(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        before = compute_fingerprint(src)
        write_package(src, "perception_node", deps=["core_lib", "msgs", "standalone"])
        assert compute_fingerprint(src) != before

    def test_changes_on_add(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        before = compute_fingerprint(src)
        write_package(src, "new_pkg")
        assert compute_fingerprint(src) != before

    def test_changes_on_remove(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        before = compute_fingerprint(src)
        (src / "standalone" / "package.xml").unlink()
        assert compute_fingerprint(src) != before

    def test_changes_on_rename(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        before = compute_fingerprint(src)
        (src / "standalone").rename(src / "renamed")
        assert compute_fingerprint(src) != before

    def test_ignores_skip_dirs(self, sample_ws: Path) -> None:
        src = sample_ws / "src"
        before = compute_fingerprint(src)
        # A package.xml under build/ must not affect the fingerprint.
        write_package(src / "build", "stale_pkg")
        assert compute_fingerprint(src) == before


class TestStoreLoad:
    def test_roundtrip(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        original = DependencyGraphAnalyzer()
        original.scan(src)
        fp = compute_fingerprint(src)

        store_cached_graph(cache, fp, original, src)
        loaded = load_cached_graph(cache, src, fp)

        assert loaded is not None
        assert loaded.packages == original.packages
        assert loaded.get_reverse_deps({"core_lib"}) == original.get_reverse_deps({"core_lib"})
        assert loaded.get_forward_deps({"perception_node"}) == original.get_forward_deps(
            {"perception_node"}
        )
        # Absolute package paths are restored relative to src.
        assert loaded.package_path("core_lib") == src / "core_lib"

    def test_miss_on_absent(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        assert load_cached_graph(tmp_path / "cache", src, "deadbeef") is None

    def test_miss_on_format_version(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        graph = DependencyGraphAnalyzer()
        graph.scan(src)
        fp = compute_fingerprint(src)
        store_cached_graph(cache, fp, graph, src)

        path = cache / f"{fp}.json"
        data = json.loads(path.read_text())
        data["cache_format_version"] = CACHE_FORMAT_VERSION + 1
        path.write_text(json.dumps(data))

        assert load_cached_graph(cache, src, fp) is None

    def test_miss_on_fingerprint_mismatch(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        graph = DependencyGraphAnalyzer()
        graph.scan(src)
        fp = compute_fingerprint(src)
        store_cached_graph(cache, fp, graph, src)

        # The file body claims a different fingerprint than its name implies.
        path = cache / f"{fp}.json"
        data = json.loads(path.read_text())
        data["fingerprint"] = "tampered"
        path.write_text(json.dumps(data))

        assert load_cached_graph(cache, src, fp) is None

    def test_miss_on_corrupt(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        cache.mkdir(parents=True)
        fp = "abc123"
        (cache / f"{fp}.json").write_text("{not valid json")
        assert load_cached_graph(cache, src, fp) is None

    def test_store_writes_valid_json(self, sample_ws: Path, tmp_path: Path) -> None:
        src = sample_ws / "src"
        cache = tmp_path / "cache"
        graph = DependencyGraphAnalyzer()
        graph.scan(src)
        fp = compute_fingerprint(src)
        store_cached_graph(cache, fp, graph, src)

        path = cache / f"{fp}.json"
        data = json.loads(path.read_text())
        assert data["fingerprint"] == fp
        assert data["cache_format_version"] == CACHE_FORMAT_VERSION
        # No stray temp files left behind.
        assert list(cache.glob(".*.tmp")) == []
