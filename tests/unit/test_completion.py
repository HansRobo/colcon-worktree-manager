"""Unit tests for cwm.cli.completion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import cwm.cli.completion as completion_mod
from cwm.cli.completion import (
    complete_distros,
    complete_git_branches,
    complete_sub_repos,
    complete_worktree_branches,
    complete_worktree_sub_repos,
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


# ---------------------------------------------------------------------------
# complete_worktree_branches
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# complete_git_branches
# ---------------------------------------------------------------------------


class TestCompleteGitBranches:
    def test_returns_matching_branches(self):
        config = MagicMock()
        config.base_ws_path = Path("/fake/base_ws")
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


# ---------------------------------------------------------------------------
# complete_sub_repos
# ---------------------------------------------------------------------------


class TestCompleteSubRepos:
    def test_returns_matching_sub_repos(self, tmp_path: Path):
        config = MagicMock()
        config.base_src_path = tmp_path
        wsm = MagicMock()

        fake_repos = {
            "core/autoware_core": tmp_path / "core/autoware_core",
            "universe/autoware_universe": tmp_path / "universe/autoware_universe",
        }

        with (
            patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)),
            patch("cwm.util.repos.discover_sub_repos", return_value=fake_repos),
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_sub_repos(_ctx(), _param(), "core")

        assert [i.value for i in items] == ["core/autoware_core"]

    def test_returns_empty_on_exception(self):
        with patch.object(
            completion_mod, "_load_config_and_wsm", side_effect=RuntimeError("fail")
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_sub_repos(_ctx(), _param(), "")

        assert items == []


# ---------------------------------------------------------------------------
# complete_worktree_sub_repos
# ---------------------------------------------------------------------------


class TestCompleteWorktreeSubRepos:
    def test_returns_sub_repos_for_given_branch(self):
        config = MagicMock()
        wsm = MagicMock()
        meta = MagicMock()
        meta.sub_repos = ["core/autoware_core", "universe/autoware_universe"]
        wsm.get_worktree_meta.return_value = meta

        with patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)):
            completion_mod._load_config_and_wsm.cache_clear()
            ctx = _ctx({"branch": "feature-x"})
            items = complete_worktree_sub_repos(ctx, _param(), "universe")

        assert [i.value for i in items] == ["universe/autoware_universe"]
        wsm.get_worktree_meta.assert_called_once_with("feature-x")

    def test_returns_empty_when_no_branch_in_params(self):
        config = MagicMock()
        wsm = MagicMock()

        with patch.object(completion_mod, "_load_config_and_wsm", return_value=(config, wsm)):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_worktree_sub_repos(_ctx(), _param(), "")

        assert items == []
        wsm.get_worktree_meta.assert_not_called()

    def test_returns_empty_on_exception(self):
        with patch.object(
            completion_mod, "_load_config_and_wsm", side_effect=RuntimeError("fail")
        ):
            completion_mod._load_config_and_wsm.cache_clear()
            items = complete_worktree_sub_repos(_ctx({"branch": "x"}), _param(), "")

        assert items == []


# ---------------------------------------------------------------------------
# complete_distros
# ---------------------------------------------------------------------------


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
