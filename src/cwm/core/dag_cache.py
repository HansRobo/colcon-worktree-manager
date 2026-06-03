"""On-disk cache for the package dependency graph.

Scanning a workspace means parsing every ``package.xml`` with catkin_pkg, which
is costly on large (autoware-scale) workspaces. This module fingerprints the
set of ``package.xml`` files by content hash and caches the serialised graph
under ``.cwm/cache/dag/<fingerprint>.json``, so a second scan of an unchanged
tree skips the XML parse entirely.

A cache miss (absent / stale / corrupt entry) is a normal, silent outcome:
callers fall back to rebuilding from source.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from cwm.core.dependency_graph import DependencyGraphAnalyzer, iter_package_xmls

# Bump when the on-disk JSON layout changes; old entries are then ignored.
CACHE_FORMAT_VERSION = 1

_logger = logging.getLogger("cwm")


def compute_fingerprint(src_path: Path) -> str:
    """Return a content hash of every ``package.xml`` under *src_path*.

    Uses :func:`iter_package_xmls`, so it walks exactly the files graph
    construction does. Each file contributes its *relative path* and the
    sha256 of its bytes, so adding, removing, renaming, or editing any
    ``package.xml`` changes the fingerprint.
    """
    digest = hashlib.sha256()
    for pkg_xml, rel in iter_package_xmls(src_path):
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(pkg_xml.read_bytes()).digest())
    return digest.hexdigest()


def _cache_file(cache_dir: Path, fingerprint: str) -> Path:
    return cache_dir / f"{fingerprint}.json"


def load_cached_graph(
    cache_dir: Path, src_path: Path, fingerprint: str
) -> DependencyGraphAnalyzer | None:
    """Load the cached graph for *fingerprint*, or ``None`` on any cache miss.

    Returns ``None`` (caller rebuilds) when the entry is absent, uses a
    different format version, has a mismatched fingerprint, or is corrupt.
    """
    path = _cache_file(cache_dir, fingerprint)
    try:
        data = json.loads(path.read_text())
        if data["cache_format_version"] != CACHE_FORMAT_VERSION:
            return None
        if data["fingerprint"] != fingerprint:
            return None
        return DependencyGraphAnalyzer.from_dict(data, src_path)
    except FileNotFoundError:
        return None  # absent entry is a normal cache miss
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
        _logger.debug("Ignoring unreadable DAG cache %s: %s", path, exc)
        return None


def store_cached_graph(
    cache_dir: Path, fingerprint: str, graph: DependencyGraphAnalyzer, src_path: Path
) -> None:
    """Atomically write *graph* to the cache. Best-effort: failures are ignored.

    Package paths are stored relative to *src_path* so the cache is portable
    across worktrees that hold the same packages at different absolute roots.
    """
    try:
        payload = {
            "cache_format_version": CACHE_FORMAT_VERSION,
            "fingerprint": fingerprint,
            **graph.to_dict(src_path),
        }
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = _cache_file(cache_dir, fingerprint)
        tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, target)  # atomic within the same directory
    except OSError as exc:
        _logger.debug("Could not write DAG cache to %s: %s", cache_dir, exc)
