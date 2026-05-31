"""Tests for cwm.util.colcon_runner sourced runners."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cwm.errors import ColconError
from cwm.util.colcon_runner import run_colcon_build_sourced, run_colcon_sourced


class TestRunColconSourced:
    def test_subcommand_embedded_in_sourced_shell_script(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            run_colcon_sourced("test", tmp_path, tmp_path / "underlay", None)

        cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["bash", "-c"]
        assert "source" in cmd[2]
        assert "colcon test" in cmd[2]

    def test_extra_args_appended_after_subcommand(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            run_colcon_sourced(
                "build", tmp_path, tmp_path / "underlay", None,
                ["--packages-select", "pkg"],
            )

        assert "colcon build --packages-select pkg" in mock_run.call_args[0][0][2]

    def test_nonzero_exit_raises_colcon_error_with_subcommand(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            with pytest.raises(ColconError, match="colcon test"):
                run_colcon_sourced("test", tmp_path, tmp_path / "underlay", None)

    def test_build_wrapper_delegates_with_build_subcommand(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            run_colcon_build_sourced(tmp_path, tmp_path / "underlay", None)

        assert "colcon build" in mock_run.call_args[0][0][2]
