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

    def test_default_mode_is_single(self) -> None:
        config = Config()
        assert config.mode == "single"
        assert not config.is_meta


class TestMetaConfig:
    def test_meta_mode_roundtrip(self, tmp_path: Path) -> None:
        config = Config(
            underlay="/opt/ros/jazzy",
            base_ws=BaseWorkspaceConfig(branch="main"),
            mode="meta",
            project_root=tmp_path,
        )
        config.save()
        loaded = Config.load(tmp_path)
        assert loaded.mode == "meta"
        assert loaded.is_meta

    def test_single_mode_not_serialised(self, tmp_path: Path) -> None:
        """mode='single' should be omitted from the YAML for backward compatibility."""
        import yaml

        config = Config(project_root=tmp_path)
        config.save()
        data = yaml.safe_load((tmp_path / ".cwm" / "config.yaml").read_text())
        assert "mode" not in data

    def test_old_config_defaults_to_single(self, tmp_path: Path) -> None:
        """Config files without 'mode' should load as single mode."""
        import yaml

        cwm_dir = tmp_path / ".cwm"
        cwm_dir.mkdir()
        (cwm_dir / "config.yaml").write_text(
            yaml.safe_dump({"version": 1, "underlay": "/opt/ros/jazzy"})
        )
        loaded = Config.load(tmp_path)
        assert loaded.mode == "single"
        assert not loaded.is_meta
