from __future__ import annotations

from canvas_sdk_tools.tools import lint_canvas_field_names

from .conftest import SDK_VERSION, read_fixture


def test_traps_detected():
    out = lint_canvas_field_names(read_fixture("bad", "field_traps.py"), SDK_VERSION)
    assert out["result"] == "ISSUES"
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert {"obs-units", "dbid-in", "weight-unit", "underscore-get", "future-annotations"} <= rule_ids


def test_clean_code_passes():
    out = lint_canvas_field_names(read_fixture("good", "handler_clean.py"), SDK_VERSION)
    assert out["result"] == "CLEAN"
    assert out["findings"] == []


def test_missing_future_annotations_flagged():
    out = lint_canvas_field_names("import json\n", SDK_VERSION)
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert "future-annotations" in rule_ids


def test_present_future_annotations_ok():
    out = lint_canvas_field_names("from __future__ import annotations\nx = 1\n", SDK_VERSION)
    rule_ids = {f.get("rule_id") for f in out["findings"]}
    assert "future-annotations" not in rule_ids
