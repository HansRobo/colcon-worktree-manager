"""CWM project configuration stored in .cwm/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from cwm.errors import ConfigNotFoundError

CONFIG_DIR = ".cwm"
CONFIG_FILE = "config.yaml"
WORKTREES_META_DIR = "worktrees"
CACHE_DIR = "cache"

CONFIG_VERSION = 1


@dataclass
class BaseWorkspaceConfig:
    """Configuration for the base (underlay) workspace."""

    path: str = "base_ws"
    branch: str = "main"
    symlink_install: bool = True


@dataclass
class Config:
    """Top-level CWM configuration."""

    version: int = CONFIG_VERSION
    underlay: str = ""
    base_ws: BaseWorkspaceConfig = field(default_factory=BaseWorkspaceConfig)
    worktrees_dir: str = "worktrees"
    mode: str = "single"  # "single" or "meta"

    # Runtime-only (not serialised)
    project_root: Path = field(default=Path("."), repr=False)

    @property
    def is_meta(self) -> bool:
        """Return True if this is a meta-repository workspace."""
        return self.mode == "meta"

    # -- Serialisation ---------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a plain dict (excluding runtime fields)."""
        d: dict = {
            "version": self.version,
            "underlay": self.underlay,
            "base_ws": {
                "path": self.base_ws.path,
                "branch": self.base_ws.branch,
                "symlink_install": self.base_ws.symlink_install,
            },
            "worktrees_dir": self.worktrees_dir,
        }
        if self.mode != "single":
            d["mode"] = self.mode
        return d

    @classmethod
    def from_dict(cls, data: dict, project_root: Path) -> Config:
        """Deserialise from a plain dict."""
        bw = data.get("base_ws", {})
        return cls(
            version=data.get("version", CONFIG_VERSION),
            underlay=data.get("underlay", "/opt/ros/jazzy"),
            base_ws=BaseWorkspaceConfig(
                path=bw.get("path", "base_ws"),
                branch=bw.get("branch", "main"),
                symlink_install=bw.get("symlink_install", True),
            ),
            worktrees_dir=data.get("worktrees_dir", "worktrees"),
            mode=data.get("mode", "single"),
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
        return cls.from_dict(data, project_root)

    # -- Derived paths ---------------------------------------------------------

    @property
    def cwm_dir(self) -> Path:
        return self.project_root / CONFIG_DIR

    @property
    def base_ws_path(self) -> Path:
        return self.project_root / self.base_ws.path

    @property
    def base_src_path(self) -> Path:
        return self.base_ws_path / "src"

    @property
    def base_install_path(self) -> Path:
        return self.base_ws_path / "install"

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
