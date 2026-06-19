"""check_sandbox_imports — report what the real Canvas sandbox would reject.

Highest-fidelity check: the code is compiled with RestrictedPython's
``compile_restricted_exec`` (compile only — never executed) using a policy that
mirrors the real plugin_runner import allow-list.  RestrictedPython itself also
rejects leading-underscore names, dunder writes, and other constructs, so those
surface too.  import_allowlist.json is the backstop / message enricher.
"""

from __future__ import annotations

import re
from typing import Any

from RestrictedPython import RestrictingNodeTransformer, compile_restricted_exec

from ..evidence import envelope, error_envelope, finding
from ..reference import UnsupportedSDKVersion, load

TOOL = "check_sandbox_imports"

# Set per-call before compiling (the policy class reads it).  Single-process,
# per-request assignment keeps this faithful without persistent state.
_ALLOWED: dict[str, set[str]] = {}

_LINE_RE = re.compile(r"Line (\d+):")


class _CanvasImportPolicy(RestrictingNodeTransformer):
    """RestrictingNodeTransformer that enforces the Canvas module allow-list."""

    def visit_Import(self, node):  # noqa: N802 (ast visitor name)
        for alias in node.names:
            top = alias.name
            if top not in _ALLOWED and top.split(".")[0] not in _ALLOWED:
                self.error(node, f'"{top}" is not an allowed import (not in ALLOWED_MODULES)')
        return self.node_contents_visit(node)

    def visit_ImportFrom(self, node):  # noqa: N802
        mod = node.module or ""
        if mod not in _ALLOWED:
            self.error(node, f'"{mod}" is not an allowed import (not in ALLOWED_MODULES)')
        else:
            allowed_names = _ALLOWED[mod]
            if "*" not in allowed_names:
                for alias in node.names:
                    if alias.name == "*":
                        self.error(node, f'star import "from {mod} import *" is not allowed')
                    elif alias.name not in allowed_names:
                        self.error(node, f'"{mod}.{alias.name}" is not an allowed import name')
        return self.node_contents_visit(node)


def _build_allowed(allowlist: dict[str, Any]) -> dict[str, set[str]]:
    allowed: dict[str, set[str]] = {}
    for mod, names in allowlist.get("allowed_modules", {}).items():
        allowed[mod] = set(names)
    return allowed


def _classify(msg: str) -> str:
    low = msg.lower()
    if "not in allowed_modules" in low or "not an allowed import" in low:
        return "not_in_allowlist"
    if "underscore" in low or msg.strip().startswith('"_') or "_ " in low:
        return "leading_underscore"
    if "star import" in low or "import *" in low:
        return "star_import"
    if "__" in msg:
        return "dunder"
    return "restricted_python"


def check_sandbox_imports(code: str, sdk_version: str | None = None) -> dict[str, Any]:
    """Compile ``code`` under the sandbox policy and report rejections."""
    global _ALLOWED
    try:
        bucket, allowlist = load(sdk_version, "import_allowlist.json")
    except UnsupportedSDKVersion as e:
        return error_envelope(
            tool=TOOL, error="unsupported_sdk_version",
            requested=e.requested, supported=e.supported,
        )

    _ALLOWED = _build_allowed(allowlist)
    result_tuple = compile_restricted_exec(code, filename="<submitted>", policy=_CanvasImportPolicy)

    findings: list[dict[str, Any]] = []
    for err in result_tuple.errors:
        m = _LINE_RE.search(err)
        line = int(m.group(1)) if m else None
        findings.append(
            finding(
                message=err,
                rule=_classify(err),
                doc_ref="sdk/sandbox",
                line=line,
            )
        )

    accepted = result_tuple.code is not None and not findings
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=accepted,
        result="ACCEPTED" if accepted else "REJECTED",
        findings=findings,
        checked={"engine": "RestrictedPython.compile_restricted_exec", "executed": False},
        warnings_from_engine=list(result_tuple.warnings or []),
    )
