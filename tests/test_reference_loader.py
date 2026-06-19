from __future__ import annotations

import pytest

from canvas_sdk_tools.reference import (
    REFERENCE_FILES,
    UnsupportedSDKVersion,
    list_supported_versions,
    load,
    resolve_bucket,
)

from .conftest import SDK_VERSION


def test_bucket_present():
    assert SDK_VERSION in list_supported_versions()


@pytest.mark.parametrize("spec", ["0.169.x", "0.169", "0.169.1", "v0.169.1"])
def test_version_normalization(spec):
    assert resolve_bucket(spec) == "sdk_0.169.x"


def test_unknown_version_raises():
    with pytest.raises(UnsupportedSDKVersion):
        resolve_bucket("0.1.x")


def test_all_reference_files_load():
    for filename in REFERENCE_FILES:
        bucket, data = load(SDK_VERSION, filename)
        assert bucket == SDK_VERSION
        assert "_meta" in data


def test_none_uses_newest():
    assert resolve_bucket(None) == "sdk_0.169.x"
