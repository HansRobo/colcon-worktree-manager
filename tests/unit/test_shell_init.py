"""Tests for the 'cwm shell-init' output."""

from __future__ import annotations

from click.testing import CliRunner

from cwm.cli.main import cli


def _shell_init_output() -> str:
    runner = CliRunner()
    result = runner.invoke(cli, ["shell-init"])
    assert result.exit_code == 0, result.output
    return result.output


class TestShellInit:
    def test_emits_cwm_function(self) -> None:
        out = _shell_init_output()
        assert "cwm()" in out

    def test_emits_git_wrapper(self) -> None:
        out = _shell_init_output()
        assert "git()" in out
        assert "cwm worktree __git_hook" in out

    def test_emits_in_project_helper(self) -> None:
        out = _shell_init_output()
        assert "__cwm_in_project()" in out

    def test_does_not_reference_cwm_active(self) -> None:
        """The directory-based detector must not depend on CWM_ACTIVE so that
        an activated shell which has cd'd into an unrelated repo does not
        hijack 'git worktree' there."""
        out = _shell_init_output()
        # Allow the env var to be set elsewhere, but not within __cwm_in_project.
        start = out.index("__cwm_in_project()")
        end = out.index("}", start)
        helper_body = out[start:end]
        assert "CWM_ACTIVE" not in helper_body

    def test_git_function_only_intercepts_worktree(self) -> None:
        out = _shell_init_output()
        start = out.index("git()")
        end = out.index("}", start)
        body = out[start:end]
        assert 'if [[ "$1" == "worktree" ]]' in body
        assert "command git" in body

    def test_git_function_intercepts_worktree_behind_global_options(self) -> None:
        """'git -C <path> worktree ...' must not slip past the interceptor, so
        the function consults a scanner that skips leading global options."""
        out = _shell_init_output()
        assert "__cwm_git_has_worktree()" in out
        start = out.index("git()")
        end = out.index("\n}", start)
        body = out[start:end]
        assert "__cwm_git_has_worktree" in body

    def test_git_has_worktree_skips_value_taking_options_in_pairs(self) -> None:
        """The scanner must skip '-C/-c/--git-dir/...' together with their value
        so the value is not mistaken for the subcommand."""
        out = _shell_init_output()
        start = out.index("__cwm_git_has_worktree()")
        end = out.index("\n}", start)
        body = out[start:end]
        assert "shift 2" in body
        assert "-C|-c|--git-dir|--work-tree" in body

    def test_in_project_helper_breaks_on_fixed_point_dirname(self) -> None:
        """__cwm_in_project must not infinite-loop when dirname returns the
        same value (e.g. dirname '.' -> '.')."""
        out = _shell_init_output()
        start = out.index("__cwm_in_project()")
        end = out.index("}", start)
        body = out[start:end]
        # Either an explicit prev/dir comparison or a guard against fixed-point
        assert "prev" in body
        assert '"$dir" == "$prev"' in body or 'dir == prev' in body
