# canvas-sdk-tools

Tier-3 **Canvas-only** MCP server: static, offline analyzers that validate
Canvas SDK plugin code and specs against vendored, version-pinned reference data.

This is the Canvas-specific MCP described in [`REUSABILITY.md`](./REUSABILITY.md)
(deploy unit: Replit Reserved VM **B**). See [`TOOLS.md`](./TOOLS.md) for the
full tool + reference-data specification.

## Hard constraints (binding)

- **Static / offline only.** No tool calls a Canvas instance.
- **No Canvas credentials.** None in config; live sandbox validation stays on the
  local CLI.
- **No PHI.** Tools receive code and JSON specs only; inputs are never logged.
- **Stateless.** No database (no Neon, no Voyage). The only state is the
  read-only `reference/sdk_<ver>/` data baked into the image.
- **Own `MCP_AUTH_TOKEN`**, distinct from the memory server's.

This logic is Canvas-specific and must **never** be merged into
`mcp-assist-memory` (Tier 1).

## Tools

| Tool | What it checks |
|---|---|
| `validate_canvas_capability` | SUPPORTED / UNSUPPORTED / WORKAROUND vs. `capability_catalog.json` |
| `check_fhir_immutability` | Forbidden FHIR mutations (e.g. Observation PATCH/PUT/DELETE) via AST scan |
| `validate_manifest` | `CANVAS_MANIFEST.json` vs. the vendored authoritative JSON Schema |
| `check_sandbox_imports` | Runs code through `RestrictedPython.compile_restricted` (compile-only) |
| `lint_canvas_field_names` | Field-name traps (`obs.units`, `dbid__in`, `lb`, `__future__`, `.get()`) |

Plus `supported_versions` for discovery. Every finding is evidence-bearing
(file/line or JSON path, a symbol or rule id, and a doc_ref).

## Reference data

`reference/sdk_<major.minor>.x/` holds version-pinned JSON. The current bucket is
**`sdk_0.169.x`**, generated from `canvas-medical/canvas-plugins@0.169.1`.
Updating the SDK = drop a new versioned directory; tools select by `sdk_version`.

Regenerate from a checkout:

```bash
git clone --depth 1 --branch 0.169.1 \
  https://github.com/canvas-medical/canvas-plugins.git /tmp/canvas-plugins
python scripts/regenerate_reference.py \
  --checkout /tmp/canvas-plugins --tag 0.169.1 --version 0.169.x
```

`capability_catalog.json`, `import_allowlist.json`, and `manifest_schema.json`
are machine-extracted from the checkout; `fhir_rules.json` and
`field_name_rules.json` are curated from Canvas docs.

## Develop

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
```

## Run

```bash
cp .env.example .env   # set MCP_AUTH_TOKEN
python -m canvas_sdk_tools
```

Serves MCP at `/mcp` (bearer auth) and an unauthenticated `/healthz`.
The operator stands up Reserved VM B and sets `MCP_AUTH_TOKEN`.

## Deployment

Live as a Replit Reserved VM:

- **MCP endpoint:** `https://canvas-sdk-tools.replit.app/mcp` (Streamable HTTP,
  `Authorization: Bearer <MCP_AUTH_TOKEN>`)
- **Health:** `https://canvas-sdk-tools.replit.app/healthz` (no auth)

See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for client setup (Claude Web / CLI), live
verification results, what changed for deployment, and the project structure.
