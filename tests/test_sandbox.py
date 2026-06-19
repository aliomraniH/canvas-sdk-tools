from __future__ import annotations

from canvas_sdk_tools.tools import check_sandbox_imports

from .conftest import SDK_VERSION, read_fixture


def test_allowed_imports_accepted():
    out = check_sandbox_imports(read_fixture("good", "handler_clean.py"), SDK_VERSION)
    assert out["result"] == "ACCEPTED"
    assert out["findings"] == []


def test_forbidden_imports_rejected():
    out = check_sandbox_imports(read_fixture("bad", "forbidden_imports.py"), SDK_VERSION)
    assert out["result"] == "REJECTED"
    offenders = " ".join(f["message"] for f in out["findings"])
    assert "os" in offenders
    assert "subprocess" in offenders


def test_from_import_disallowed_name():
    out = check_sandbox_imports("from json import loads, JSONDecoder\n", SDK_VERSION)
    # 'loads' is allowed; 'JSONDecoder' is not in the allow-list for json.
    assert out["result"] == "REJECTED"
    assert any("JSONDecoder" in f["message"] for f in out["findings"])


def test_engine_does_not_execute():
    out = check_sandbox_imports("import json\n", SDK_VERSION)
    assert out["checked"]["executed"] is False
