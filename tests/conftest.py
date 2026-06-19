from __future__ import annotations

from pathlib import Path

import pytest

SDK_VERSION = "0.169.x"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


def read_fixture(*parts: str) -> str:
    return (FIXTURES.joinpath(*parts)).read_text(encoding="utf-8")
