"""Tests for cwm.core.changeset.compute_changeset.

The pipeline's building blocks (scan / reverse-deps / topological sort / file
diff) are covered directly in test_dga.py and test_cdc.py.  Here we patch those
class methods and verify only how compute_changeset wires them together.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from cwm.core.changeset import compute_changeset


def _mock_config(tmp_path: Path) -> MagicMock:
    config = MagicMock()
    config.worktree_src_path.return_value = tmp_path / "src"
    config.worktree_meta_path.return_value = tmp_path / "meta.yaml"
    return config


class TestComputeChangeset:
    def test_includes_reverse_deps_in_topological_order(self, tmp_path: Path) -> None:
        config = _mock_config(tmp_path)
        with patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.packages",
                   new_callable=PropertyMock, return_value={"a", "b", "c"}), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta",
                   return_value=["repo/a/src/main.cpp"]), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages",
                   return_value={"a"}), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps",
                   return_value={"b"}), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort",
                   side_effect=sorted), \
             patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:
            mock_meta.return_value.repo_name = "repo"
            mock_meta.return_value.base_sha = "abc123"

            cs = compute_changeset(config, "feature-x")

        assert cs.package_count == 3
        assert cs.changed == {"a"}
        assert cs.affected == {"b"}
        assert cs.build_order == ["a", "b"]

    def test_no_rdeps_skips_reverse_dependency_analysis(self, tmp_path: Path) -> None:
        config = _mock_config(tmp_path)
        with patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.packages",
                   new_callable=PropertyMock, return_value={"a", "b"}), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta",
                   return_value=["repo/a/src/main.cpp"]), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages",
                   return_value={"a"}), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps") as mock_rev, \
             patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort",
                   side_effect=sorted), \
             patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:
            mock_meta.return_value.repo_name = "repo"
            mock_meta.return_value.base_sha = "abc123"

            cs = compute_changeset(config, "feature-x", no_rdeps=True)

        mock_rev.assert_not_called()
        assert cs.affected == set()
        assert cs.build_order == ["a"]

    def test_no_changes_yields_empty_build_order(self, tmp_path: Path) -> None:
        config = _mock_config(tmp_path)
        with patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.packages",
                   new_callable=PropertyMock, return_value={"a", "b"}), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta",
                   return_value=[]), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages",
                   return_value=set()), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps",
                   return_value=set()), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort",
                   side_effect=sorted), \
             patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:
            mock_meta.return_value.repo_name = "repo"
            mock_meta.return_value.base_sha = "abc123"

            cs = compute_changeset(config, "feature-x")

        assert cs.changed == set()
        assert cs.affected == set()
        assert cs.build_order == []
