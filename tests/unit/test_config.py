"""Unit tests for CWM configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwm.core.config import Config
from cwm.errors import ConfigVersionError


class TestConfigSerialization:
    def test_roundtrip(self, tmp_path: Path) -> None:
        config = Config(
            underlay="/opt/ros/jazzy",
            worktrees_dir="worktrees",
            project_root=tmp_path,
        )
        config.save()
        loaded = Config.load(tmp_path)
        assert loaded.underlay == config.underlay
        assert loaded.symlink_install == config.symlink_install
        assert loaded.worktrees_dir == config.worktrees_dir

    def test_derived_paths(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        assert config.base_src_path == tmp_path / "src"
        assert config.base_install_path == tmp_path / "install"
        assert config.worktrees_path == tmp_path / "worktrees"

    def test_worktree_ws_path_sanitises_slashes(self, tmp_path: Path) -> None:
        config = Config(project_root=tmp_path)
        ws = config.worktree_ws_path("feature/perception")
        assert "feature-perception_ws" in ws.name

    def test_v1_config_raises_helpful_error(self, tmp_path: Path) -> None:
        import yaml

        (tmp_path / ".cwm").mkdir()
        (tmp_path / ".cwm" / "config.yaml").write_text(
            yaml.safe_dump({"version": 1, "underlay": "/opt/ros/jazzy", "base_ws": {"path": "base_ws", "branch": "main"}})
        )
        with pytest.raises(ConfigVersionError, match="re-initialise"):
            Config.load(tmp_path)


class TestConfigDefaults:
    def test_default_underlay(self) -> None:
        config = Config()
        assert config.underlay == ""

    def test_no_base_ws_in_config(self, tmp_path: Path) -> None:
        import yaml

        config = Config(project_root=tmp_path)
        config.save()
        data = yaml.safe_load((tmp_path / ".cwm" / "config.yaml").read_text())
        assert "mode" not in data
        assert "base_ws" not in data
        assert "symlink_install" in data
