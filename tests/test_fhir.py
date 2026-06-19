from __future__ import annotations

from canvas_sdk_tools.tools import check_fhir_immutability

from .conftest import SDK_VERSION, read_fixture


def test_forbidden_mutations_flagged():
    out = check_fhir_immutability(read_fixture("bad", "fhir_mutation.py"), SDK_VERSION)
    assert out["result"] == "VIOLATIONS"
    interactions = sorted(f["interaction"] for f in out["findings"])
    assert interactions == ["delete", "patch", "update"]  # put -> update
    assert all(f["resource"] == "Observation" for f in out["findings"])


def test_clean_code_passes():
    out = check_fhir_immutability(read_fixture("good", "handler_clean.py"), SDK_VERSION)
    assert out["result"] == "IMMUTABLE_OK"
    assert out["findings"] == []


def test_read_and_create_allowed():
    code = (
        "import requests\n"
        "requests.get('https://x/Observation/1')\n"
        "requests.post('https://x/Observation', json={})\n"
    )
    assert check_fhir_immutability(code, SDK_VERSION)["result"] == "IMMUTABLE_OK"


def test_diff_input_added_lines_only():
    diff = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,3 @@\n"
        " import requests\n"
        "+requests.delete('https://x/Observation/9')\n"
        " other = 1\n"
    )
    out = check_fhir_immutability(diff, SDK_VERSION)
    assert out["result"] == "VIOLATIONS"
    assert out["findings"][0]["interaction"] == "delete"
