from __future__ import annotations

from starlette.testclient import TestClient

from canvas_sdk_tools.app import build_app
from canvas_sdk_tools.config import Settings


def _client() -> TestClient:
    app, _ = build_app(Settings(mcp_auth_token="test-token"))
    return TestClient(app)


def test_healthz_unauthenticated():
    with _client() as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "0.169.x" in body["supported_sdk"]


def test_mcp_requires_bearer():
    with _client() as client:
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert resp.status_code == 401


def test_mcp_rejects_wrong_token():
    with _client() as client:
        resp = client.post(
            "/mcp",
            headers={"Authorization": "Bearer wrong"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
        assert resp.status_code == 401
