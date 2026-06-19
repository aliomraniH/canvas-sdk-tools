"""check_fhir_immutability — flag forbidden FHIR mutations via AST scan.

Canonical trap: any PATCH / PUT / DELETE on an Observation.  Resource rules and
detection patterns come from fhir_rules.json.  Static call-site detection only;
the tool never calls a Canvas instance.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from ..diff import extract_source
from ..evidence import envelope, error_envelope, finding
from ..reference import UnsupportedSDKVersion, load

TOOL = "check_fhir_immutability"


def _string_args(call: ast.Call) -> list[str]:
    """Collect literal string content from positional args (incl. f-string parts)."""
    out: list[str] = []
    for a in call.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            out.append(a.value)
        elif isinstance(a, ast.JoinedStr):
            parts = [v.value for v in a.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            out.append("".join(parts))
    return out


def _resource_from_strings(strings: list[str], resources: dict, url_re: re.Pattern) -> str | None:
    for s in strings:
        # exact resource name as an argument, e.g. fhir.delete("Observation", id)
        if s in resources:
            return s
        m = url_re.search(s)
        if m and m.group(1) in resources:
            return m.group(1)
    return None


def check_fhir_immutability(code_or_diff: str, sdk_version: str | None = None) -> dict[str, Any]:
    """Scan code (or a unified diff's added lines) for forbidden FHIR writes."""
    try:
        bucket, rules = load(sdk_version, "fhir_rules.json")
    except UnsupportedSDKVersion as e:
        return error_envelope(
            tool=TOOL, error="unsupported_sdk_version",
            requested=e.requested, supported=e.supported,
        )

    resources: dict[str, Any] = rules.get("resources", {})
    interaction_map: dict[str, str] = rules.get("interaction_map", {})
    det = rules.get("detection", {})
    http_methods = set(det.get("http_methods", ["put", "patch", "delete"]))
    orm_mutators = set(det.get("orm_mutators", ["save", "update", "delete"]))
    url_re = re.compile(det.get("url_resource_regex", r"/([A-Z][A-Za-z]+)(?:/[^/\"']+)?/?$"))

    source = extract_source(code_or_diff)
    findings: list[dict[str, Any]] = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return envelope(
            tool=TOOL, sdk_version=bucket, ok=True, result="SKIPPED",
            findings=[], checked={"parsed": False, "reason": f"syntax_error: {e.msg}"},
            limits="Input did not parse as a complete Python module; no static scan performed.",
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        strings = _string_args(node)
        resource = _resource_from_strings(strings, resources, url_re)

        # Path 1: HTTP-client style (requests.delete(url), session.patch(url), ...)
        if method in http_methods:
            interaction = interaction_map.get(method, method)
            if resource and interaction in resources[resource].get("forbidden", []):
                findings.append(_make_finding(node, resource, interaction, method, resources))
                continue

        # Path 2: ORM / FHIR-client mutator (fhir.delete("Observation", id), obj.update(...))
        if method in orm_mutators:
            interaction = interaction_map.get(method, method)
            # only flag when we can attribute a concrete forbidden resource
            if resource and interaction in resources[resource].get("forbidden", []):
                findings.append(_make_finding(node, resource, interaction, method, resources))

    result = "IMMUTABLE_OK" if not findings else "VIOLATIONS"
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=(not findings), result=result,
        findings=findings,
        checked={"parsed": True, "resources_enforced": sorted(resources)},
        limits="Static call-site detection; dynamically-named methods or "
               "indirected URLs may not be caught. Never validates by calling live.",
    )


def _make_finding(node: ast.Call, resource: str, interaction: str, method: str, resources: dict) -> dict:
    return finding(
        message=f"Forbidden FHIR {interaction.upper()} on immutable resource {resource} "
                f"(call `.{method}(...)`). {resources[resource].get('rationale', '')}".strip(),
        rule=f"fhir.{resource}.forbidden",
        doc_ref=resources[resource].get("doc_ref"),
        line=node.lineno, col=node.col_offset,
        resource=resource, interaction=interaction, method=method,
    )
