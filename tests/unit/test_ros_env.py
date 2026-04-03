"""Unit tests for cwm.util.ros_env."""

from __future__ import annotations

from pathlib import Path

import pytest

import cwm.util.ros_env as ros_env


def _make_distro(base: Path, name: str) -> Path:
    """Create a fake ROS distro directory with setup.bash."""
    distro_path = base / name
    distro_path.mkdir(parents=True)
    (distro_path / "setup.bash").write_text("# fake setup")
    return distro_path


class TestDetectSystemUnderlay:
    def test_uses_ros_distro_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _make_distro(tmp_path, "jazzy")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.setenv("ROS_DISTRO", "jazzy")

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "jazzy")

    def test_env_var_invalid_path_falls_back_to_scan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_distro(tmp_path, "humble")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.setenv("ROS_DISTRO", "nonexistent")

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "humble")

    def test_scan_picks_alphabetically_last_named_distro(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_distro(tmp_path, "humble")
        _make_distro(tmp_path, "jazzy")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.delenv("ROS_DISTRO", raising=False)

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "jazzy")

    def test_rolling_excluded_when_named_distro_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_distro(tmp_path, "jazzy")
        _make_distro(tmp_path, "rolling")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.delenv("ROS_DISTRO", raising=False)

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "jazzy")

    def test_falls_back_to_rolling_when_only_rolling_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_distro(tmp_path, "rolling")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.delenv("ROS_DISTRO", raising=False)

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "rolling")

    def test_returns_none_when_nothing_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.delenv("ROS_DISTRO", raising=False)

        result = ros_env.detect_system_underlay()
        assert result is None

    def test_returns_none_when_base_dir_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path / "nonexistent")
        monkeypatch.delenv("ROS_DISTRO", raising=False)

        result = ros_env.detect_system_underlay()
        assert result is None

    def test_ros_distro_env_rolling_used_directly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When $ROS_DISTRO=rolling is explicitly set, use it."""
        _make_distro(tmp_path, "rolling")
        _make_distro(tmp_path, "jazzy")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)
        monkeypatch.setenv("ROS_DISTRO", "rolling")

        result = ros_env.detect_system_underlay()
        assert result == str(tmp_path / "rolling")


class TestListAvailableDistros:
    def test_returns_all_distros(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _make_distro(tmp_path, "humble")
        _make_distro(tmp_path, "jazzy")
        _make_distro(tmp_path, "rolling")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)

        result = ros_env.list_available_distros()
        assert sorted(result) == sorted([
            str(tmp_path / "humble"),
            str(tmp_path / "jazzy"),
            str(tmp_path / "rolling"),
        ])

    def test_returns_empty_when_no_distros(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)

        result = ros_env.list_available_distros()
        assert result == []

    def test_returns_empty_when_base_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path / "nonexistent")

        result = ros_env.list_available_distros()
        assert result == []
