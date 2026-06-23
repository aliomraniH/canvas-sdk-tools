from __future__ import annotations

from canvas_sdk_tools.tools import lint_canvas_field_names

from .conftest import SDK_VERSION, read_fixture


def test_traps_detected():
    # Input A: pragma present, but dbid__in / .units / .lb / unguarded .get all fire.
    out = lint_canvas_field_names(read_fixture("bad", "field_traps.py"), SDK_VERSION)
    assert out["result"] == "ISSUES"
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert rule_ids == {"dbid-in", "obs-units", "weight-lb", "unguarded-get"}


def test_clean_code_passes():
    out = lint_canvas_field_names(read_fixture("good", "handler_clean.py"), SDK_VERSION)
    assert out["result"] == "CLEAN"
    assert out["findings"] == []


def test_missing_future_annotations_flagged():
    # Input B: no pragma + a .units access -> exactly two findings.
    out = lint_canvas_field_names("obs.units\n", SDK_VERSION)
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert rule_ids == {"future-annotations", "obs-units"}


def test_present_future_annotations_ok():
    out = lint_canvas_field_names("from __future__ import annotations\nx = 1\n", SDK_VERSION)
    rule_ids = {f.get("rule_id") for f in out["findings"]}
    assert "future-annotations" not in rule_ids


def test_guarded_objects_get_is_clean():
    code = (
        "from __future__ import annotations\n"
        "try:\n"
        "    obj = Patient.objects.get(id=pid)\n"
        "except Patient.DoesNotExist:\n"
        "    obj = None\n"
    )
    out = lint_canvas_field_names(code, SDK_VERSION)
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert "unguarded-get" not in rule_ids


def test_dbid_family_lookups_flagged():
    code = (
        "from __future__ import annotations\n"
        "a = Model.objects.filter(dbid=5)\n"
        "b = Model.objects.filter(dbid__gt=10)\n"
    )
    out = lint_canvas_field_names(code, SDK_VERSION)
    dbid_findings = [f for f in out["findings"] if f["rule_id"] == "dbid-in"]
    assert len(dbid_findings) == 2


def test_units_as_dict_key_or_string_not_flagged():
    code = (
        "from __future__ import annotations\n"
        'config = {"units": "metric"}\n'
        'label = config["units"]\n'
        'name = "units"\n'
    )
    out = lint_canvas_field_names(code, SDK_VERSION)
    rule_ids = {f["rule_id"] for f in out["findings"]}
    assert "obs-units" not in rule_ids
    assert out["result"] == "CLEAN"
