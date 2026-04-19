"""CWM project configuration stored in .cwm/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from cwm.errors import ConfigNotFoundError, ConfigVersionError

CONFIG_DIR = ".cwm"
CONFIG_FILE = "config.yaml"
WORKTREES_META_DIR = "worktrees"
CACHE_DIR = "cache"
COLCON_IGNORE = "COLCON_IGNORE"

CONFIG_VERSION = 3


@dataclass
class Config:
    """Top-level CWM configuration."""

    version: int = CONFIG_VERSION
    underlay: str = ""
    symlink_install: bool = True
    worktrees_dir: str = "worktrees"
    repo: str | None = None  # relative path under src/ of the tracked git repo

    # Runtime-only (not serialised)
    project_root: Path = field(default=Path("."), repr=False)

    # -- Serialisation ---------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a plain dict (excluding runtime fields)."""
        d: dict = {
            "version": self.version,
            "underlay": self.underlay,
            "symlink_install": self.symlink_install,
            "worktrees_dir": self.worktrees_dir,
        }
        if self.repo is not None:
            d["repo"] = self.repo
        return d

    @classmethod
    def from_dict(cls, data: dict, project_root: Path) -> Config:
        """Deserialise from a plain dict."""
        return cls(
            version=data.get("version", CONFIG_VERSION),
            underlay=data.get("underlay", "/opt/ros/jazzy"),
            symlink_install=data.get("symlink_install", True),
            worktrees_dir=data.get("worktrees_dir", "worktrees"),
            repo=data.get("repo") or None,
            project_root=project_root,
        )

    # -- Persistence -----------------------------------------------------------

    def save(self) -> None:
        """Write the config to .cwm/config.yaml."""
        config_path = self.project_root / CONFIG_DIR / CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as fh:
            yaml.safe_dump(self.to_dict(), fh, default_flow_style=False)

    @classmethod
    def load(cls, project_root: Path) -> Config:
        """Load configuration from *project_root*/.cwm/config.yaml."""
        config_path = project_root / CONFIG_DIR / CONFIG_FILE
        if not config_path.exists():
            raise ConfigNotFoundError(f"Config not found: {config_path}")
        with open(config_path) as fh:
            data = yaml.safe_load(fh) or {}

        version = data.get("version", 1)
        if version < CONFIG_VERSION:
            raise ConfigVersionError(
                f"CWM config at {config_path} uses version {version} (current: {CONFIG_VERSION}).\n"
                "The config schema has changed: a single tracked repository is now required.\n"
                "Please re-initialise with: cwm init"
            )

        return cls.from_dict(data, project_root)

    # -- Derived paths ---------------------------------------------------------

    @property
    def cwm_dir(self) -> Path:
        return self.project_root / CONFIG_DIR

    @property
    def repo_name(self) -> str:
        """Basename of the tracked repository path (e.g. 'autoware.universe')."""
        return Path(self.repo).name if self.repo else ""

    @property
    def repo_path(self) -> Path | None:
        """Absolute path to the tracked git repository, or None if not selected."""
        if self.repo is None:
            return None
        return self.base_src_path / self.repo

    @property
    def base_src_path(self) -> Path:
        return self.project_root / "src"

    @property
    def base_install_path(self) -> Path:
        return self.project_root / "install"

    @property
    def worktrees_path(self) -> Path:
        return self.project_root / self.worktrees_dir

    @staticmethod
    def safe_branch_name(branch: str) -> str:
        """Sanitise a branch name for use as a directory/file name."""
        return branch.replace("/", "-")

    def worktree_ws_path(self, branch: str) -> Path:
        """Return the workspace root for a given branch worktree."""
        return self.worktrees_path / f"{self.safe_branch_name(branch)}_ws"

    def worktree_src_path(self, branch: str) -> Path:
        return self.worktree_ws_path(branch) / "src"

    def worktree_install_path(self, branch: str) -> Path:
        return self.worktree_ws_path(branch) / "install"

    def worktree_meta_path(self, branch: str) -> Path:
        return self.cwm_dir / WORKTREES_META_DIR / f"{self.safe_branch_name(branch)}.yaml"

    @property
    def cache_path(self) -> Path:
        return self.cwm_dir / CACHE_DIR

    def ensure_worktrees_ignore_marker(self) -> None:
        self.worktrees_path.mkdir(parents=True, exist_ok=True)
        (self.worktrees_path / COLCON_IGNORE).touch()
