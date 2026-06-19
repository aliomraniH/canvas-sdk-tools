"""Shared evidence / response-envelope helpers.

Every tool returns the same envelope, and every finding is evidence-bearing:
a location (file/line or JSON path), a symbol or rule id, and a doc_ref.
No finding is ever a bare assertion.
"""

from __future__ import annotations

from typing import Any


def finding(
    *,
    message: str,
    rule: str,
    doc_ref: str | None = None,
    line: int | None = None,
    col: int | None = None,
    path: str | None = None,
    severity: str = "error",
    **extra: Any,
) -> dict[str, Any]:
    """Build one evidence-bearing finding."""
    f: dict[str, Any] = {"message": message, "rule": rule, "severity": severity}
    if doc_ref is not None:
        f["doc_ref"] = doc_ref
    if line is not None:
        f["line"] = line
    if col is not None:
        f["col"] = col
    if path is not None:
        f["path"] = path
    f.update(extra)
    return f


def envelope(
    *,
    tool: str,
    result: str,
    sdk_version: str | None = None,
    ok: bool = True,
    findings: list[dict[str, Any]] | None = None,
    checked: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build the common tool response envelope."""
    env: dict[str, Any] = {
        "tool": tool,
        "result": result,
        "ok": ok,
        "findings": findings or [],
    }
    if sdk_version is not None:
        env["sdk_version"] = sdk_version
    if checked is not None:
        env["checked"] = checked
    env.update(extra)
    return env


def error_envelope(*, tool: str, error: str, **extra: Any) -> dict[str, Any]:
    """Build a structured error envelope (e.g. unsupported sdk_version)."""
    env: dict[str, Any] = {"tool": tool, "ok": False, "error": error, "findings": []}
    env.update(extra)
    return env
