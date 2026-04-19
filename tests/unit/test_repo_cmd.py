"""Unit tests for cwm repo {show, switch} commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cwm.cli.main import cli
from cwm.core.config import Config
from tests.conftest import make_git_repo


class TestRepoShow:
    def test_shows_current_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()
        project = tmp_path / "ws"
        project.mkdir()
        make_git_repo(project / "src" / "my_repo")
        monkeypatch.chdir(project)

        runner = CliRunner()
        runner.invoke(cli, ["init", "--underlay", str(underlay)], catch_exceptions=False)
        result = runner.invoke(cli, ["repo", "show"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "my_repo" in result.output

    def test_shows_no_repo_when_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()
        project = tmp_path / "ws"
        project.mkdir()
        monkeypatch.chdir(project)

        runner = CliRunner()
        runner.invoke(cli, ["init", "--underlay", str(underlay)], catch_exceptions=False)
        result = runner.invoke(cli, ["repo", "show"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "No repository" in result.output


class TestRepoSwitch:
    def test_switch_updates_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()
        project = tmp_path / "ws"
        project.mkdir()
        make_git_repo(project / "src" / "repo_a")
        make_git_repo(project / "src" / "repo_b")
        monkeypatch.chdir(project)

        runner = CliRunner()
        runner.invoke(
            cli,
            ["init", "--underlay", str(underlay), "--repo", "repo_a"],
            catch_exceptions=False,
        )
        result = runner.invoke(cli, ["repo", "switch", "repo_b"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        config = Config.load(project)
        assert config.repo == "repo_b"

    def test_switch_validates_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        underlay = tmp_path / "ros"
        underlay.mkdir()
        project = tmp_path / "ws"
        project.mkdir()
        make_git_repo(project / "src" / "my_repo")
        monkeypatch.chdir(project)

        runner = CliRunner()
        runner.invoke(cli, ["init", "--underlay", str(underlay)], catch_exceptions=False)
        result = runner.invoke(cli, ["repo", "switch", "nonexistent_repo"])

        assert result.exit_code != 0
        assert "nonexistent_repo" in result.output
