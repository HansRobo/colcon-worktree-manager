"""Tests for cwm colcon-passthrough functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cwm.cli.main import cli


# ---------------------------------------------------------------------------
# cwm ws build: unknown flags forwarded without "--"
# ---------------------------------------------------------------------------

class TestBuildPassthrough:
    """cwm ws build should forward unknown colcon flags without requiring '--'."""

    def _make_env(self, ws: Path) -> dict:
        return {
            "CWM_ACTIVE": "1",
            "CWM_WORKTREE": "feature-x",
            "CWM_WORKSPACE": str(ws),
        }

    def test_build_unknown_flags_forwarded_dry_run(self, tmp_path: Path) -> None:
        """--symlink-install and --cmake-args are forwarded in dry-run mode."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.cli.build_cmd.find_project_root", return_value=tmp_path), \
             patch("cwm.core.config.Config.load") as mock_cfg, \
             patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta", return_value=[]), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages", return_value={"my_pkg"}), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps", return_value=set()), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort", return_value=["my_pkg"]), \
             patch("cwm.core.cdc.ColconDiscoveryController.generate_build_args", return_value=["--packages-select", "my_pkg"]), \
             patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:

            cfg = mock_cfg.return_value
            cfg.worktree_ws_path.return_value = ws
            cfg.worktree_src_path.return_value = ws / "src"
            cfg.worktree_meta_path.return_value = ws / "meta.json"
            cfg.symlink_install = False
            cfg.worktree_install_path.return_value = ws / "install"
            cfg.base_install_path = tmp_path / "install"

            mock_meta.return_value.sub_repos = []
            mock_meta.return_value.sub_repo_shas = {}

            result = runner.invoke(
                cli,
                ["ws", "build", "--dry-run", "--symlink-install", "--cmake-args", "-DCMAKE_BUILD_TYPE=Release"],
                env=self._make_env(ws),
            )

        assert result.exit_code == 0, result.output
        assert "--symlink-install" in result.output
        assert "-DCMAKE_BUILD_TYPE=Release" in result.output

    def test_build_no_double_dash_required(self, tmp_path: Path) -> None:
        """cwm ws build --dry-run --symlink-install must not fail with 'No such option'."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.cli.build_cmd.find_project_root", return_value=tmp_path), \
             patch("cwm.core.config.Config.load") as mock_cfg, \
             patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta", return_value=[]), \
             patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages", return_value={"my_pkg"}), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps", return_value=set()), \
             patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort", return_value=["my_pkg"]), \
             patch("cwm.core.cdc.ColconDiscoveryController.generate_build_args", return_value=[]), \
             patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:

            cfg = mock_cfg.return_value
            cfg.worktree_ws_path.return_value = ws
            cfg.worktree_src_path.return_value = ws / "src"
            cfg.worktree_meta_path.return_value = ws / "meta.json"
            cfg.symlink_install = False
            cfg.worktree_install_path.return_value = ws / "install"
            cfg.base_install_path = tmp_path / "install"

            mock_meta.return_value.sub_repos = []
            mock_meta.return_value.sub_repo_shas = {}

            result = runner.invoke(
                cli,
                ["ws", "build", "--dry-run", "--symlink-install"],
                env=self._make_env(ws),
            )

        assert "No such option" not in result.output
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Removed top-level commands must not fall through to colcon passthrough
# ---------------------------------------------------------------------------


class TestMovedTopLevelCommands:
    @pytest.mark.parametrize(
        ("old_name", "new_path"),
        [
            ("build", "ws build"),
            ("clean", "ws clean"),
            ("status", "ws status"),
            ("env", "inspect env"),
            ("detect", "inspect detect"),
        ],
    )
    def test_old_command_reports_new_location(self, old_name: str, new_path: str) -> None:
        runner = CliRunner()

        result = runner.invoke(cli, [old_name, "--anything"])

        assert result.exit_code != 0
        assert f"'cwm {old_name}' was removed." in result.output
        assert f"Use: cwm {new_path}" in result.output


# ---------------------------------------------------------------------------
# Generic colcon-verb passthrough
# ---------------------------------------------------------------------------

class TestColconPassthrough:
    """Unknown cwm subcommands should be forwarded to colcon in the active workspace."""

    def test_unknown_verb_without_activation_raises_error(self) -> None:
        """cwm list without activation should fail with a clear message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list"], env={})
        assert result.exit_code != 0
        assert "active CWM workspace" in result.output

    def test_unknown_verb_with_activation_calls_colcon(self, tmp_path: Path) -> None:
        """cwm list with CWM_WORKSPACE set should call colcon list in that directory."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                cli,
                ["list"],
                env={"CWM_WORKSPACE": str(ws)},
            )

        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["colcon", "list"]
        assert call_args[1]["cwd"] == ws

    def test_unknown_verb_forwards_args(self, tmp_path: Path) -> None:
        """cwm test --packages-select my_pkg should call colcon test --packages-select my_pkg."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                cli,
                ["test", "--packages-select", "my_pkg"],
                env={"CWM_WORKSPACE": str(ws)},
            )

        assert result.exit_code == 0, result.output
        call_args = mock_run.call_args
        assert call_args[0][0] == ["colcon", "test", "--packages-select", "my_pkg"]

    def test_colcon_failure_propagates_exit_code(self, tmp_path: Path) -> None:
        """Non-zero colcon exit should result in a ClickException."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = runner.invoke(
                cli,
                ["test"],
                env={"CWM_WORKSPACE": str(ws)},
            )

        assert result.exit_code != 0
