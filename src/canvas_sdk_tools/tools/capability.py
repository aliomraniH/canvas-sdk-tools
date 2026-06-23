"""validate_canvas_capability — is a feature/symbol supported by the SDK?"""

from __future__ import annotations

import difflib
from typing import Any

from ..evidence import envelope, error_envelope
from ..reference import UnsupportedSDKVersion, load

# data_models early so a bare resource name (e.g. "obs"/"Observation") resolves
# to the data model rather than a same-named effect class.
_CATALOG_KINDS = (
    "handler_base_classes",
    "data_models",
    "commands",
    "effects",
    "events",
    "functions",
)
# Generic path segments that should not drive fuzzy suggestions on their own.
_GENERIC_SEGMENTS = {
    "canvas_sdk", "effects", "events", "commands", "data", "utils",
    "handlers", "http", "base", "v1",
}
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
    # Users may paste a fully dotted symbol (canvas_sdk.effects.banner_alert.
    # AddBannerAlert). The catalog is keyed by short names, and a symbol's own
    # module path can differ from the pasted one, so match on the leaf name too.
    leaf = key.rsplit(".", 1)[-1]

    # Search each catalog by key, by leaf, then by trailing symbol segment.
    for kind in _CATALOG_KINDS:
        entries: dict[str, Any] = catalog.get(kind, {})
        if key in entries:
            entry, matched_key = entries[key], key
        elif leaf in entries:
            entry, matched_key = entries[leaf], leaf
        else:
            entry, matched_key = None, None
            for ek, ev in entries.items():
                sym = ev.get("symbol", "")
                if sym == key or sym.rsplit(".", 1)[-1] == leaf:
                    entry, matched_key = ev, ek
                    break
        if entry is not None:
            return envelope(
                tool=TOOL, sdk_version=bucket, ok=True,
                result=entry.get("status", "SUPPORTED"),
                findings=[],
                checked={"query": feature_or_symbol, "matched_kind": kind, "matched_key": matched_key},
                symbol=entry.get("symbol"),
                doc_ref=entry.get("doc_ref"),
                replacement=entry.get("replacement"),
                note=entry.get("note"),
            )

    # Not found anywhere -> UNSUPPORTED, with offline fuzzy suggestions.
    all_keys: list[str] = []
    for kind in _CATALOG_KINDS:
        all_keys.extend(catalog.get(kind, {}).keys())
    suggestions = difflib.get_close_matches(leaf, all_keys, n=5, cutoff=0.6)
    if not suggestions:
        # fall back to matching distinctive path segments against catalog symbols
        segs = {
            s.lower() for s in key.split(".")
            if len(s) > 3 and s.lower() not in _GENERIC_SEGMENTS
        }
        if segs:
            hits: list[str] = []
            for kind in _CATALOG_KINDS:
                for ek, ev in catalog.get(kind, {}).items():
                    sym = ev.get("symbol", "").lower()
                    if any(seg in sym for seg in segs) and ek not in hits:
                        hits.append(ek)
            suggestions = hits[:5]
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=True, result="UNSUPPORTED",
        findings=[],
        checked={"query": feature_or_symbol, "matched_kind": None},
        reason="not_in_catalog",
        suggestions=suggestions,
    )
