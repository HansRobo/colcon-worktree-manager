"""Shared test fixtures."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Minimal git identity for subprocess calls in tests
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "t@t.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "t@t.com",
}


def make_git_repo(path: Path, branch: str = "main") -> None:
    """Initialise a bare git repo with one empty commit at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True, env=GIT_ENV)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=path, check=True, capture_output=True, env=GIT_ENV)


def make_package_xml(name: str, deps: list[str] | None = None, *, dep_xml: str | None = None) -> str:
    """Render a minimal ``package.xml``.

    Pass *deps* for the common ``<depend>`` case, or *dep_xml* to supply a
    pre-rendered dependency block (e.g. mixed build/exec/export tags).
    """
    if dep_xml is None:
        dep_xml = "\n".join(f"  <depend>{d}</depend>" for d in (deps or []))
    return f"""<?xml version="1.0"?>
<package format="3">
  <name>{name}</name>
  <version>0.0.0</version>
  <description>Test package</description>
  <maintainer email="test@test.com">test</maintainer>
  <license>Apache-2.0</license>
{dep_xml}
  <export>
    <build_type>ament_cmake</build_type>
  </export>
</package>
"""


def write_package(
    src: Path, name: str, deps: list[str] | None = None, *, dep_xml: str | None = None
) -> Path:
    """Create (or overwrite) ``src/<name>/package.xml`` and return its directory."""
    pkg_dir = src / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "package.xml").write_text(make_package_xml(name, deps, dep_xml=dep_xml))
    return pkg_dir


@pytest.fixture
def sample_ws(tmp_path: Path) -> Path:
    """Create a minimal ROS 2 workspace layout with known dependencies.

    Dependency graph:
        core_lib  <--  perception_node
        core_lib  <--  control_node
        msgs      <--  perception_node
        msgs      <--  control_node
        perception_node  (leaf)
        control_node     (leaf)
        standalone       (no deps, no dependants)
    """
    pkgs = {
        "core_lib": {
            "deps": [],
        },
        "msgs": {
            "deps": [],
        },
        "perception_node": {
            "deps": ["core_lib", "msgs"],
        },
        "control_node": {
            "deps": ["core_lib", "msgs"],
        },
        "standalone": {
            "deps": [],
        },
    }

    src = tmp_path / "src"
    for name, info in pkgs.items():
        write_package(src, name, info["deps"])

    return tmp_path


@pytest.fixture
def mixed_deps_ws(tmp_path: Path) -> Path:
    """Workspace exercising each dependency category for ABI-edge tests.

    Only build/build_export dependencies are ABI-relevant; exec-only edges
    are dropped from the graph:
        lib_abi      <--  abi_consumer     (build_depend)
        lib_abi      <--  shared_consumer  (depend = build + exec + export)
        lib_abi      <--  export_consumer  (build_export_depend)
        lib_runtime  <--  exec_consumer    (exec_depend -- ABI-irrelevant)
    """
    # name -> {package.xml dependency tag -> [dependency names]}
    pkgs: dict[str, dict[str, list[str]]] = {
        "lib_abi": {},
        "lib_runtime": {},
        "abi_consumer": {"build_depend": ["lib_abi"]},
        "exec_consumer": {"exec_depend": ["lib_runtime"]},
        "shared_consumer": {"depend": ["lib_abi"]},
        "export_consumer": {"build_export_depend": ["lib_abi"]},
    }

    src = tmp_path / "src"
    for name, deps_by_tag in pkgs.items():
        dep_xml = "\n".join(
            f"  <{tag}>{dep}</{tag}>"
            for tag, deps in deps_by_tag.items()
            for dep in deps
        )
        write_package(src, name, dep_xml=dep_xml)

    return tmp_path
