"""Unit tests for CWM configuration."""

from __future__ import annotations

from pathlib import Path

from cwm.core.config import Config, BaseWorkspaceConfig


class TestConfigSerialization:
    def test_roundtrip(self, tmp_path: Path) -> None:
        config = Config(
            underlay="/opt/ros/jazzy",
            base_ws=BaseWorkspaceConfig(path="base_ws", branch="main"),
            worktrees_dir="worktrees",
            project_root=tmp_path,
        )
        config.save()
        loaded = Config.load(tmp_path)
        assert loaded.underlay == config.underlay
        assert loaded.base_ws.branch == config.base_ws.branch
        assert loaded.worktrees_dir == config.worktrees_dir

    def test_derived_paths(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.base_ws_path == tmp_path / "base_ws"
        assert config.base_src_path == tmp_path / "base_ws" / "src"
        assert config.worktrees_path == tmp_path / "worktrees"

    def test_worktree_ws_path_sanitises_slashes(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        ws = config.worktree_ws_path("feature/perception")
        assert "feature-perception_ws" in ws.name


class TestConfigDefaults:
    def test_default_underlay(self) -> None:
        config = Config()
        assert config.underlay == "/opt/ros/jazzy"

    def test_default_base_branch(self) -> None:
        config = Config()
        assert config.base_ws.branch == "main"
