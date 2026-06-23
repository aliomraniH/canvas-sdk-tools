from __future__ import annotations

from canvas_sdk_tools.reference import load
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


def test_effect_full_dotted_path_supported():
    # The pasted module path (banner_alert) differs from the real one
    # (add_banner_alert); leaf matching must still resolve it.
    out = validate_canvas_capability(
        "canvas_sdk.effects.banner_alert.AddBannerAlert", SDK_VERSION
    )
    assert out["result"] == "SUPPORTED"
    assert out["symbol"] == "canvas_sdk.effects.add_banner_alert.AddBannerAlert"


def test_command_supported():
    out = validate_canvas_capability("canvas_sdk.commands.GoalCommand", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert out["symbol"] == "canvas_sdk.commands.GoalCommand"


def test_util_http_supported():
    out = validate_canvas_capability("canvas_sdk.utils.http.Http", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert "Http" in out["symbol"]


def test_data_model_full_path_supported():
    out = validate_canvas_capability("canvas_sdk.v1.data.Patient", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert out["symbol"] == "canvas_sdk.v1.data.Patient"


def test_handler_full_path_supported():
    out = validate_canvas_capability("canvas_sdk.handlers.BaseHandler", SDK_VERSION)
    assert out["result"] == "SUPPORTED"
    assert "BaseHandler" in out["symbol"]


def test_fake_dotted_symbol_unsupported_with_suggestions():
    out = validate_canvas_capability(
        "canvas_sdk.effects.banner_alert.NotARealThing", SDK_VERSION
    )
    assert out["result"] == "UNSUPPORTED"
    assert out["reason"] == "not_in_catalog"
    assert len(out["suggestions"]) > 0


def test_catalog_is_comprehensive():
    _, catalog = load(SDK_VERSION, "capability_catalog.json")
    kinds = (
        "handler_base_classes", "data_models", "commands",
        "effects", "events", "functions",
    )
    total = sum(len(catalog.get(k, {})) for k in kinds)
    assert total > 1500
    assert "GoalCommand" in catalog["commands"]
    assert "Http" in catalog["functions"]
