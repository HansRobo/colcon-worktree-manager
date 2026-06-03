"""Tests for cwm inspect changed."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cwm.cli.main import cli
from cwm.core.changeset import Changeset


def _activate_env(ws: Path) -> dict:
    return {"CWM_ACTIVE": "1", "CWM_WORKTREE": "feature-x", "CWM_WORKSPACE": str(ws)}


@contextlib.contextmanager
def _patched(changeset: Changeset):
    cfg = MagicMock()
    with patch("cwm.cli.inspect_changed_cmd.resolve_worktree", return_value=("feature-x", Path("/ws"), cfg)), \
         patch("cwm.cli.inspect_changed_cmd.compute_changeset", return_value=changeset):
        yield


class TestInspectChanged:
    def test_human_output_lists_changed_and_affected(self, tmp_path: Path) -> None:
        cs = Changeset(
            package_count=5,
            changed={"pkg_a"},
            affected={"pkg_b"},
            build_order=["pkg_a", "pkg_b"],
        )
        runner = CliRunner()
        with _patched(cs):
            result = runner.invoke(cli, ["inspect", "changed"], env=_activate_env(tmp_path))

        assert result.exit_code == 0, result.output
        assert "Changed: pkg_a" in result.output
        assert "pkg_b" in result.output
        assert "pkg_a -> pkg_b" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        cs = Changeset(
            package_count=5,
            changed={"pkg_a"},
            affected={"pkg_b"},
            build_order=["pkg_a", "pkg_b"],
        )
        runner = CliRunner()
        with _patched(cs):
            result = runner.invoke(cli, ["inspect", "changed", "--json"], env=_activate_env(tmp_path))

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == {
            "changed": ["pkg_a"],
            "affected": ["pkg_b"],
            "build_order": ["pkg_a", "pkg_b"],
            "package_count": 5,
        }

    def test_no_changes(self, tmp_path: Path) -> None:
        cs = Changeset(package_count=3, changed=set(), affected=set(), build_order=[])
        runner = CliRunner()
        with _patched(cs):
            result = runner.invoke(cli, ["inspect", "changed"], env=_activate_env(tmp_path))

        assert result.exit_code == 0, result.output
        assert "No changed packages" in result.output
