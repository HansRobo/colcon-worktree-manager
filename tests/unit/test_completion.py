"""Unit tests for cwm.cli.completion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import cwm.cli.completion as completion_mod
from cwm.cli.completion import (
    complete_distros,
    complete_git_branches,
    complete_worktree_branches,
)


def _ctx(params: dict | None = None) -> MagicMock:
    ctx = MagicMock(spec=["params"])
    ctx.params = params or {}
    return ctx


def _param() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear lru_cache between tests."""
    completion_mod._load_config_and_wsm.cache_clear()
    yield
    completion_mod._load_config_and_wsm.cache_clear()


class TestCompleteWorktreeBranches:
    def _make_meta(self, branch: str) -> MagicMock:
        m = MagicMock()
        m.branch = branch
        return m

    def test_returns_matching_branches(self):
        wsm = MagicMock()
        wsm.list_worktrees.return_value = [
            self._make_meta("feature-a"),
            self._make_meta("feature-b"),
            self._make_meta("hotfix-1"),
        ]
        config = MagicMock()

        with patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_worktree_branches(_ctx(), _param(), "feature")

        assert {i.value for i in items} == {"feature-a", "feature-b"}

    def test_returns_all_branches_on_empty_incomplete(self):
        wsm = MagicMock()
        wsm.list_worktrees.return_value = [
            self._make_meta("main"),
            self._make_meta("dev"),
        ]
        config = MagicMock()

        with patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_worktree_branches(_ctx(), _param(), "")

        assert {i.value for i in items} == {"main", "dev"}

    def test_returns_empty_on_exception(self):
        with patch.object(
            completion_mod, "_load_config_and_wsm", side_effect=RuntimeError("no project")
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_worktree_branches(_ctx(), _param(), "feat")

        assert items == []


class TestCompleteGitBranches:
    def test_returns_matching_branches(self):
        config = MagicMock()
        config.repo_path = Path("/fake/src/my_repo")
        wsm = MagicMock()

        with (
            patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)),
            patch("cwm.util.git.list_branches", return_value=["main", "dev", "feature-xyz"]),
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_git_branches(_ctx(), _param(), "feat")

        assert [i.value for i in items] == ["feature-xyz"]

    def test_returns_empty_on_exception(self):
        with patch.object(
            completion_mod, "_load_config_and_wsm", side_effect=RuntimeError("no git")
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_git_branches(_ctx(), _param(), "")

        assert items == []


class TestCompleteDistros:
    def test_returns_matching_distros(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        import cwm.util.ros_env as ros_env

        (tmp_path / "jazzy").mkdir()
        (tmp_path / "jazzy" / "setup.bash").write_text("# fake")
        (tmp_path / "humble").mkdir()
        (tmp_path / "humble" / "setup.bash").write_text("# fake")
        monkeypatch.setattr(ros_env, "ROS_INSTALL_BASE", tmp_path)

        items = complete_distros(_ctx(), _param(), str(tmp_path / "j"))

        assert len(items) == 1
        assert items[0].value == str(tmp_path / "jazzy")

    def test_returns_empty_on_exception(self):
        with patch("cwm.util.ros_env.list_available_distros", side_effect=RuntimeError("fail")):
            items = complete_distros(_ctx(), _param(), "")

        assert items == []
