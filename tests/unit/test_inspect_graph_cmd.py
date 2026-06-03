"""Tests for cwm inspect graph."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cwm.cli.main import cli


def _activate_env(ws: Path) -> dict:
    return {"CWM_ACTIVE": "1", "CWM_WORKTREE": "feature-x", "CWM_WORKSPACE": str(ws)}


@contextlib.contextmanager
def _patched(src_path: Path):
    cfg = MagicMock()
    cfg.worktree_src_path.return_value = src_path
    cfg.dag_cache_dir = None
    with patch("cwm.cli.inspect_graph_cmd.resolve_worktree", return_value=("feature-x", src_path.parent, cfg)):
        yield


class TestInspectGraph:
    def test_human_output_shows_adjacency(self, sample_ws: Path) -> None:
        runner = CliRunner()
        with _patched(sample_ws / "src"):
            result = runner.invoke(cli, ["inspect", "graph"], env=_activate_env(sample_ws))

        assert result.exit_code == 0, result.output
        assert "Packages: 5" in result.output
        assert "perception_node -> core_lib, msgs" in result.output

    def test_json_output(self, sample_ws: Path) -> None:
        runner = CliRunner()
        with _patched(sample_ws / "src"):
            result = runner.invoke(cli, ["inspect", "graph", "--json"], env=_activate_env(sample_ws))

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["packages"]["perception_node"]["depends_on"] == ["core_lib", "msgs"]
        assert payload["packages"]["core_lib"]["depends_on"] == []
