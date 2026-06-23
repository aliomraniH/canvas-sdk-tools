"""lint_canvas_field_names — AST checks for known Canvas field-name traps.

Rules come from field_name_rules.json: attribute renames (obs.units -> obs.unit,
.lb is not a field), kwarg renames (dbid__in -> id__in), required pragmas
(from __future__ import annotations), and access patterns (subscripting
underscore keys -> .get(), and unguarded Model.objects.get(...) -> guard with
try/except Model.DoesNotExist).
"""

from __future__ import annotations

import ast
from typing import Any

from ..diff import extract_source
from ..evidence import envelope, error_envelope, finding
from ..reference import UnsupportedSDKVersion, load

TOOL = "lint_canvas_field_names"


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _receiver_matches(receiver: str, applies_to: list[str]) -> bool:
    # An empty applies_to means the rule is not scoped to a receiver (match any).
    if not applies_to:
        return True
    low = receiver.lower()
    return any(tok.lower() in low for tok in applies_to)


def _kwarg_matches(name: str, rule: dict) -> bool:
    if name == rule.get("wrong"):
        return True
    family = rule.get("family")
    return bool(family) and (name == family or name.startswith(f"{family}__"))


def _is_objects_get_call(node: ast.AST) -> bool:
    """True for `<...>.objects.get(...)` calls (the unguarded-lookup trap)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _dotted(node.func.value).endswith("objects")
    )


def _handler_guards_dne(handler: ast.ExceptHandler) -> bool:
    """True if an except clause catches DoesNotExist (or everything)."""
    if handler.type is None:  # bare `except:` catches DoesNotExist too
        return True
    for n in ast.walk(handler.type):
        name = ""
        if isinstance(n, ast.Attribute):
            name = n.attr
        elif isinstance(n, ast.Name):
            name = n.id
        if name.endswith("DoesNotExist") or name in ("Exception", "BaseException"):
            return True
    return False


def _guarded_get_calls(tree: ast.AST) -> set[int]:
    """ids of `.objects.get(...)` calls wrapped in a try/except DoesNotExist."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(_handler_guards_dne(h) for h in node.handlers):
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if _is_objects_get_call(sub):
                        guarded.add(id(sub))
    return guarded


def lint_canvas_field_names(code: str, sdk_version: str | None = None) -> dict[str, Any]:
    """Scan code (or a diff's added lines) for Canvas field-name traps."""
    try:
        bucket, rules = load(sdk_version, "field_name_rules.json")
    except UnsupportedSDKVersion as e:
        return error_envelope(
            tool=TOOL, error="unsupported_sdk_version",
            requested=e.requested, supported=e.supported,
        )

    source = extract_source(code)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return envelope(
            tool=TOOL, sdk_version=bucket, ok=True, result="SKIPPED",
            findings=[], checked={"parsed": False, "reason": f"syntax_error: {e.msg}"},
        )

    findings: list[dict[str, Any]] = []
    attr_rules = rules.get("attribute_renames", [])
    kwarg_rules = rules.get("kwarg_renames", [])
    value_rules = rules.get("value_literals", [])
    pragma_rules = rules.get("required_pragmas", [])
    access_rules = rules.get("access_patterns", [])
    unguarded_rule = next(
        (a for a in access_rules if a.get("pattern") == "unguarded_objects_get"), None
    )
    guarded_gets = _guarded_get_calls(tree)

    # required pragmas: must be the first statement of the module.
    for pr in pragma_rules:
        if pr.get("scope") == "module":
            first = tree.body[0] if tree.body else None
            ok = (
                isinstance(first, ast.ImportFrom)
                and first.module == "__future__"
                and any(a.name == "annotations" for a in first.names)
            )
            if not ok:
                findings.append(
                    finding(
                        message=pr["message"], rule_id=pr["id"], rule="field.required_pragma",
                        doc_ref=pr.get("doc_ref"), line=1,
                        suggested=pr["require"],
                    )
                )

    for node in ast.walk(tree):
        # attribute renames: obs.unit -> obs.units
        if isinstance(node, ast.Attribute):
            for r in attr_rules:
                if node.attr == r["wrong"] and _receiver_matches(_dotted(node.value), r.get("applies_to", [])):
                    findings.append(
                        finding(
                            message=r["message"], rule_id=r["id"], rule="field.attribute_rename",
                            doc_ref=r.get("doc_ref"), line=node.lineno, col=node.col_offset,
                            found=r["wrong"], suggested=r["right"],
                        )
                    )

        # unguarded ORM lookup: Model.objects.get(...) without try/except DoesNotExist
        if unguarded_rule and _is_objects_get_call(node) and id(node) not in guarded_gets:
            findings.append(
                finding(
                    message=unguarded_rule["message"], rule_id=unguarded_rule["id"],
                    rule="field.access_pattern", doc_ref=unguarded_rule.get("doc_ref"),
                    line=node.lineno, col=node.col_offset,
                    found=".objects.get(...)", suggested=unguarded_rule["right"],
                )
            )

        # kwarg renames + value literals (keyword form: units="lbs")
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                r = next((kr for kr in kwarg_rules if _kwarg_matches(kw.arg, kr)), None)
                if r is not None:
                    findings.append(
                        finding(
                            message=r["message"], rule_id=r["id"], rule="field.kwarg_rename",
                            doc_ref=r.get("doc_ref"), line=kw.value.lineno, col=kw.value.col_offset,
                            found=kw.arg, suggested=r["right"],
                        )
                    )
                for vr in value_rules:
                    if (
                        kw.arg == vr.get("field")
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value == vr["wrong"]
                    ):
                        findings.append(_value_finding(vr, kw.value))

        # value literals (assignment form: x.units = "lbs")
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for tgt in node.targets:
                if isinstance(tgt, ast.Attribute):
                    for vr in value_rules:
                        if tgt.attr == vr.get("field") and node.value.value == vr["wrong"]:
                            findings.append(_value_finding(vr, node.value))

        # access patterns: d["_id"] -> d.get("_id")
        if isinstance(node, ast.Subscript) and access_rules:
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value.startswith("_"):
                ar = next((a for a in access_rules if a.get("pattern") == "subscript_on_underscore_key"), None)
                if ar:
                    findings.append(
                        finding(
                            message=ar["message"], rule_id=ar["id"], rule="field.access_pattern",
                            doc_ref=ar.get("doc_ref"), line=node.lineno, col=node.col_offset,
                            found=f'["{key.value}"]', suggested=ar["right"],
                        )
                    )

    result = "CLEAN" if not findings else "ISSUES"
    return envelope(
        tool=TOOL, sdk_version=bucket, ok=(not findings), result=result,
        findings=findings, checked={"parsed": True},
    )


def _value_finding(vr: dict, value_node: ast.Constant) -> dict:
    return finding(
        message=vr["message"], rule_id=vr["id"], rule="field.value_literal",
        doc_ref=vr.get("doc_ref"), line=value_node.lineno, col=value_node.col_offset,
        found=vr["wrong"], suggested=vr["right"],
    )
