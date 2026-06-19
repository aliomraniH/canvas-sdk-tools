from __future__ import annotations

from canvas_sdk_tools.tools import validate_canvas_capability

from .conftest import SDK_VERSION


def test_known_data_model_supported():
    out = validate_canvas_capability("Observation", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert out["symbol"] == "canvas_sdk.v1.data.Observation"


def test_handler_base_class_supported():
    out = validate_canvas_capability("BaseHandler", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert "BaseHandler" in out["symbol"]


def test_alias_resolves_to_data_model():
    out = validate_canvas_capability("obs", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert out["symbol"] == "canvas_sdk.v1.data.Observation"


def test_legacy_protocol_is_workaround():
    out = validate_canvas_capability("BaseProtocol", SDK_VERSION)
    assert out["result"] == "WORKAROUND"
    assert out["replacement"] == "BaseHandler"


def test_unknown_symbol_unsupported_with_suggestions():
    out = validate_canvas_capability("FooBarWidgetThatDoesNotExist", SDK_VERSION)
    assert out["result"] == "UNSUPPORTED"
    assert out["reason"] == "not_in_catalog"
    assert isinstance(out["suggestions"], list)


def test_unsupported_version_errors():
    out = validate_canvas_capability("Observation", "9.9.x")
    assert out["ok"] is False
    assert out["error"] == "unsupported_sdk_version"
    assert "0.169.x" in out["supported"]
