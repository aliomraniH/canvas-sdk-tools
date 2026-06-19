"""Version resolver + cached loader for the vendored reference/ data.

The only state this service holds is read-only, version-pinned reference data
baked into the image.  Buckets live at ``reference/sdk_<major.minor>.x/``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# reference/ sits at the repo root, two parents up from this file's package dir:
# src/canvas_sdk_tools/reference.py -> src/canvas_sdk_tools -> src -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = _REPO_ROOT / "reference"

_BUCKET_RE = re.compile(r"^sdk_(\d+)\.(\d+)\.x$")
_VER_RE = re.compile(r"^v?(\d+)\.(\d+)")

REFERENCE_FILES = (
    "capability_catalog.json",
    "fhir_rules.json",
    "manifest_schema.json",
    "import_allowlist.json",
    "field_name_rules.json",
)


class UnsupportedSDKVersion(Exception):
    """Raised when a requested sdk_version has no vendored bucket."""

    def __init__(self, requested: str, supported: list[str]):
        self.requested = requested
        self.supported = supported
        super().__init__(f"unsupported sdk_version {requested!r}; supported: {supported}")


def list_supported_versions() -> list[str]:
    """Return the sorted list of vendored buckets, e.g. ['0.169.x']."""
    if not REFERENCE_ROOT.is_dir():
        return []
    out = []
    for child in REFERENCE_ROOT.iterdir():
        m = _BUCKET_RE.match(child.name)
        if child.is_dir() and m:
            out.append(f"{int(m.group(1))}.{int(m.group(2))}.x")
    return sorted(out, key=_version_key)


def _version_key(v: str) -> tuple[int, int]:
    m = _VER_RE.match(v)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def resolve_bucket(sdk_version: str | None) -> str:
    """Normalize an sdk_version string to a vendored bucket name.

    Accepts '0.169.x', '0.169', '0.169.1', 'v0.169.1'.  Never silently falls
    back to a different minor version: a false 'supported' is worse than an
    explicit error.
    """
    supported = list_supported_versions()
    if sdk_version is None:
        # Caller is responsible for passing the configured default; if they pass
        # None we use the newest available bucket.
        if not supported:
            raise UnsupportedSDKVersion("<none>", supported)
        return f"sdk_{supported[-1]}"

    m = _VER_RE.match(sdk_version.strip())
    if not m:
        raise UnsupportedSDKVersion(sdk_version, supported)
    bucket_label = f"{int(m.group(1))}.{int(m.group(2))}.x"
    if bucket_label not in supported:
        raise UnsupportedSDKVersion(sdk_version, supported)
    return f"sdk_{bucket_label}"


@lru_cache(maxsize=64)
def _load_file(bucket: str, filename: str) -> dict[str, Any]:
    path = REFERENCE_ROOT / bucket / filename
    if not path.is_file():
        raise FileNotFoundError(f"missing reference file: {bucket}/{filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def load(sdk_version: str | None, filename: str) -> tuple[str, dict[str, Any]]:
    """Resolve the bucket and load one reference file.

    Returns (bucket_label, data) where bucket_label is like '0.169.x'.
    """
    bucket = resolve_bucket(sdk_version)
    data = _load_file(bucket, filename)
    return bucket.removeprefix("sdk_"), data
