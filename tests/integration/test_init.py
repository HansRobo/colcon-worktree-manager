"""Integration tests for cwm init."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cwm.cli.main import cli
from cwm.core.config import Config


class TestCwmInit:
    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()

        project = tmp_path / "project"
        project.mkdir()

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project):
            result = runner.invoke(
                cli,
                ["init", "--underlay", str(underlay)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output

            cwd = Path.cwd()
            assert (cwd / ".cwm").is_dir()
            assert (cwd / ".cwm" / "config.yaml").is_file()
            assert (cwd / "base_ws" / "src").is_dir()
            assert (cwd / "base_ws" / "build").is_dir()
            assert (cwd / "base_ws" / "install").is_dir()
            assert (cwd / "worktrees").is_dir()

    def test_config_persisted(self, tmp_path: Path) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()

        project = tmp_path / "project"
        project.mkdir()

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project):
            result = runner.invoke(
                cli,
                ["init", "--underlay", str(underlay), "--base-branch", "develop"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            config = Config.load(Path.cwd())
            assert config.underlay == str(underlay)
            assert config.base_ws.branch == "develop"

    def test_double_init_fails(self, tmp_path: Path) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init", "--underlay", str(underlay)])
            result = runner.invoke(cli, ["init", "--underlay", str(underlay)])
            assert result.exit_code != 0
            assert "already initialised" in result.output
