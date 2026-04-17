"""Unit tests for cwm.cli.cd_cmd."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cwm.cli.cd_cmd import _resolve, cd, cd_resolve, switch
from cwm.core.config import Config
from cwm.core.wsm import WorktreeMeta
from cwm.errors import CWMError


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal CWM project structure."""
    cwm_dir = tmp_path / ".cwm"
    cwm_dir.mkdir()
    (cwm_dir / "worktrees").mkdir()
    config = Config(project_root=tmp_path)
    config.save()
    return tmp_path


@pytest.fixture
def config(project_root: Path) -> Config:
    return Config.load(project_root)


def _make_meta(branch: str, sub_repos: list[str] | None = None) -> WorktreeMeta:
    return WorktreeMeta(
        branch=branch,
        created_at="2025-01-01T00:00:00",
        base_sha="abc123",
        sub_repos=sub_repos or [],
    )


# ---------------------------------------------------------------------------
# _resolve: no arguments
# ---------------------------------------------------------------------------


class TestResolveNoArgs:
    def test_returns_active_workspace(self, project_root: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CWM_WORKSPACE", str(project_root / "worktrees" / "feat_ws"))
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            result = _resolve(())
        assert result == str(project_root / "worktrees" / "feat_ws")

    def test_error_when_no_active_workspace(self, project_root: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("CWM_WORKSPACE", raising=False)
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with pytest.raises(CWMError, match="No worktree specified"):
                _resolve(())


# ---------------------------------------------------------------------------
# _resolve: base
# ---------------------------------------------------------------------------


class TestResolveBase:
    def test_returns_project_root(self, project_root: Path):
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            result = _resolve(("base",))
        assert result == str(project_root)


# ---------------------------------------------------------------------------
# _resolve: branch name
# ---------------------------------------------------------------------------


class TestResolveBranch:
    def test_returns_worktree_root(self, project_root: Path):
        meta = _make_meta("feature-x", ["core/repo_a"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                result = _resolve(("feature-x",))
        assert result == str(project_root / "worktrees" / "feature-x_ws")

    def test_returns_sub_repo_path(self, project_root: Path):
        meta = _make_meta("feature-x", ["core/repo_a", "core/repo_b"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve(("feature-x", "core/repo_a"))
        assert result == str(project_root / "worktrees" / "feature-x_ws" / "src" / "core" / "repo_a")

    def test_error_on_unknown_sub_repo(self, project_root: Path):
        meta = _make_meta("feature-x", ["core/repo_a"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                with pytest.raises(CWMError, match="Sub-repo 'missing' not found"):
                    _resolve(("feature-x", "missing"))


# ---------------------------------------------------------------------------
# _resolve: sub-repo in active worktree
# ---------------------------------------------------------------------------


class TestResolveActiveSubRepo:
    def test_returns_sub_repo_in_active_worktree(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ws = str(project_root / "worktrees" / "feat_ws")
        monkeypatch.setenv("CWM_WORKSPACE", ws)
        monkeypatch.setenv("CWM_WORKTREE", "feat")

        meta = _make_meta("feat", ["core/repo_a"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve(("core/repo_a",))
        assert result == str(project_root / "worktrees" / "feat_ws" / "src" / "core" / "repo_a")


# ---------------------------------------------------------------------------
# _resolve: unknown target
# ---------------------------------------------------------------------------


class TestResolveUnknown:
    def test_error_on_unknown_target(self, project_root: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("CWM_WORKSPACE", raising=False)
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = []
                with pytest.raises(CWMError, match="No worktree or sub-repo found"):
                    _resolve(("nonexistent",))


# ---------------------------------------------------------------------------
# cd_resolve CLI command
# ---------------------------------------------------------------------------


class TestCdResolveCommand:
    def test_outputs_path_on_success(self, project_root: Path):
        with (
            patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root),
            patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM,
        ):
            MockWSM.return_value.list_worktrees.return_value = []
            runner = CliRunner()
            result = runner.invoke(cd_resolve, ["base"])
        assert result.exit_code == 0
        assert result.output.strip() == str(project_root)

    def test_outputs_error_on_failure(self, project_root: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("CWM_WORKSPACE", raising=False)
        with (
            patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root),
            patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM,
        ):
            MockWSM.return_value.list_worktrees.return_value = []
            runner = CliRunner()
            result = runner.invoke(cd_resolve, ["nonexistent"])
        assert result.exit_code == 1
        assert "No worktree or sub-repo found" in result.output


# ---------------------------------------------------------------------------
# _resolve: auto_subrepo flag
# ---------------------------------------------------------------------------


class TestResolveAutoSubrepo:
    def test_no_args_returns_sole_subrepo(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ws = str(project_root / "worktrees" / "feat_ws")
        monkeypatch.setenv("CWM_WORKSPACE", ws)
        monkeypatch.setenv("CWM_WORKTREE", "feat")
        meta = _make_meta("feat", ["core/repo_a"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve((), auto_subrepo=True)
        assert result == str(project_root / "worktrees" / "feat_ws" / "src" / "core" / "repo_a")

    def test_no_args_returns_workspace_when_multiple_subrepos(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ws = str(project_root / "worktrees" / "feat_ws")
        monkeypatch.setenv("CWM_WORKSPACE", ws)
        monkeypatch.setenv("CWM_WORKTREE", "feat")
        meta = _make_meta("feat", ["core/repo_a", "core/repo_b"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve((), auto_subrepo=True)
        assert result == ws

    def test_branch_arg_returns_sole_subrepo(self, project_root: Path):
        meta = _make_meta("feature-x", ["core/repo_a"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve(("feature-x",), auto_subrepo=True)
        assert result == str(
            project_root / "worktrees" / "feature-x_ws" / "src" / "core" / "repo_a"
        )

    def test_branch_arg_returns_workspace_when_multiple_subrepos(self, project_root: Path):
        meta = _make_meta("feature-x", ["core/repo_a", "core/repo_b"])
        with patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root):
            with patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM:
                MockWSM.return_value.list_worktrees.return_value = [meta]
                MockWSM.return_value.get_worktree_meta.return_value = meta
                result = _resolve(("feature-x",), auto_subrepo=True)
        assert result == str(project_root / "worktrees" / "feature-x_ws")


# ---------------------------------------------------------------------------
# cd_resolve --auto-subrepo flag
# ---------------------------------------------------------------------------


class TestCdResolveAutoSubrepo:
    def test_auto_subrepo_flag_selects_sole_subrepo(
        self, project_root: Path, monkeypatch: pytest.MonkeyPatch
    ):
        ws = str(project_root / "worktrees" / "feat_ws")
        monkeypatch.setenv("CWM_WORKSPACE", ws)
        monkeypatch.setenv("CWM_WORKTREE", "feat")
        meta = _make_meta("feat", ["core/repo_a"])
        with (
            patch("cwm.cli.cd_cmd.find_project_root", return_value=project_root),
            patch("cwm.cli.cd_cmd.WorktreeStateManager") as MockWSM,
        ):
            MockWSM.return_value.list_worktrees.return_value = [meta]
            MockWSM.return_value.get_worktree_meta.return_value = meta
            runner = CliRunner()
            result = runner.invoke(cd_resolve, ["--auto-subrepo"])
        assert result.exit_code == 0
        assert result.output.strip() == str(
            project_root / "worktrees" / "feat_ws" / "src" / "core" / "repo_a"
        )


# ---------------------------------------------------------------------------
# cd CLI command (visible, shows TTY hint)
# ---------------------------------------------------------------------------


class TestCdCommand:
    def test_shows_tty_hint(self):
        runner = CliRunner()
        result = runner.invoke(cd, ["base"])
        assert result.exit_code != 0
        assert "shell integration" in result.output


# ---------------------------------------------------------------------------
# switch CLI command (visible, shows TTY hint)
# ---------------------------------------------------------------------------


class TestSwitchCommand:
    def test_shows_tty_hint(self):
        runner = CliRunner()
        result = runner.invoke(switch, ["feature-x"])
        assert result.exit_code != 0
        assert "shell integration" in result.output
