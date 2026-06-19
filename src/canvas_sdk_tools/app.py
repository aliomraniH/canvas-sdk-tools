"""FastMCP server: bearer auth on /mcp, unauthenticated /healthz, structlog JSON.

Same clean pattern as the memory server.  Registers the five static analyzers.
No Canvas calls, no credentials, no database — entirely offline.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .config import Settings, get_settings
from .logging import configure_logging, get_logger
from .reference import list_supported_versions
from .tools import (
    check_fhir_immutability,
    check_sandbox_imports,
    lint_canvas_field_names,
    validate_canvas_capability,
    validate_manifest,
)

log = get_logger()


def build_mcp(settings: Settings) -> FastMCP:
    """Construct the FastMCP server and register tools."""
    mcp: FastMCP = FastMCP(name="canvas-sdk-tools")

    default_ver = settings.default_sdk_version

    @mcp.tool
    def capability(feature_or_symbol: str, sdk_version: str | None = None) -> dict[str, Any]:
        """SUPPORTED/UNSUPPORTED/WORKAROUND for a Canvas SDK feature or symbol."""
        out = validate_canvas_capability(feature_or_symbol, sdk_version or default_ver)
        log.info("tool_call", tool="validate_canvas_capability", result=out.get("result"))
        return out

    @mcp.tool
    def fhir_immutability(code_or_diff: str, sdk_version: str | None = None) -> dict[str, Any]:
        """Flag forbidden FHIR mutations (e.g. Observation PATCH/PUT/DELETE)."""
        out = check_fhir_immutability(code_or_diff, sdk_version or default_ver)
        log.info("tool_call", tool="check_fhir_immutability",
                 result=out.get("result"), findings=len(out.get("findings", [])))
        return out

    @mcp.tool
    def manifest(manifest_json: Any, sdk_version: str | None = None) -> dict[str, Any]:
        """Validate CANVAS_MANIFEST.json against the vendored schema."""
        out = validate_manifest(manifest_json, sdk_version)
        log.info("tool_call", tool="validate_manifest",
                 result=out.get("result"), findings=len(out.get("findings", [])))
        return out

    @mcp.tool
    def sandbox_imports(code: str, sdk_version: str | None = None) -> dict[str, Any]:
        """Report what the real RestrictedPython sandbox would reject."""
        out = check_sandbox_imports(code, sdk_version or default_ver)
        log.info("tool_call", tool="check_sandbox_imports",
                 result=out.get("result"), findings=len(out.get("findings", [])))
        return out

    @mcp.tool
    def field_names(code: str, sdk_version: str | None = None) -> dict[str, Any]:
        """Lint Canvas field-name traps (obs.units, dbid__in, lb, __future__, .get)."""
        out = lint_canvas_field_names(code, sdk_version or default_ver)
        log.info("tool_call", tool="lint_canvas_field_names",
                 result=out.get("result"), findings=len(out.get("findings", [])))
        return out

    @mcp.tool
    def supported_versions() -> dict[str, Any]:
        """List the vendored SDK reference buckets available to these tools."""
        return {"supported": list_supported_versions(), "default": default_ver}

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "supported_sdk": list_supported_versions(),
            }
        )

    return mcp


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Require ``Authorization: Bearer <token>`` on the MCP endpoint.

    /healthz is intentionally unauthenticated for liveness probes.
    """

    def __init__(self, app, token: str, protected_prefix: str = "/mcp"):
        super().__init__(app)
        self._token = token
        self._prefix = protected_prefix

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(self._prefix):
            header = request.headers.get("authorization", "")
            expected = f"Bearer {self._token}"
            if not header or header != expected:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def build_app(settings: Settings | None = None):
    """Build the Starlette ASGI app with auth middleware (for serving)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    mcp = build_mcp(settings)
    app = mcp.http_app()
    app.add_middleware(BearerAuthMiddleware, token=settings.mcp_auth_token)
    return app, settings


def main() -> None:
    import uvicorn

    app, settings = build_app()
    log.info("starting", host=settings.host, port=settings.port,
             supported_sdk=list_supported_versions())
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
