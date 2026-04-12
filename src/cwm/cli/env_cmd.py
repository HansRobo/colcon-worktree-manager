"""cwm env - output environment variables for a worktree."""

from __future__ import annotations

import json

import click

from cwm.cli.completion import complete_worktree_branches
from cwm.cli.main import cli
from cwm.core.config import Config
from cwm.errors import CWMError
from cwm.util.fs import find_project_root


@cli.command()
@click.argument("branch", shell_complete=complete_worktree_branches)
def env(branch: str) -> None:
    """Show the environment variables for the BRANCH worktree.

    Outputs the CWM environment markers and the setup scripts that
    should be sourced to establish the ROS 2 overlay environment.
    """
    try:
        root = find_project_root()
        config = Config.load(root)

        ws_path = config.worktree_ws_path(branch)
        if not ws_path.exists():
            raise CWMError(
                f"Worktree workspace not found: {ws_path}\n"
                f"Create it first with: cwm worktree add {branch}"
            )

        source_scripts: list[str] = []

        # Underlay (ROS 2 distro)
        underlay_setup = config.underlay + "/setup.bash"
        source_scripts.append(underlay_setup)

        # Base workspace install
        base_setup = str(config.base_install_path / "setup.bash")
        source_scripts.append(base_setup)

        # Overlay workspace local_setup (may not exist until first build)
        overlay_setup = str(config.worktree_install_path(branch) / "local_setup.bash")
        source_scripts.append(overlay_setup)

        result = {
            "CWM_ACTIVE": "1",
            "CWM_PROJECT_ROOT": str(root),
            "CWM_WORKTREE": branch,
            "CWM_WORKSPACE": str(ws_path),
            "source_scripts": source_scripts,
        }

        click.echo(json.dumps(result))

    except CWMError as exc:
        click.echo(json.dumps({"error": str(exc)}))
        raise SystemExit(1) from exc
