"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
        pkg_dir = src / name
        pkg_dir.mkdir(parents=True)
        dep_xml = "\n".join(
            f"  <depend>{d}</depend>" for d in info["deps"]
        )
        (pkg_dir / "package.xml").write_text(
            f"""<?xml version="1.0"?>
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
        )

    return tmp_path
