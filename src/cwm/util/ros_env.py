"""ROS 2 environment detection utilities."""

from __future__ import annotations

import os
from pathlib import Path

ROS_INSTALL_BASE = Path("/opt/ros")
_ROLLING = "rolling"


def detect_system_underlay(available: list[str] | None = None) -> str | None:
    """Auto-detect the system ROS 2 underlay path.

    Detection order:
    1. If $ROS_DISTRO is set, check /opt/ros/$ROS_DISTRO
    2. Scan /opt/ros/*/setup.bash; prefer named distros over rolling,
       pick alphabetically last (newest) among named ones.
    3. Fall back to rolling if no named distro found.

    Returns the path string (e.g. "/opt/ros/jazzy") or None.
    Pass *available* (from list_available_distros()) to avoid a redundant scan.
    """
    distro_env = os.environ.get("ROS_DISTRO")
    if distro_env:
        candidate = ROS_INSTALL_BASE / distro_env
        if (candidate / "setup.bash").is_file():
            return str(candidate)

    if available is None:
        available = list_available_distros()
    if not available:
        return None

    named = [d for d in available if Path(d).name != _ROLLING]
    if named:
        return sorted(named)[-1]

    return available[0]  # rolling only


def list_available_distros() -> list[str]:
    """Return paths of all detected ROS 2 installations under /opt/ros/."""
    if not ROS_INSTALL_BASE.is_dir():
        return []
    return sorted(
        str(p.parent)
        for p in ROS_INSTALL_BASE.glob("*/setup.bash")
        if p.is_file()
    )
