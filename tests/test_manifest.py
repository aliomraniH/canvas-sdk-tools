from __future__ import annotations

import json

from canvas_sdk_tools.tools import validate_manifest

from .conftest import SDK_VERSION, read_fixture


def test_valid_manifest():
    out = validate_manifest(read_fixture("good", "manifest_valid.json"))
    assert out["result"] == "VALID"
    errors = [f for f in out["findings"] if f["severity"] == "error"]
    assert errors == []


def test_invalid_manifest():
    out = validate_manifest(read_fixture("bad", "manifest_invalid.json"), SDK_VERSION)
    assert out["result"] == "INVALID"
    paths = {f.get("path") for f in out["findings"]}
    # missing required top-level keys + a handler missing `class`
    assert any("class" in (p or "") for p in paths) or any("<root>" == p for p in paths)


def test_accepts_dict_input():
    manifest = json.loads(read_fixture("good", "manifest_valid.json"))
    assert validate_manifest(manifest)["result"] == "VALID"


def test_bad_json_string():
    out = validate_manifest("{not valid json", SDK_VERSION)
    assert out["ok"] is False
    assert out["error"] == "parse_error"


def test_data_access_unknown_model_warns():
    manifest = json.loads(read_fixture("good", "manifest_valid.json"))
    manifest["components"]["handlers"][0]["data_access"]["read"] = ["NotARealModelXYZ"]
    out = validate_manifest(manifest)
    warns = [f for f in out["findings"] if f["severity"] == "warning"]
    assert any("NotARealModelXYZ" in f["message"] for f in warns)
