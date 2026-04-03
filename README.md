# Colcon Worktree Manager (CWM)

A CLI tool that integrates `git worktree` with `colcon` for parallel ROS 2 development. CWM automates overlay workspace management, enabling developers to work on multiple branches simultaneously without full rebuilds or environment variable conflicts.

## Features

- **Smart diff-based builds** - Automatically detects changed packages via `git diff` and builds only what's needed
- **ABI-safe reverse dependency resolution** - Computes and rebuilds affected packages to prevent ODR violations and runtime crashes
- **Environment sandboxing** - Launches isolated subshells per worktree to prevent `AMENT_PREFIX_PATH` pollution
- **Optimised colcon arguments** - Generates `--packages-select` and `--allow-overriding` flags automatically

## Installation

```bash
uv tool install .
# or
pip install .
```

## Quick Start

```bash
# 1. Initialise CWM in your project directory (ROS 2 underlay is auto-detected)
cwm init

# Or specify a custom underlay if needed
# cwm init --underlay /path/to/custom_ws

# 2. Clone your ROS 2 source into base_ws/src/
git clone <your-repo> base_ws/src/

# 3. Build the base workspace
cd base_ws && colcon build --symlink-install && cd ..

# 4. Create a worktree for a feature branch
cwm worktree add feature-perception

# 5. Enter the sandboxed environment
cwm enter feature-perception

# 6. Edit code, then build only changed packages + reverse deps
cwm build

# 7. Exit when done (environment is fully restored)
exit
```

## Commands

| Command | Description |
|---------|-------------|
| `cwm init [--underlay PATH]` | Initialise a CWM project (underlay auto-detected from `/opt/ros/`) |
| `cwm base update` | Pull and rebuild the base workspace |
| `cwm worktree add <branch>` | Create a new overlay worktree |
| `cwm worktree rm <branch>` | Remove a worktree and its artifacts |
| `cwm worktree list` | List all managed worktrees |
| `cwm enter <branch>` | Enter a sandboxed subshell |
| `cwm build [--dry-run] [--no-rdeps]` | Build changed packages + reverse deps |
| `cwm clean [--all]` | Clean build artifacts |

## Architecture

CWM consists of three core modules:

1. **Colcon Discovery Controller (CDC)** - Detects changed packages via git diff and controls colcon's package discovery
2. **Dependency Graph Analyzer (DGA)** - Parses `package.xml` files to build a DAG and computes reverse dependencies
3. **Worktree State Manager (WSM)** - Manages git worktree lifecycle and environment isolation

### Directory Structure

```
project/
├── .cwm/              # CWM metadata and config
├── base_ws/           # Underlay (main branch, full build)
│   ├── src/
│   ├── build/
│   ├── install/
│   └── log/
└── worktrees/         # Overlay worktrees
    └── feature-X_ws/
        ├── src/       # git worktree checkout
        ├── build/
        ├── install/
        └── log/
```

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run python -m pytest tests/ -v
```

## License

Apache License 2.0
