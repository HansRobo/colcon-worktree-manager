"""Tests for cwm.util.colcon_runner sourced runners."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cwm.errors import ColconError
from cwm.util.colcon_runner import (
    run_colcon_build_sourced,
    run_colcon_sourced,
    run_colcon_test_result,
)


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

    def test_args_with_spaces_are_quoted(self, tmp_path: Path) -> None:
        """A colcon argument value containing spaces must be passed as a single
        token to the bash subshell, not word-split into separate arguments."""
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            run_colcon_sourced(
                "build", tmp_path, tmp_path / "underlay", None,
                ["--cmake-args", "-DFOO=bar baz"],
            )

        shell_script = mock_run.call_args[0][0][2]
        assert "'-DFOO=bar baz'" in shell_script
        # The raw, unquoted value must not appear adjacent to --cmake-args.
        assert "--cmake-args -DFOO=bar baz" not in shell_script

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


class TestRunColconTestResult:
    def test_passes_all_and_return_code_flag(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            run_colcon_test_result(tmp_path)

        cmd = mock_run.call_args[0][0]
        assert cmd == ["colcon", "test-result", "--all", "--return-code-on-test-failure"]

    def test_nonzero_exit_raises_colcon_error(self, tmp_path: Path) -> None:
        with patch("cwm.util.colcon_runner.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            with pytest.raises(ColconError, match="colcon test-result"):
                run_colcon_test_result(tmp_path)
