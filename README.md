# Colcon Worktree Manager (CWM)

A CLI tool that integrates `git worktree` with `colcon` for parallel ROS 2 development. CWM automates overlay workspace management, enabling developers to work on multiple branches simultaneously without full rebuilds or environment variable conflicts.

## Features

- **Smart diff-based builds** - Automatically detects changed packages via `git diff` and builds only what's needed
- **ABI-safe reverse dependency resolution** - Computes and rebuilds affected packages to prevent ODR violations and runtime crashes
- **Environment isolation** - Activates per-worktree environment (ROS overlays, `AMENT_PREFIX_PATH`) via `cwm activate` / `deactivate`
- **Optimised colcon arguments** - Generates `--packages-select` and `--allow-overriding` flags automatically

## Installation

```bash
uv tool install .
# or
pip install .
```

## Quick Start

### Adopting an existing workspace

If you already have a colcon workspace (e.g. `~/ws/ibis_ws` with `src/` populated):

```bash
cd ~/ws/ibis_ws
cwm init          # ROS 2 underlay is auto-detected
cwm worktree add feature-perception
source <(cwm activate feature-perception)
cwm build
deactivate
```

### Starting fresh

```bash
mkdir my_ws && cd my_ws
cwm init          # creates .cwm/ and worktrees/ only
mkdir src
git clone <your-repo> src/
colcon build --symlink-install
cwm worktree add feature-perception
source <(cwm activate feature-perception)
cwm build
deactivate
```

## Commands

| Command | Description |
|---------|-------------|
| `cwm init [--underlay PATH]` | Initialise a CWM project (underlay auto-detected from `/opt/ros/`) |
| `cwm base update` | Pull and rebuild the base workspace |
| `cwm worktree add <branch>` | Create a new overlay worktree |
| `cwm worktree rm <branch>` | Remove a worktree and its artifacts |
| `cwm worktree list` | List all managed worktrees |
| `source <(cwm activate [branch])` | Activate a worktree environment (or interactive menu) |
| `deactivate` | Restore the previous environment |
| `cwm build [--dry-run] [--no-rdeps]` | Build changed packages + reverse deps |
| `cwm clean [--all]` | Clean build artifacts |

## Architecture

CWM consists of three core modules:

1. **Colcon Discovery Controller (CDC)** - Detects changed packages via git diff and controls colcon's package discovery
2. **Dependency Graph Analyzer (DGA)** - Parses `package.xml` files to build a DAG and computes reverse dependencies
3. **Worktree State Manager (WSM)** - Manages git worktree lifecycle and environment isolation

### Directory Structure

CWM treats the workspace root itself as the base workspace — matching standard colcon conventions:

```
my_ws/                 # project root = base colcon workspace
├── .cwm/              # CWM metadata and config
├── src/               # base source tree (existing or cloned by you)
├── build/
├── install/
├── log/
└── worktrees/         # overlay worktrees (created by cwm worktree add)
    └── feature-X_ws/
        ├── src/       # git worktree checkouts
        ├── build/
        ├── install/
        └── log/
```

## Shell Completion

`cwm` supports tab completion for subcommands, worktree branch names, sub-repository paths, and ROS 2 underlay paths.

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

What gets completed:

| Argument / Option | Completion |
|---|---|
| `cwm worktree add BRANCH` | Local and remote git branch names |
| `cwm worktree rm BRANCH` | Existing CWM worktree names |
| `cwm worktree focus BRANCH` | Existing CWM worktree names |
| `cwm worktree add --repos` | Sub-repository paths under `src/` |
| `cwm worktree focus --add` | Sub-repository paths under `src/` |
| `cwm worktree focus --rm` | Sub-repositories active in the worktree |
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
