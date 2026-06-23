from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from canvas_sdk_tools.app import BearerAuthMiddleware, build_app
from canvas_sdk_tools.config import Settings


def _client() -> TestClient:
    app, _ = build_app(Settings(mcp_auth_token="test-token"))
    return TestClient(app)


def _auth_client() -> TestClient:
    """Minimal app exercising only BearerAuthMiddleware on a /mcp/ route.

    Avoids the real streamable-HTTP MCP handler (which would block waiting on a
    session), so auth acceptance can be asserted deterministically.
    """

    async def ok(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/mcp/", ok, methods=["POST"])])
    app.add_middleware(BearerAuthMiddleware, token="test-token")
    return TestClient(app)


def test_healthz_unauthenticated():
    client = _client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "0.169.x" in body["supported_sdk"]


def test_mcp_requires_bearer():
    client = _client()
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
    assert resp.status_code == 401


def test_mcp_rejects_wrong_token():
    client = _client()
    resp = client.post(
        "/mcp",
        headers={"Authorization": "Bearer wrong"},
        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
    )
    assert resp.status_code == 401


def test_mcp_rejects_wrong_query_token():
    client = _auth_client()
    resp = client.post("/mcp/?token=wrong", json={"x": 1})
    assert resp.status_code == 401


def test_mcp_accepts_query_token():
    client = _auth_client()
    resp = client.post("/mcp/?token=test-token", json={"x": 1})
    assert resp.status_code == 200


def test_mcp_accepts_bearer_header():
    client = _auth_client()
    resp = client.post(
        "/mcp/",
        headers={"Authorization": "Bearer test-token"},
        json={"x": 1},
    )
    assert resp.status_code == 200
