# Deployment — canvas-sdk-tools

`canvas-sdk-tools` is deployed on **Replit** as an always-on **Reserved VM**
(Web Server). It is static, offline, and **stateless** — no database, no Canvas
credentials, no PHI. The only persistent data is the read-only `reference/`
directory baked into the image, and the only secret is its own `MCP_AUTH_TOKEN`.

## Live service

| | |
|---|---|
| Base URL | `https://canvas-sdk-tools.replit.app` |
| MCP endpoint | `https://canvas-sdk-tools.replit.app/mcp` |
| Transport | Streamable HTTP |
| Auth | `Authorization: Bearer <MCP_AUTH_TOKEN>` |
| Health check | `https://canvas-sdk-tools.replit.app/healthz` (no auth) |
| Deployment type | Replit Reserved VM (always-on), public |
| Runtime | Python 3.11 |
| Run command | `python -m canvas_sdk_tools` (binds `0.0.0.0:8000`, exposed at `80`/`443`) |
| Server identity | `canvas-sdk-tools` v3.4.2 |
| Reference bucket | `sdk_0.169.x` |

## Connect an MCP client

The endpoint speaks Streamable HTTP and requires a bearer token. Replace
`<MCP_AUTH_TOKEN>` with the token stored as the Replit Secret of the same name.

### Claude Web / Desktop (and other JSON-config clients)

```json
{
  "mcpServers": {
    "canvas-sdk-tools": {
      "url": "https://canvas-sdk-tools.replit.app/mcp",
      "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
    }
  }
}
```

### Claude CLI / Claude Code

```bash
claude mcp add --transport http canvas-sdk-tools \
  https://canvas-sdk-tools.replit.app/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

## Exposed tools

The live server reports six tools via `tools/list`:

| Tool id | Purpose |
|---|---|
| `capability` | SUPPORTED / UNSUPPORTED / WORKAROUND vs. `capability_catalog.json` |
| `fhir_immutability` | Forbidden FHIR mutations (e.g. Observation PATCH/PUT/DELETE) via AST scan |
| `manifest` | `CANVAS_MANIFEST.json` vs. the vendored authoritative JSON Schema |
| `sandbox_imports` | Runs code through `RestrictedPython.compile_restricted` (compile-only) |
| `field_names` | Field-name traps (`obs.units`, `dbid__in`, `lb`, `__future__`, `.get()`) |
| `supported_versions` | Discovery of supported SDK reference buckets |

## Verification (live, against production)

| Check | Expected | Result |
|---|---|---|
| `GET /healthz` (no auth) | 200 + status JSON | ✅ 200 `{"status":"ok","version":"0.1.0","supported_sdk":["0.169.x"]}` |
| Root serving (`8000` → `80`/`443`) | served at root | ✅ confirmed |
| `POST /mcp` no token | 401 | ✅ 401 `{"error":"unauthorized"}` |
| `POST /mcp` wrong token | 401 | ✅ 401 |
| `initialize` with bearer | 200 + session | ✅ 200, session id, `serverInfo.name = canvas-sdk-tools` |
| `notifications/initialized` | 202 | ✅ 202 |
| `tools/list` | 200 + tools | ✅ 200, 6 tools |
| `tools/call` (`supported_versions`) | 200, `isError:false` | ✅ returned `{"supported":["0.169.x"],"default":"0.169.x"}` |

Local gates also pass: `ruff check .` is clean and `pytest -q` passes all 34 tests.

## What changed to make it deployable

These changes are limited to environment/runtime configuration — the analyzer
code and `reference/` data were **not** modified.

- **Runtime via Replit modules.** Removed `replit.nix` (it collided with the
  Python toolchain) and pinned the runtime with `modules = ["python-3.11"]` in
  `.replit`, plus `[nix] packages = ["libxcrypt"]` for the native dependency.
- **Locked dependencies.** Added `uv.lock` and the dev/server extras in
  `pyproject.toml` so the build is reproducible.
- **Deployment config in `.replit`.** Added a `[deployment]` block
  (`deploymentTarget = "vm"`, `run = ["python", "-m", "canvas_sdk_tools"]`),
  a `[[ports]]` mapping for `localPort = 8000`, and a console workflow that runs
  the server.
- **Production port mapping.** The Reserved VM exposes the service on the root
  domain by mapping internal `8000` → external `80`/`443` in the deployment's
  Networking configuration.
- **Secret.** Generated a strong random `MCP_AUTH_TOKEN` and stored it as a
  Replit Secret. No Canvas credentials, database URL, or API keys are set.
- **No database.** The service remains stateless by design; nothing was
  provisioned.

## Project structure

```
.
├── .env.example                 # MCP_AUTH_TOKEN template
├── .python-version              # 3.11
├── .replit                      # Replit run/deploy/port/workflow config
├── pyproject.toml               # package + dev extras
├── uv.lock                      # locked dependency graph
├── README.md
├── DEPLOYMENT.md                # this file
├── REUSABILITY.md               # deploy-unit / access-matrix context
├── TOOLS.md                     # tool + reference-data specification
├── docs/
│   └── REPLIT_AGENT_PROMPT.md   # authoritative deploy spec
├── reference/
│   └── sdk_0.169.x/             # version-pinned, read-only reference data
│       ├── capability_catalog.json
│       ├── fhir_rules.json
│       ├── field_name_rules.json
│       ├── import_allowlist.json
│       ├── manifest_schema.json
│       ├── PROVENANCE.md
│       └── VERSION
├── scripts/
│   └── regenerate_reference.py  # rebuild reference data from an SDK checkout
├── src/
│   └── canvas_sdk_tools/
│       ├── __main__.py          # `python -m canvas_sdk_tools` entrypoint
│       ├── app.py               # FastMCP server: /mcp (bearer) + /healthz
│       ├── config.py            # env-driven settings (pydantic-settings)
│       ├── reference.py         # reference-data loader
│       ├── diff.py
│       ├── evidence.py
│       ├── logging.py
│       └── tools/               # capability, fhir, field_names, manifest, sandbox
└── tests/                       # 34 tests + good/bad fixtures
```

## Operate / redeploy

- **Redeploy:** push changes and re-publish from Replit; the run command and
  port mapping are already configured.
- **Rotate the token:** update the `MCP_AUTH_TOKEN` Replit Secret and redeploy,
  then update each connected client's bearer header.
- **Bump the SDK reference:** drop a new `reference/sdk_<ver>/` bucket (see
  `README.md` → Reference data); clients select via `sdk_version`.
