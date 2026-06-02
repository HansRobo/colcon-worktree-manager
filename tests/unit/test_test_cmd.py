"""Tests for cwm ws test and cwm ws test-result commands."""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cwm.cli.main import cli


def _activate_env(ws: Path) -> dict:
    return {
        "CWM_ACTIVE": "1",
        "CWM_WORKTREE": "feature-x",
        "CWM_WORKSPACE": str(ws),
    }


@contextlib.contextmanager
def _patched_changeset(tmp_path: Path, ws: Path, *, changed: set[str], affected: set[str]):
    """Patch the changeset pipeline + config the way test_passthrough does for build."""
    with patch("cwm.cli._workspace.find_project_root", return_value=tmp_path), \
         patch("cwm.core.config.Config.load") as mock_cfg, \
         patch("cwm.core.dga.DependencyGraphAnalyzer.scan"), \
         patch("cwm.core.cdc.ColconDiscoveryController.get_changed_files_meta", return_value=[]), \
         patch("cwm.core.cdc.ColconDiscoveryController.get_changed_packages", return_value=changed), \
         patch("cwm.core.dga.DependencyGraphAnalyzer.get_reverse_deps", return_value=affected), \
         patch("cwm.core.dga.DependencyGraphAnalyzer.topological_sort", side_effect=lambda pkgs: sorted(pkgs)), \
         patch("cwm.core.wsm.WorktreeMeta.load") as mock_meta:

        cfg = mock_cfg.return_value
        cfg.worktree_ws_path.return_value = ws
        cfg.worktree_src_path.return_value = ws / "src"
        cfg.worktree_meta_path.return_value = ws / "meta.json"
        cfg.symlink_install = False
        cfg.worktree_install_path.return_value = ws / "install"
        cfg.base_install_path = tmp_path / "install"

        mock_meta.return_value.repo_name = "repo"
        mock_meta.return_value.base_sha = "abc123"
        mock_meta.return_value.sub_repos = []
        mock_meta.return_value.sub_repo_shas = {}

        yield cfg


class TestWsTest:
    def test_dry_run_shows_packages_select_only(self, tmp_path: Path) -> None:
        """--dry-run prints colcon test --packages-select without build-only flags."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with _patched_changeset(tmp_path, ws, changed={"pkg_a"}, affected=set()), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            result = runner.invoke(cli, ["ws", "test", "--dry-run"], env=_activate_env(ws))

        assert result.exit_code == 0, result.output
        assert "colcon test --packages-select pkg_a" in result.output
        assert "--allow-overriding" not in result.output
        assert "--symlink-install" not in result.output
        mock_run.assert_not_called()

    def test_activate_path_runs_colcon_test(self, tmp_path: Path) -> None:
        """With an active workspace, colcon test runs inheriting the environment."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with _patched_changeset(tmp_path, ws, changed={"pkg_a"}, affected={"pkg_b"}), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["ws", "test"], env=_activate_env(ws))

        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["colcon", "test"]
        assert "--packages-select" in cmd
        assert "pkg_a" in cmd and "pkg_b" in cmd
        assert "--allow-overriding" not in cmd

    def test_worktree_path_sources_environment(self, tmp_path: Path) -> None:
        """-w runs colcon test inside a sourced bash subshell."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with _patched_changeset(tmp_path, ws, changed={"pkg_a"}, affected=set()), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["ws", "test", "-w", "feature-x"])

        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["bash", "-c"]
        assert "source" in cmd[2]
        assert "colcon test" in cmd[2]

    def test_no_changes_skips_colcon(self, tmp_path: Path) -> None:
        """No changed packages prints a notice and runs nothing."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with _patched_changeset(tmp_path, ws, changed=set(), affected=set()), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            result = runner.invoke(cli, ["ws", "test"], env=_activate_env(ws))

        assert result.exit_code == 0, result.output
        assert "Nothing to test" in result.output
        mock_run.assert_not_called()

    def test_no_rdeps_excludes_affected(self, tmp_path: Path) -> None:
        """--no-rdeps tests changed packages only."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with _patched_changeset(tmp_path, ws, changed={"pkg_a"}, affected={"pkg_b"}), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["ws", "test", "--no-rdeps"], env=_activate_env(ws))

        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert "pkg_a" in cmd
        assert "pkg_b" not in cmd


class TestWsTestResult:
    def test_runs_test_result_with_return_code_flag(self, tmp_path: Path) -> None:
        """test-result forwards --all --return-code-on-test-failure to colcon."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.cli._workspace.find_project_root", return_value=tmp_path), \
             patch("cwm.core.config.Config.load"), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = runner.invoke(cli, ["ws", "test-result"], env=_activate_env(ws))

        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert cmd == ["colcon", "test-result", "--all", "--return-code-on-test-failure"]
        assert mock_run.call_args[1]["cwd"] == ws

    def test_nonzero_exit_on_test_failure(self, tmp_path: Path) -> None:
        """A failing test-result (non-zero colcon exit) propagates as exit 1."""
        ws = tmp_path / "feature-x_ws"
        ws.mkdir()

        runner = CliRunner()
        with patch("cwm.cli._workspace.find_project_root", return_value=tmp_path), \
             patch("cwm.core.config.Config.load"), \
             patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = runner.invoke(cli, ["ws", "test-result"], env=_activate_env(ws))

        assert result.exit_code == 1, result.output
