"""validate_canvas_capability — is a feature/symbol supported by the SDK?"""

from __future__ import annotations

import difflib
from typing import Any

from ..evidence import envelope, error_envelope
from ..reference import UnsupportedSDKVersion, load

# data_models first so a bare resource name (e.g. "obs"/"Observation") resolves
# to the data model rather than a same-named effect class.
_CATALOG_KINDS = ("handler_base_classes", "data_models", "effects", "events")
TOOL = "validate_canvas_capability"


def _normalize(s: str) -> str:
    return s.strip().lstrip(".").split("(")[0].strip()


def validate_canvas_capability(feature_or_symbol: str, sdk_version: str | None = None) -> dict[str, Any]:
    """Look up ``feature_or_symbol`` in the capability catalog for ``sdk_version``.

    Returns SUPPORTED / UNSUPPORTED / WORKAROUND with the matching symbol and
    doc_ref.  Resolves common aliases (e.g. ``Protocol`` -> ``BaseProtocol``,
    ``obs`` -> ``Observation``) before searching the four catalogs.
    """
    try:
        bucket, catalog = load(sdk_version, "capability_catalog.json")
    except UnsupportedSDKVersion as e:
        return error_envelope(
            tool=TOOL, error="unsupported_sdk_version",
            requested=e.requested, supported=e.supported,
        )

    query = _normalize(feature_or_symbol)
    aliases = catalog.get("aliases", {})
    key = aliases.get(query, query)

    # Search each catalog by key, then by trailing symbol segment.
    for kind in _CATALOG_KINDS:
        entries: dict[str, Any] = catalog.get(kind, {})
        entry = entries.get(key)
        if entry is None:
            # match on the leaf of a dotted symbol the user might paste
            for ek, ev in entries.items():
                sym = ev.get("symbol", "")
                if sym.rsplit(".", 1)[-1] == key or sym == key:
                    entry, key = ev, ek
                    break
        if entry is not None:
            return envelope(
                tool=TOOL, sdk_version=bucket, ok=True,
                result=entry.get("status", "SUPPORTED"),
                findings=[],
                checked={"query": feature_or_symbol, "matched_kind": kind, "matched_key": key},
                symbol=entry.get("symbol"),
                doc_ref=entry.get("doc_ref"),
                replacement=entry.get("replacement"),
                note=entry.get("note"),
            )

    # Not found anywhere -> UNSUPPORTED, with offline fuzzy suggestions.
    all_keys: list[str] = []
    for kind in _CATALOG_KINDS:
        all_keys.extend(catalog.get(kind, {}).keys())
    suggestions = difflib.get_close_matches(key, all_keys, n=5, cutoff=0.6)
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=True, result="UNSUPPORTED",
        findings=[],
        checked={"query": feature_or_symbol, "matched_kind": None},
        reason="not_in_catalog",
        suggestions=suggestions,
    )
