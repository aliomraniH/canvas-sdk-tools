"""validate_manifest — jsonschema validation of CANVAS_MANIFEST.json.

The schema is the authoritative one vendored from canvas_cli's manifest_schema
at the pinned tag.  Optionally warns when data_access read/write targets do not
resolve in the capability catalog.
"""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from ..evidence import envelope, error_envelope, finding
from ..reference import UnsupportedSDKVersion, load

TOOL = "validate_manifest"


def _coerce(manifest_json: Any) -> tuple[dict | None, str | None]:
    if isinstance(manifest_json, dict):
        return manifest_json, None
    if isinstance(manifest_json, str):
        try:
            return json.loads(manifest_json), None
        except json.JSONDecodeError as e:
            return None, f"invalid JSON: {e}"
    return None, f"unsupported manifest type: {type(manifest_json).__name__}"


def validate_manifest(manifest_json: Any, sdk_version: str | None = None) -> dict[str, Any]:
    """Validate a CANVAS_MANIFEST.json document against the vendored schema."""
    manifest, parse_err = _coerce(manifest_json)
    if parse_err is not None:
        return error_envelope(tool=TOOL, error="parse_error", detail=parse_err)

    # Prefer the manifest's own sdk_version unless caller overrides.
    effective_version = sdk_version or manifest.get("sdk_version")
    try:
        bucket, schema = load(effective_version, "manifest_schema.json")
    except UnsupportedSDKVersion as e:
        return error_envelope(
            tool=TOOL, error="unsupported_sdk_version",
            requested=e.requested, supported=e.supported,
        )
    schema = {k: v for k, v in schema.items() if k != "_meta"}

    validator = Draft202012Validator(schema)
    findings: list[dict[str, Any]] = []
    for err in sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        findings.append(
            finding(
                message=err.message,
                rule="manifest.schema",
                doc_ref="manifest-schema",
                path=path,
                validator=err.validator,
            )
        )

    # Non-fatal: cross-check data_access targets against the capability catalog.
    warnings = _check_data_access(manifest, effective_version)

    result = "VALID" if not findings else "INVALID"
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=(not findings), result=result,
        findings=findings + warnings,
        checked={"validated_against": "manifest_schema.json"},
    )


def _check_data_access(manifest: dict, sdk_version: str | None) -> list[dict]:
    try:
        _, catalog = load(sdk_version, "capability_catalog.json")
    except UnsupportedSDKVersion:
        return []
    models = catalog.get("data_models", {})
    known = set(models.keys()) | {m.get("symbol") for m in models.values()}

    warnings: list[dict] = []
    components = manifest.get("components", {}) if isinstance(manifest, dict) else {}
    for ckey in ("handlers", "protocols"):
        for i, comp in enumerate(components.get(ckey, []) or []):
            da = comp.get("data_access", {}) if isinstance(comp, dict) else {}
            for access in ("read", "write"):
                for j, target in enumerate(da.get(access, []) or []):
                    # accept "v1.Observation" or "Observation"
                    leaf = str(target).split(".")[-1]
                    if leaf not in known and target not in known:
                        warnings.append(
                            finding(
                                message=f"data_access.{access} target {target!r} not found "
                                        f"in capability catalog data_models.",
                                rule="manifest.data_access.unknown_model",
                                doc_ref="manifest-schema",
                                path=f"components.{ckey}[{i}].data_access.{access}[{j}]",
                                severity="warning",
                            )
                        )
    return warnings
