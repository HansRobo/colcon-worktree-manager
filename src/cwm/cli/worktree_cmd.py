"""cwm worktree {add, remove, list, prune} - manage overlay worktrees."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, NoReturn

import click

from cwm.cli.completion import complete_git_branches, complete_worktree_branches
from cwm.cli.main import worktree
from cwm.core.config import Config
from cwm.core.worktree_state import WorktreeStateManager
from cwm.errors import CWMError
from cwm.util import git as gitutil
from cwm.util.filesystem import find_project_root


def _load() -> tuple[Config, WorktreeStateManager]:
    root = find_project_root()
    config = Config.load(root)
    return config, WorktreeStateManager(config)


def _json_fail(msg: str) -> NoReturn:
    click.echo(json.dumps({"ok": False, "error": msg}))
    raise SystemExit(1)


def _json_ok(payload: dict[str, Any]) -> None:
    click.echo(json.dumps({"ok": True, **payload}))


@worktree.command()
@click.argument("branch", shell_complete=complete_git_branches)
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def add(branch: str, as_json: bool) -> None:
    """Create a new overlay worktree for BRANCH."""
    try:
        config, manager = _load()
        ws_path = manager.create_worktree(branch)
        repo_name = Path(config.repo).name if config.repo else ""
        src_path = config.worktree_src_path(branch) / repo_name

        if as_json:
            _json_ok({
                "branch": branch,
                "ws_path": str(ws_path),
                "src_path": str(src_path),
                "repo": config.repo,
            })
        else:
            click.echo(f"Created worktree workspace: {ws_path}")
            click.echo(f"  Repo:    {config.repo}")
            click.echo(f"  Source:  {src_path}")
            click.echo(f"  Build:   {ws_path / 'build'}")
            click.echo(f"  Install: {ws_path / 'install'}")
            click.echo()
            click.echo(f"Activate with: source <(cwm activate {branch})")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


@worktree.command("remove")
@click.argument("branch", shell_complete=complete_worktree_branches)
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes.")
@click.option("--delete-branch", is_flag=True, help="Also delete the git branch after removing the worktree.")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def remove(branch: str, force: bool, delete_branch: bool, as_json: bool) -> None:
    """Remove the overlay worktree for BRANCH."""
    try:
        config, manager = _load()
        if not force and not as_json:
            ws_path = config.worktree_ws_path(branch)
            click.echo("This will permanently remove:")
            click.echo(f"  Branch:    {branch}")
            click.echo(f"  Workspace: {ws_path}")
            if delete_branch:
                click.echo("  (git branch will also be deleted)")
            click.confirm("Continue?", abort=True)
        manager.remove_worktree(branch, force=force, delete_branch=delete_branch)

        if as_json:
            _json_ok({"branch": branch})
        else:
            click.echo(f"Removed worktree: {branch}")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


@worktree.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output result as JSON.")
def list_worktrees_cmd(as_json: bool) -> None:
    """List all managed worktrees."""
    try:
        config, manager = _load()
        metas = manager.list_worktrees()

        if as_json:
            items = []
            for meta in metas:
                ws_path = config.worktree_ws_path(meta.branch)
                items.append({
                    "branch": meta.branch,
                    "repo": meta.repo,
                    "ws_path": str(ws_path),
                    "exists": ws_path.exists(),
                    "created_at": meta.created_at,
                    "base_sha": meta.base_sha,
                })
            _json_ok({"worktrees": items})
            return

        if not metas:
            click.echo("No worktrees. Create one with: cwm worktree add <branch>")
            return
        for meta in metas:
            ws_path = config.worktree_ws_path(meta.branch)
            status = "exists" if ws_path.exists() else click.style("missing", fg="red")
            repo_str = f"  [{meta.repo}]" if meta.repo else ""
            click.echo(f"  {meta.branch}  ({status}){repo_str}  created {meta.created_at}")
    except CWMError as exc:
        if as_json:
            _json_fail(str(exc))
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# Git hook helpers
# ---------------------------------------------------------------------------


def _parse_git_worktree_add(
    args: list[str],
) -> tuple[Path, str, list[str]] | None:
    """Parse ``git worktree add`` arguments and extract (path, branch, ignored_flags).

    Returns None when the arguments cannot be parsed or no positional path was
    supplied; callers should fall back to a user-facing error message in that
    case.

    Native git flags whose semantics CWM cannot fully reproduce (e.g.
    ``--detach``, ``--orphan``, ``--lock``) are returned in *ignored_flags* so
    the caller can emit a warning rather than silently dropping them.
    """
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--checkout", action="store_true")
    parser.add_argument("--no-checkout", action="store_true")
    parser.add_argument("--lock", action="store_true")
    parser.add_argument("--reason")
    parser.add_argument("--orphan", action="store_true")
    parser.add_argument("--track", action="store_true")
    parser.add_argument("--no-track", action="store_true")
    parser.add_argument("--guess-remote", action="store_true")
    parser.add_argument("-b", dest="new_branch")
    parser.add_argument("-B", dest="reset_new_branch")
    parser.add_argument("positional", nargs="*")
    try:
        parsed = parser.parse_args(args)
    except (argparse.ArgumentError, SystemExit):
        return None
    pos = parsed.positional or []
    if not pos:
        return None
    path = Path(pos[0])
    branch = parsed.new_branch or parsed.reset_new_branch
    if branch is None:
        branch = pos[1] if len(pos) >= 2 else path.name
    ignored: list[str] = []
    if parsed.force:
        ignored.append("--force")
    if parsed.detach:
        ignored.append("--detach")
    if parsed.no_checkout:
        ignored.append("--no-checkout")
    if parsed.lock:
        ignored.append("--lock")
    if parsed.orphan:
        ignored.append("--orphan")
    return path, branch, ignored


def _hook_msg(line: str, *, fg: str | None = None, bold: bool = False) -> None:
    click.secho(f"[CWM Agent Hook] {line}", fg=fg, bold=bold, err=True)


def _hook_unsupported(ctx: click.Context, subcmd: str) -> NoReturn:
    _hook_msg(
        f"'git worktree {subcmd}' is not supported under CWM. "
        f"Run 'cwm worktree --help' for available commands.",
        fg="yellow",
    )
    ctx.exit(1)


def _hook_add(ctx: click.Context, rest: list[str]) -> None:
    parsed = _parse_git_worktree_add(rest)
    if parsed is None:
        _hook_msg(
            "Could not parse 'git worktree add' arguments. "
            "Use 'cwm worktree add <branch>' instead.",
            fg="yellow",
        )
        ctx.exit(1)
    requested_path, branch, ignored_flags = parsed

    for flag in ignored_flags:
        _hook_msg(
            f"Note: '{flag}' is ignored - CWM always creates a managed overlay worktree.",
            fg="yellow",
        )

    try:
        config, manager = _load()
        ws_path = manager.create_worktree(branch)
    except CWMError as exc:
        _hook_msg(str(exc), fg="red")
        ctx.exit(1)

    try:
        link_path = manager.register_agent_symlink(branch, requested_path)
    except (CWMError, OSError) as exc:
        # Roll back the half-created worktree so retry is not blocked.
        try:
            manager.remove_worktree(branch, force=True)
        except CWMError:
            pass
        _hook_msg(
            f"Failed to create symlink at {requested_path}: {exc}",
            fg="red",
        )
        ctx.exit(1)

    repo_name = config.repo_name
    src_path = ws_path / "src" / repo_name if repo_name else ws_path / "src"

    _hook_msg("Intercepted 'git worktree add'.", fg="green")
    _hook_msg(f"  Real workspace:  {ws_path}", fg="cyan")
    _hook_msg(
        f"  Symlink at:      {link_path}  "
        "(use this path or the real one - they are equivalent)",
        fg="cyan",
    )
    _hook_msg(f"  Repo checkout:   {src_path}", fg="cyan")
    _hook_msg(
        f"Next: run 'source <(cwm activate {branch})' "
        "to enter the CWM-managed environment.",
        fg="yellow",
        bold=True,
    )


def _hook_list(ctx: click.Context, rest: list[str]) -> None:
    porcelain = "--porcelain" in rest
    try:
        config, manager = _load()
    except CWMError as exc:
        _hook_msg(str(exc), fg="red")
        ctx.exit(1)

    entries: list[tuple[Path, str, str]] = []  # (path, sha, branch)
    seen_paths: set[str] = set()

    # First, mirror what real git knows by asking the base repository for its
    # worktree list.  This ensures we surface any worktrees created outside of
    # CWM (e.g. plain 'git worktree add' before adoption) so agents get a
    # complete picture.
    base_repo = config.repo_path
    if base_repo is not None and base_repo.exists():
        try:
            infos = gitutil.worktree_list(cwd=base_repo)
        except CWMError:
            infos = []
        for info in infos:
            entries.append((info.path, info.head, info.branch or ""))
            seen_paths.add(str(info.path.resolve(strict=False)))

    # Augment with CWM-managed entries, replacing the workspace path with the
    # agent-facing symlink when one is registered.
    for meta in manager.list_worktrees():
        ws_path = config.worktree_ws_path(meta.branch)
        checkout = ws_path / "src" / meta.repo_name
        sha = meta.base_sha
        if checkout.exists():
            try:
                sha = gitutil.get_head_sha(cwd=checkout)
            except CWMError:
                pass
        display_path = (
            Path(meta.agent_symlinks[0]) if meta.agent_symlinks else ws_path
        )
        # Drop the duplicate entry git worktree list emitted for this checkout
        # so the agent does not see two rows for the same branch.
        checkout_resolved = str(checkout.resolve(strict=False))
        entries = [
            (p, s, b)
            for (p, s, b) in entries
            if str(p.resolve(strict=False)) != checkout_resolved
        ]
        entries.append((display_path, sha, meta.branch))

    if porcelain:
        for path, sha, branch in entries:
            click.echo(f"worktree {path}")
            if sha:
                click.echo(f"HEAD {sha}")
            if branch:
                click.echo(f"branch refs/heads/{branch}")
            click.echo("")
    else:
        for path, sha, branch in entries:
            short_sha = sha[:7] if sha else ""
            branch_label = f"[{branch}]" if branch else "(detached HEAD)"
            click.echo(f"{path}\t{short_sha}\t{branch_label}")


def _hook_remove(ctx: click.Context, rest: list[str]) -> None:
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("positional", nargs="*")
    try:
        parsed = parser.parse_args(rest)
    except (argparse.ArgumentError, SystemExit):
        _hook_msg(
            "Could not parse 'git worktree remove' arguments. "
            "Use 'cwm worktree remove <branch>' instead.",
            fg="yellow",
        )
        ctx.exit(1)

    if not parsed.positional:
        _hook_msg("'git worktree remove' requires a <path> argument.", fg="yellow")
        ctx.exit(1)

    target = Path(os.path.abspath(parsed.positional[0]))
    config, manager = _load()

    target_resolved = target.resolve(strict=False)
    branch: str | None = None
    for meta in manager.list_worktrees():
        if str(target) in meta.agent_symlinks:
            branch = meta.branch
            break
        ws_resolved = config.worktree_ws_path(meta.branch).resolve(strict=False)
        if ws_resolved == target_resolved:
            branch = meta.branch
            break

    if branch is None:
        _hook_msg(
            f"No CWM worktree found for path: {target}. "
            "Use 'cwm worktree list' to inspect managed worktrees.",
            fg="yellow",
        )
        ctx.exit(1)

    try:
        manager.remove_worktree(branch, force=parsed.force)
    except CWMError as exc:
        _hook_msg(str(exc), fg="red")
        ctx.exit(1)

    _hook_msg(f"Removed worktree '{branch}' (was at {target})", fg="green")


def _hook_prune(ctx: click.Context, rest: list[str]) -> None:
    _config, manager = _load()
    try:
        pruned = manager.prune_stale()
    except CWMError as exc:
        _hook_msg(str(exc), fg="red")
        ctx.exit(1)
    _hook_msg(f"Pruned {len(pruned)} stale worktree(s).", fg="green")
    for branch in pruned:
        _hook_msg(f"  - {branch}", fg="cyan")


@worktree.command(
    "__git_hook",
    hidden=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def git_hook(ctx: click.Context) -> None:
    """Internal: handle 'git worktree ...' calls intercepted by the shell/PATH wrapper."""
    args = ctx.args
    if not args:
        _hook_unsupported(ctx, "(no subcommand)")

    subcmd, rest = args[0], list(args[1:])
    if subcmd == "add":
        _hook_add(ctx, rest)
    elif subcmd == "list":
        _hook_list(ctx, rest)
    elif subcmd == "remove":
        _hook_remove(ctx, rest)
    elif subcmd == "prune":
        _hook_prune(ctx, rest)
    else:
        _hook_unsupported(ctx, subcmd)


@worktree.command("prune")
@click.option("--force", is_flag=True, help="Remove stale metadata without confirmation.")
def prune(force: bool) -> None:
    """Remove metadata for worktrees whose workspace directory no longer exists.

    Also runs 'git worktree prune' to clean up stale git worktree entries.
    """
    try:
        config, manager = _load()
        metas = manager.list_worktrees()
        stale_branches = [m.branch for m in metas if not config.worktree_ws_path(m.branch).exists()]

        if not stale_branches:
            click.echo("No stale worktrees found.")
            return

        click.echo("Stale worktrees (workspace directory missing):")
        for branch in stale_branches:
            click.echo(f"  {branch}")
        click.echo()

        if not force:
            click.confirm("Remove stale metadata?", abort=True)

        pruned = manager.prune_stale(stale_branches)
        for branch in pruned:
            click.echo(f"  Pruned: {branch}")
        click.echo(f"Pruned {len(pruned)} stale worktree(s).")
    except CWMError as exc:
        raise click.ClickException(str(exc)) from exc
