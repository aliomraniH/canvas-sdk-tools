#!/usr/bin/env python3
"""Generate reference/sdk_<ver>/ from a canvas-plugins checkout.

Dev/build-time only.  The running service never invokes this; it only reads the
JSON this produces.  Machine-extractable files (capability_catalog,
import_allowlist, manifest_schema) are derived directly from the pinned checkout;
the curated knowledge files (fhir_rules, field_name_rules) are emitted from the
version-stamped constants below, sourced from Canvas docs.

Usage:
    python scripts/regenerate_reference.py \
        --checkout /path/to/canvas-plugins \
        --tag 0.169.1 --version 0.169.x \
        --out reference
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

DOC_BASE = "https://docs.canvasmedical.com/"
ENUM_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*\d+\s*;")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _meta(version: str, tag: str) -> dict[str, Any]:
    return {
        "sdk_version": version,
        "generated_from": f"canvas-medical/canvas-plugins@{tag}",
        "generated_at": dt.date.today().isoformat(),
        "doc_base": DOC_BASE + "sdk/",
    }


def _proto_enum_names(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENUM_LINE.match(line)
        if m:
            names.append(m.group(1))
    # dedupe, keep order
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _module_all(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in ("__all__", "__exports__"):
                    return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []


def _class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.name for n in tree.body if isinstance(n, ast.ClassDef)]


def _extract_dict_of_str_sets(source: str, varname: str) -> dict[str, list[str]]:
    """Extract `VARNAME = {"mod": {"a","b"}, ...}` as {mod: [names]}."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == varname for t in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            out: dict[str, list[str]] = {}
            for k, v in zip(node.value.keys, node.value.values, strict=False):
                assert isinstance(k, ast.Constant)
                key = k.value
                if isinstance(v, ast.Set):
                    out[key] = sorted(e.value for e in v.elts if isinstance(e, ast.Constant))
                elif isinstance(v, ast.Call):  # set()
                    out[key] = []
                else:
                    out[key] = []
            return out
    raise SystemExit(f"could not find {varname} in sandbox.py")


def _literal_assign(source: str, varname: str) -> Any:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == varname for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit(f"could not find {varname}")


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #
def build_capability_catalog(ck: Path, meta: dict) -> dict[str, Any]:
    events_proto = ck / "protobufs/canvas_generated/messages/events.proto"
    effects_proto = ck / "protobufs/canvas_generated/messages/effects.proto"
    data_init = ck / "canvas_sdk/v1/data/__init__.py"
    handlers_dir = ck / "canvas_sdk/handlers"

    events = {
        name: {"symbol": f"EventType.{name}", "status": "SUPPORTED", "doc_ref": "sdk/events/"}
        for name in _proto_enum_names(events_proto)
        if name != "UNKNOWN"
    }
    effects = {
        name: {"symbol": f"EffectType.{name}", "status": "SUPPORTED", "doc_ref": "sdk/effects/"}
        for name in _proto_enum_names(effects_proto)
        if name != "UNKNOWN_EFFECT"
    }
    # add python effect classes as capabilities too
    for py in sorted((ck / "canvas_sdk/effects").rglob("*.py")):
        if py.name == "__init__.py":
            continue
        for cls in _class_names(py):
            effects.setdefault(
                cls,
                {"symbol": f"canvas_sdk.effects.{py.stem}.{cls}", "status": "SUPPORTED",
                 "doc_ref": "sdk/effects/"},
            )

    data_models = {
        name: {"symbol": f"canvas_sdk.v1.data.{name}", "status": "SUPPORTED",
               "doc_ref": "sdk/data/"}
        for name in _module_all(data_init)
    }

    handler_base_classes: dict[str, Any] = {}
    for py in sorted(handlers_dir.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        rel = py.relative_to(ck / "canvas_sdk").with_suffix("")
        dotted = "canvas_sdk." + ".".join(rel.parts)
        for cls in _class_names(py):
            handler_base_classes.setdefault(
                cls, {"symbol": f"{dotted}.{cls}", "status": "SUPPORTED", "doc_ref": "sdk/handlers/"}
            )
    # legacy alias retained as a workaround pointer
    handler_base_classes.setdefault(
        "BaseProtocol",
        {"symbol": "canvas_sdk.protocols.BaseProtocol", "status": "WORKAROUND",
         "replacement": "BaseHandler", "note": "legacy alias; use BaseHandler",
         "doc_ref": "sdk/handlers/"},
    )

    return {
        "_meta": meta,
        "handler_base_classes": handler_base_classes,
        "events": events,
        "effects": effects,
        "data_models": data_models,
        "aliases": {"Protocol": "BaseProtocol", "obs": "Observation"},
    }


def build_import_allowlist(ck: Path, meta: dict) -> dict[str, Any]:
    sandbox_src = (ck / "plugin_runner/sandbox.py").read_text(encoding="utf-8")
    std = _extract_dict_of_str_sets(sandbox_src, "STANDARD_LIBRARY_MODULES")
    third = _extract_dict_of_str_sets(sandbox_src, "THIRD_PARTY_MODULES")
    canvas = json.loads((ck / "plugin_runner/allowed-module-imports.json").read_text("utf-8"))
    canvas = {k: sorted(v) for k, v in canvas.items()}

    allowed: dict[str, list[str]] = {}
    for d in (std, third, canvas):
        for mod, names in d.items():
            allowed.setdefault(mod, [])
            allowed[mod] = sorted(set(allowed[mod]) | set(names))

    return {
        "_meta": meta,
        "allowed_modules": dict(sorted(allowed.items())),
        "name_rules": {
            "no_leading_underscore": True,
            "no_dunder_assignment_except": ["__all__"],
            "no_star_import_from_unlisted": True,
        },
        "note": "Mirrors plugin_runner ALLOWED_MODULES (STANDARD_LIBRARY + THIRD_PARTY "
                "+ allowed-module-imports.json). The live tool also runs RestrictedPython.",
    }


def build_manifest_schema(ck: Path, meta: dict) -> dict[str, Any]:
    src = (ck / "canvas_cli/utils/validators/manifest_schema.py").read_text(encoding="utf-8")
    schema = _literal_assign(src, "manifest_schema")
    schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    schema.setdefault("title", "CANVAS_MANIFEST.json")
    schema["_meta"] = meta
    return schema


def build_fhir_rules(meta: dict) -> dict[str, Any]:
    return {
        "_meta": meta,
        "resources": {
            "Observation": {
                "allowed": ["create", "read", "search"],
                "forbidden": ["update", "patch", "delete"],
                "rationale": "Observations are immutable clinical records; "
                             "corrections are recorded as new Observations.",
                "doc_ref": "api/observation/",
            },
            "DiagnosticReport": {
                "allowed": ["create", "read", "search"],
                "forbidden": ["update", "patch", "delete"],
                "rationale": "Diagnostic reports are immutable once created.",
                "doc_ref": "api/diagnosticreport/",
            },
        },
        "interaction_map": {
            "put": "update", "patch": "patch", "delete": "delete",
            "post": "create", "get": "read", "update": "update", "save": "update",
        },
        "detection": {
            "http_methods": ["put", "patch", "delete"],
            "orm_mutators": ["save", "update", "delete"],
            "url_resource_regex": r"/([A-Z][A-Za-z]+)(?:/[^/\"']+)?/?$",
            "note": "Static call-site signals only.",
        },
    }


def build_field_name_rules(meta: dict) -> dict[str, Any]:
    return {
        "_meta": meta,
        "attribute_renames": [
            {"id": "obs-units", "wrong": "unit", "right": "units",
             "applies_to": ["Observation", "obs"],
             "message": "Observation uses `.units` (plural), not `.unit`.",
             "doc_ref": "sdk/data/"},
        ],
        "kwarg_renames": [
            {"id": "dbid-in", "wrong": "id__in", "right": "dbid__in",
             "message": "Filter on `dbid__in`, not `id__in`.", "doc_ref": "sdk/data/"},
        ],
        "value_literals": [
            {"id": "weight-unit", "field": "units", "wrong": "lbs", "right": "lb",
             "message": "Weight unit literal is `lb`, not `lbs`.", "doc_ref": "sdk/data/"},
        ],
        "required_pragmas": [
            {"id": "future-annotations", "require": "from __future__ import annotations",
             "scope": "module",
             "message": "Canvas plugin modules must start with "
                        "`from __future__ import annotations`.",
             "doc_ref": "sdk/"},
        ],
        "access_patterns": [
            {"id": "underscore-get", "pattern": "subscript_on_underscore_key",
             "right": ".get()",
             "message": "Use `.get('_key')` for underscore-prefixed keys; "
                        "subscripting underscore keys is rejected by the sandbox.",
             "doc_ref": "sdk/"},
        ],
    }


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkout", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--version", required=True, help="bucket label, e.g. 0.169.x")
    ap.add_argument("--out", default="reference", type=Path)
    args = ap.parse_args()

    ck = args.checkout
    meta = _meta(args.version, args.tag)
    out_dir = args.out / f"sdk_{args.version}"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "capability_catalog.json": build_capability_catalog(ck, meta),
        "import_allowlist.json": build_import_allowlist(ck, meta),
        "manifest_schema.json": build_manifest_schema(ck, meta),
        "fhir_rules.json": build_fhir_rules(meta),
        "field_name_rules.json": build_field_name_rules(meta),
    }
    for name, data in files.items():
        (out_dir / name).write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", "utf-8")
        print(f"wrote {out_dir / name}")

    (out_dir / "VERSION").write_text(args.tag + "\n", "utf-8")
    (out_dir / "PROVENANCE.md").write_text(
        f"# Provenance — sdk_{args.version}\n\n"
        f"- Source: `canvas-medical/canvas-plugins@{args.tag}`\n"
        f"- Generated: {meta['generated_at']}\n"
        f"- Generator: `scripts/regenerate_reference.py`\n\n"
        "Machine-extracted: capability_catalog.json, import_allowlist.json, "
        "manifest_schema.json (from canvas_cli manifest_schema).\n"
        "Curated (Canvas docs): fhir_rules.json, field_name_rules.json.\n\n"
        "## Regenerate\n```\n"
        f"git clone --depth 1 --branch {args.tag} "
        "https://github.com/canvas-medical/canvas-plugins.git /tmp/canvas-plugins\n"
        f"python scripts/regenerate_reference.py --checkout /tmp/canvas-plugins "
        f"--tag {args.tag} --version {args.version}\n```\n",
        "utf-8",
    )
    print(f"wrote {out_dir / 'VERSION'} and PROVENANCE.md")


if __name__ == "__main__":
    main()
