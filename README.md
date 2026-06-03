# Colcon Worktree Manager (CWM)

A CLI tool that integrates `git worktree` with `colcon` for parallel ROS 2 development. CWM automates overlay workspace management, enabling developers to work on multiple branches simultaneously without full rebuilds or environment variable conflicts.

## Features

- **Smart diff-based builds** - Automatically detects changed packages via `git diff` and builds only what's needed
- **ABI-safe reverse dependency resolution** - Rebuilds affected packages via `build`/`build_export` dependencies to prevent ODR violations and runtime crashes; runtime-only (`exec`) dependents are skipped
- **Environment isolation** - Activates per-worktree environment (ROS overlays, `AMENT_PREFIX_PATH`) via `cwm activate` / `cwm deactivate`
- **Optimised colcon arguments** - Generates `--packages-select` and `--allow-overriding` flags automatically

## Installation

```bash
uv tool install .
# or
pip install .
```

## Quick Start

### Shell integration (one-time setup)

Add the following line to `~/.bashrc` (or `~/.zshrc`) so that `cwm activate` and `cwm deactivate` can mutate the current shell environment:

```bash
eval "$(cwm shell-init)"
```

Without shell integration you can still activate a worktree with the long form:

```bash
source <(cwm activate <branch>)
deactivate
```

### Adopting an existing workspace

If you already have a colcon workspace (e.g. `~/ws/ibis_ws` with `src/autoware.universe/` cloned):

```bash
cd ~/ws/ibis_ws
cwm init                           # ROS 2 underlay auto-detected; repo auto-selected if unique
cwm worktree add feature-perception
cwm activate feature-perception
cwm ws build
cwm deactivate
```

If multiple repositories are in `src/`, select which one to track:

```bash
cwm repo switch autoware.universe
cwm worktree add feature-perception
```

### Starting fresh

```bash
mkdir my_ws && cd my_ws
cwm init                           # creates .cwm/ and worktrees/ only
mkdir src
git clone <your-repo> src/my_repo
cwm repo switch my_repo            # track this repository
colcon build --symlink-install
cwm worktree add feature-perception
cwm activate feature-perception
cwm ws build
cwm deactivate
```

## Commands

### Shell / setup

| Command | Description |
|---------|-------------|
| `cwm init [--underlay PATH] [--repo PATH]` | Initialise a CWM project (underlay auto-detected; repo auto-selected if `src/` has a single git repo) |
| `cwm activate [branch]` | Activate a worktree environment (interactive menu when branch is omitted) |
| `cwm deactivate` | Restore the previous environment (provided by shell integration) |
| `cwm switch <branch>` | Activate a worktree **and** navigate to it in one step |
| `cwm cd [branch\|repo\|base]` | Jump to a worktree root or repository checkout via shell integration |
| `cwm shell-init` | Print the shell integration function — add `eval "$(cwm shell-init)"` to `.bashrc` |

### Repository management

| Command | Description |
|---------|-------------|
| `cwm repo show` | Show the currently tracked git repository |
| `cwm repo switch <path>` | Change the tracked repository (relative to `src/`) |

### Workspace operations

| Command | Description |
|---------|-------------|
| `cwm ws build [--dry-run] [--no-rdeps]` | Build changed packages + their ABI reverse deps (`build`/`build_export`; `exec`-only excluded) in the active worktree |
| `cwm ws test [-w BRANCH] [--dry-run] [--no-rdeps]` | Run `colcon test` on changed packages + their ABI reverse deps (underlay+overlay sourced) |
| `cwm ws test-result [-w BRANCH]` | Show the test summary; exits non-zero if any test failed (`--return-code-on-test-failure`) |
| `cwm ws clean [--all]` | Clean build artifacts |
| `cwm ws status [--json]` | Show the state of the base workspace and all worktrees |

### Worktree management

| Command | Description |
|---------|-------------|
| `cwm worktree add <branch>` | Create a new overlay worktree for the tracked repository |
| `cwm worktree remove <branch> [--force] [--delete-branch]` | Remove a worktree and its artifacts; also syncs `git worktree` state |
| `cwm worktree list` | List all managed worktrees |
| `cwm worktree prune [--force]` | Remove stale worktree state and run `git worktree prune` |

Several commands accept `--json` for machine-readable output: `cwm ws status`, `cwm worktree add`, `cwm worktree remove`, and `cwm worktree list`.

### Inspection / tooling

| Command | Description |
|---------|-------------|
| `cwm inspect env <branch>` | Show environment variables and setup script paths for a worktree (JSON) |
| `cwm inspect detect [--cwd PATH]` | Detect whether the directory is inside a CWM project (outputs JSON) |

### Base workspace

| Command | Description |
|---------|-------------|
| `cwm base update [-- <colcon args>]` | Pull the tracked repository and rebuild the base workspace |
| `cwm base build [-- <colcon args>]` | Rebuild the base workspace without pulling |
| `cwm base clean [--yes]` | Remove the base build artifacts (build/, install/, log/) |
| `cwm base status [--json]` | Show whether the base is built and dirty |
| `cwm base doctor [--fix] [--json]` | Detect (and with `--fix` delete) stale build dirs pointing at missing sources |

`base update` and `base build` source the ROS 2 underlay
(`underlay` in `.cwm/config.yaml`, e.g. `/opt/ros/jazzy`) before invoking
colcon, symmetric with the worktree build path. Extra arguments after `--` are
forwarded to `colcon build` (e.g. `cwm base build -- --continue-on-error`).

`base clean` removes the shared base install that every worktree overlays as
its underlay, so all worktrees will need rebuilding afterwards (it prompts for
confirmation unless `--yes` is given). `cwm ws clean --base` is deprecated in
favour of `cwm base clean`.

`base doctor` reads each `build/<pkg>/CMakeCache.txt` and flags build
directories whose source no longer exists (e.g. a moved or deleted package),
which otherwise surface as `CMake Error`s on the next build; `--fix` deletes
only those directories.

### AI agent integration

CWM intercepts `git worktree` invocations inside a CWM project so that AI
coding agents (or any tool that defaults to raw `git` knowledge) can drive the
overlay workflow without breaking the `<branch>_ws/src/<repo>` layout. The
interception is two-tiered:

1. **Shell function** — `eval "$(cwm shell-init)"` installs a `git()` function
   that intercepts `git worktree …` whenever the current directory (or an
   ancestor) contains `.cwm/`. Activation is *not* required.
2. **PATH shim** — `cwm activate <branch>` prepends `<project>/.cwm/bin` to
   `PATH`. The `git` script there forwards `worktree` subcommands to CWM and
   delegates everything else to the real `git`. This catches `git` calls made
   from subprocesses (Python `subprocess`, `bash -c …`) that bypass the shell
   function.

For an agent, `git worktree add -b feature-x ../feature-x` then transparently
creates `worktrees/feature-x_ws/`, drops a symlink at `../feature-x`, and
prints the next step (`source <(cwm activate feature-x)`) to stderr. Both the
symlink and the real workspace are valid working paths.

| Subcommand | Behaviour |
|---|---|
| `git worktree add [-b] <path> [<branch>]` | Creates the CWM workspace and a symlink at `<path>`. Recognised flags (`-f`, `--detach`, `--lock`, `--orphan`, …) are accepted but the CWM layout is always produced. |
| `git worktree list [--porcelain]` | Lists CWM-managed worktrees in `git worktree list` format. |
| `git worktree remove <path>` | Resolves `<path>` (symlink or real workspace) back to a branch and runs `cwm worktree remove`. |
| `git worktree prune` | Forwards to `cwm worktree prune`. |
| `lock` / `unlock` / `move` / `repair` | Refused with a pointer to `cwm worktree --help`. |

The symlink path is recorded in the worktree metadata and removed automatically
by `cwm worktree remove`.

### Concurrency / locking

All worktree lifecycle operations (`add`, `remove`, `prune`, and the agent
`git worktree` interceptions) are serialized project-wide via a POSIX `flock`
on `.cwm/lock`. Concurrent `cwm worktree add` invocations run one after another,
preventing corruption of `.git/worktrees` and the per-branch metadata. This is
an intentional Linux/ROS 2 trade-off: build and test operations are deliberately
*not* locked, so parallel builds across worktrees remain fully concurrent.

### colcon passthrough

After activation, `cwm` acts as a drop-in replacement for `colcon`. Any flags
not recognised by `cwm ws build` are forwarded to colcon, and any colcon verb not
defined by cwm is run verbatim in the active worktree workspace:

```bash
cwm activate feature-perception

# Smart diff-based build; extra flags forwarded to colcon
cwm ws build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# Run tests, list packages, inspect the graph — any colcon verb works
cwm test --packages-select my_pkg
cwm list
cwm graph
```

## Architecture

CWM consists of three core modules:

1. **Colcon Discovery Controller (CDC)** - Detects changed packages via git diff and controls colcon's package discovery
2. **Dependency Graph Analyzer (DGA)** - Parses `package.xml` files to build a DAG and computes ABI reverse dependencies (`build_depends`/`build_export_depends`; `exec_depends` are runtime-only and excluded)
3. **Worktree State Manager (WSM)** - Manages git worktree lifecycle and environment isolation

### Directory Structure

CWM treats the workspace root itself as the base workspace — matching standard colcon conventions.
Each worktree contains a checkout of the single tracked repository under `src/<repo-name>/`:

```
my_ws/                      # project root = base colcon workspace
├── .cwm/                   # CWM metadata and config
│   ├── config.yaml         # underlay, tracked repo, worktrees_dir
│   └── worktrees/          # per-branch metadata YAML files
├── src/
│   └── autoware.universe/  # the single tracked git repository
├── build/
├── install/
├── log/
└── worktrees/              # overlay worktrees (created by cwm worktree add)
    └── feature-X_ws/
        ├── src/
        │   └── autoware.universe/  # git worktree checkout
        ├── build/
        ├── install/
        └── log/
```

## Shell Completion

`cwm` supports tab completion for subcommands, worktree branch names, and ROS 2 underlay paths.

**Bash** — add to `~/.bashrc`:

```bash
eval "$(_CWM_COMPLETE=bash_source cwm)"
```

**Zsh** — add to `~/.zshrc`:

```zsh
eval "$(_CWM_COMPLETE=zsh_source cwm)"
```

**Fish** — save to `~/.config/fish/completions/cwm.fish`:

```fish
_CWM_COMPLETE=fish_source cwm | source
```

For faster shell startup, generate the completion script once:

```bash
_CWM_COMPLETE=bash_source cwm > ~/.cwm-complete.bash
# then in ~/.bashrc:
source ~/.cwm-complete.bash
```

| Argument / Option | Completion |
|---|---|
| `cwm worktree add BRANCH` | Local and remote git branch names from the tracked repo |
| `cwm worktree remove BRANCH` | Existing CWM worktree names |
| `cwm activate BRANCH` | Existing CWM worktree names |
| `cwm init --underlay` | Detected ROS 2 distro paths (`/opt/ros/*`) |

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run python -m pytest tests/ -v
```

## License

Apache License 2.0
