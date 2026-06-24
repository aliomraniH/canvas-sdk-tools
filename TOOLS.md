# `canvas-sdk-tools` — Tool & Reference-Data Specification

> **Status: IMPLEMENTED.** This document defines the five MCP tools, exactly
> what each one checks, the evidence each returns, and the on-disk format of the
> vendored `reference/` data they check against. The server, the analyzers, the
> `reference/sdk_0.169.x/` data (generated from `canvas-plugins@0.169.1`), the
> fixtures, and CI are all in the repo.

Tier-3 Canvas-only MCP from `REUSABILITY.md`. This is the **Canvas SDK static
analyzer** service that runs on Replit Reserved VM **B**. Canvas-named tools are
legitimate here (Tier 3). This logic must **never** be merged into
`mcp-assist-memory` (Tier 1).

---

## 1. Hard constraints (binding — from `REUSABILITY.md` §"Canvas MCP")

| Constraint | How this spec honors it |
|---|---|
| **Static / offline only** | Every tool analyzes *code/specs passed in as arguments* against vendored reference data. No tool opens a network socket. |
| **Never call a Canvas instance** | No HTTP client to any Canvas host. No FHIR base URL. The word "endpoint" appears only inside `fhir_rules.json` as a *pattern to detect in user code*, never as something we call. |
| **No Canvas credentials** | `config.py` defines **no** Canvas auth fields. Live sandbox validation stays on the local CLI. |
| **No PHI** | Tools receive source code and JSON specs only. Inputs are never logged verbatim at INFO (see §6 logging). |
| **Stateless** | No DB. No Neon. No Voyage. No per-request persistence. The only state is the read-only, version-pinned `reference/` tree baked into the image. |
| **Own `MCP_AUTH_TOKEN`** | Distinct bearer token from the memory server. Set by the operator on VM B. |
| **Same clean pattern as memory server** | `config.py` (pydantic-settings) · `app.py` (FastMCP + bearer auth on `/mcp`, plus `/healthz`) · `structlog` JSON logging. |

---

## 2. Versioned reference data — `reference/sdk_<ver>/`

The "vendored SDK surface" is a set of **version-pinned JSON data files**. Each
supported Canvas SDK minor version gets its own directory. Tools select the
directory by the `sdk_version` argument.

```
reference/
  sdk_0.169.x/
    VERSION                 # exact pinned tag the data was generated from, e.g. "0.169.1"
    PROVENANCE.md           # source commit/tag URLs + generation date + how to regenerate
    capability_catalog.json # events, data models, effect types, handler base classes
    fhir_rules.json         # allowed FHIR interactions per resource
    manifest_schema.json    # JSON Schema for CANVAS_MANIFEST.json
    import_allowlist.json   # RestrictedPython sandbox allow-list (mirrors plugin_runner)
    field_name_rules.json   # known field-name traps
```

### 2.1 Version selection (shared by all tools)

- `sdk_version` is a **string** like `"0.169.x"`, `"0.169"`, or an exact
  `"0.169.1"`.
- Resolution: normalize to the `sdk_<major.minor>.x` bucket → look up
  `reference/sdk_<major.minor>.x/`.
- If the bucket is missing → tool returns a structured error
  `{"error": "unsupported_sdk_version", "supported": [...], "requested": "..."}`.
  Tools **never** silently fall back to a different version (a false "supported"
  is worse than an explicit "unknown").
- A `GET`-style helper `list_supported_versions()` is exposed for discovery
  (optional, low-risk; included so the planning surface can enumerate buckets).

### 2.2 "Updating the SDK" workflow

Updating = **drop a new `reference/sdk_<newver>/` directory**; tools pick it up
by version. No code change required for a data-only bump. Each directory's
`PROVENANCE.md` records the upstream tag (`canvas-medical/canvas-plugins`) and
the regeneration command, so the data is auditable and reproducible.

> The pinned baseline for the first cut is **`sdk_0.169.x`** (upstream latest,
> generated from tag `0.169.1`). Per the contract, an older bucket such as
> `sdk_0.163.x` can be added later as a data-only drop.

---

## 3. Reference-data file formats

All files are UTF-8 JSON with a top-level `"_meta"` block:

```json
"_meta": {
  "sdk_version": "0.169.x",
  "generated_from": "canvas-medical/canvas-plugins@0.169.1",
  "generated_at": "2026-06-19",
  "doc_base": "https://docs.canvasmedical.com/sdk/"
}
```

Every *rule* entry carries its own `doc_ref` and/or `symbol` so tools can emit
evidence rather than bare assertions.

### 3.1 `capability_catalog.json`

Drives `validate_canvas_capability`. Six catalogs keyed by kind
(`handler_base_classes`, `data_models`, `commands`, `effects`, `events`,
`functions`), plus an `aliases` map.

```json
{
  "_meta": { ... },
  "handler_base_classes": {
    "BaseHandler":        { "symbol": "canvas_sdk.handlers.BaseHandler",            "status": "SUPPORTED", "doc_ref": "sdk/handlers/" },
    "SimpleAPI":          { "symbol": "canvas_sdk.handlers.simple_api.SimpleAPI",   "status": "SUPPORTED", "doc_ref": "sdk/handlers-simple-api/" },
    "SimpleAPIRoute":     { "symbol": "canvas_sdk.handlers.simple_api.SimpleAPIRoute", "status": "SUPPORTED", "doc_ref": "sdk/handlers-simple-api/" },
    "BaseProtocol":       { "symbol": "canvas_sdk.protocols.BaseProtocol",          "status": "WORKAROUND", "replacement": "BaseHandler", "doc_ref": "sdk/handlers/", "note": "legacy alias; use BaseHandler" }
  },
  "events": {
    "OBSERVATION_CREATED": { "symbol": "EventType.OBSERVATION_CREATED", "status": "SUPPORTED", "doc_ref": "sdk/events/" },
    "...": {}
  },
  "effects": {
    "BannerAlert":   { "symbol": "canvas_sdk.effects.banner_alert.BannerAlert",   "status": "SUPPORTED", "doc_ref": "sdk/effect-banner-alert/" },
    "ProtocolCard":  { "symbol": "canvas_sdk.effects.protocol_card.ProtocolCard", "status": "SUPPORTED", "doc_ref": "sdk/effect-protocol-card/" },
    "...": {}
  },
  "data_models": {
    "Observation": { "symbol": "canvas_sdk.v1.data.Observation", "status": "SUPPORTED", "doc_ref": "sdk/data-observation/" },
    "Patient":     { "symbol": "canvas_sdk.v1.data.Patient",     "status": "SUPPORTED", "doc_ref": "sdk/data-patient/" },
    "...": {}
  },
  "commands": {
    "GoalCommand": { "symbol": "canvas_sdk.commands.GoalCommand", "status": "SUPPORTED", "doc_ref": "sdk/commands/" },
    "...": {}
  },
  "functions": {
    "Http": { "symbol": "canvas_sdk.utils.http.Http", "status": "SUPPORTED", "doc_ref": "sdk/utils/" },
    "...": {}
  },
  "aliases": { "Protocol": "BaseProtocol", "obs": "Observation" }
}
```

- `status` ∈ `SUPPORTED` | `UNSUPPORTED` | `WORKAROUND`.
- `WORKAROUND` entries SHOULD carry `replacement` and/or `note`.
- `aliases` maps common shorthands a user might pass to the canonical key.
- Catalog contents are generated from the pinned tag: events from
  `canvas_generated.messages.events_pb2.EventType`; effects from
  `canvas_sdk/effects/`; data models from `canvas_sdk/v1/data/`; handler base
  classes from `canvas_sdk/handlers/`; commands and functions from the public
  import allowlist (`commands` = `*Command` symbols under `canvas_sdk.commands`;
  `functions` = public names under `canvas_sdk.utils*`).

### 3.2 `fhir_rules.json`

Drives `check_fhir_immutability`. Per-resource allowed interaction set plus the
detection patterns the AST scanner uses.

```json
{
  "_meta": { ... },
  "resources": {
    "Observation": {
      "allowed":   ["create", "read", "search"],
      "forbidden": ["update", "patch", "delete"],
      "rationale": "Observations are immutable clinical records; corrections are new Observations.",
      "doc_ref":   "api/observation/"
    },
    "AllergyIntolerance": { "allowed": ["create","read","search","update"], "forbidden": ["delete"], "doc_ref": "api/allergyintolerance/" }
  },
  "interaction_map": {
    "put":    "update",
    "patch":  "patch",
    "delete": "delete",
    "post":   "create",
    "get":    "read"
  },
  "detection": {
    "http_methods": ["put", "patch", "delete"],
    "url_resource_regex": "/([A-Z][A-Za-z]+)(?:/[^/\"']+)?/?$",
    "orm_mutators": ["save", "update", "delete"],
    "note": "Static signals only. The tool flags a *call site* that would perform a forbidden interaction on a FHIR resource named in `resources`."
  }
}
```

### 3.3 `manifest_schema.json`

The **authoritative** schema, extracted verbatim from
`canvas_cli/utils/validators/manifest_schema.py` at the pinned tag (so it always
matches what the real CLI validates), with `$schema`/`title`/`_meta` added and
validated by `validate_manifest` via `jsonschema` (Draft 2020-12). The real
schema is richer than the illustrative shape below — it includes `variables`,
`origins`/`url_permissions` (mutually exclusive), `questionnaires`, `commands`,
`custom_data`, the full `applications.scope` enum, and `tags` enums; top-level
`required` is `["sdk_version","plugin_version","name","description","components","tags","license","readme"]`.
Illustrative excerpt:

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CANVAS_MANIFEST.json",
  "type": "object",
  "required": ["sdk_version", "plugin_version", "name", "components"],
  "properties": {
    "sdk_version":    { "type": "string" },
    "plugin_version": { "type": "string" },
    "name":           { "type": "string" },
    "description":    { "type": "string" },
    "components": {
      "type": "object",
      "properties": {
        "protocols":    { "type": "array", "items": { "$ref": "#/$defs/handlerComponent" } },
        "handlers":     { "type": "array", "items": { "$ref": "#/$defs/handlerComponent" } },
        "applications": { "type": "array", "items": { "$ref": "#/$defs/applicationComponent" } },
        "commands":     { "type": "array" },
        "content":      { "type": "array" },
        "effects":      { "type": "array" },
        "views":        { "type": "array" }
      },
      "additionalProperties": false
    },
    "secrets": { "type": "array", "items": { "type": "string" } },
    "tags":    { "type": "object" }
  },
  "$defs": {
    "dataAccess": {
      "type": "object",
      "properties": {
        "event": { "type": "string" },
        "read":  { "type": "array", "items": { "type": "string" } },
        "write": { "type": "array", "items": { "type": "string" } }
      },
      "additionalProperties": false
    },
    "handlerComponent": {
      "type": "object",
      "required": ["class", "description", "data_access"],
      "properties": {
        "class":       { "type": "string", "pattern": "^[\\w./-]+:[A-Za-z_][A-Za-z0-9_]*$" },
        "description": { "type": "string" },
        "data_access": { "$ref": "#/$defs/dataAccess" }
      },
      "additionalProperties": false
    },
    "applicationComponent": {
      "type": "object",
      "required": ["class", "name", "description", "scope"],
      "properties": {
        "class":       { "type": "string" },
        "name":        { "type": "string" },
        "description": { "type": "string" },
        "scope":       { "type": "string", "enum": ["patient_specific", "global"] },
        "icon":        { "type": "string" }
      }
    }
  }
}
```

> The `class` pattern enforces Canvas's `module/path:ClassName` class-path
> convention. `data_access.read`/`write` values (e.g. `"v1.Observation"`) are
> schema-validated as strings here; cross-checking them against the capability
> catalog is a **future enhancement** noted in `validate_manifest`'s output.

### 3.4 `import_allowlist.json`

Mirrors the real `plugin_runner` sandbox allow-list so `check_sandbox_imports`
has a faithful backstop. Generated from the upstream
`plugin_runner/allowed-module-imports.json` plus the hard-coded
`STANDARD_LIBRARY_MODULES` / `THIRD_PARTY_MODULES` / `CANVAS_MODULES` sets in
`plugin_runner/sandbox.py` at the pinned tag.

Faithful to the real `ALLOWED_MODULES` (a module → allowed-names map): the
generator merges `STANDARD_LIBRARY_MODULES` + `THIRD_PARTY_MODULES` (AST-extracted
from `plugin_runner/sandbox.py`) with `plugin_runner/allowed-module-imports.json`
into a single `allowed_modules` dict. `["*"]` means any name from that module.

```json
{
  "_meta": { ... },
  "allowed_modules": {
    "__future__": ["annotations"],
    "json": ["JSONDecodeError", "dumps", "loads"],
    "requests": ["*"],
    "canvas_sdk.handlers": ["BaseHandler"],
    "canvas_sdk.v1.data": ["*"]
  },
  "name_rules": {
    "no_leading_underscore": true,
    "no_dunder_assignment_except": ["__all__"],
    "no_star_import_from_unlisted": true
  }
}
```

### 3.5 `field_name_rules.json`

Drives `lint_canvas_field_names`. Each rule is an evidence-bearing trap.

```json
{
  "_meta": { ... },
  "attribute_renames": [
    { "id": "obs-units", "wrong": "unit", "right": "units", "applies_to": ["Observation","obs"], "message": "Observation uses `.units` (plural), not `.unit`.", "doc_ref": "sdk/data-observation/" }
  ],
  "kwarg_renames": [
    { "id": "dbid-in", "wrong": "id__in", "right": "dbid__in", "message": "Filter on `dbid__in`, not `id__in`.", "doc_ref": "sdk/data-basics/" }
  ],
  "value_literals": [
    { "id": "weight-unit", "field": "units", "wrong": "lbs", "right": "lb", "message": "Weight unit literal is `lb`, not `lbs`.", "doc_ref": "sdk/data-observation/" }
  ],
  "required_pragmas": [
    { "id": "future-annotations", "require": "from __future__ import annotations", "scope": "module", "message": "Canvas plugin modules must start with `from __future__ import annotations`.", "doc_ref": "sdk/" }
  ],
  "access_patterns": [
    { "id": "underscore-get", "pattern": "subscript_on_underscore_key", "right": ".get()", "message": "Use `.get('_key')` for underscore-prefixed keys; subscripting raises under the sandbox.", "doc_ref": "sdk/" }
  ]
}
```

---

## 4. The five tools

All tools are **deterministic** and **evidence-bearing**: every finding carries
`file`/`line` (or `path` for JSON), a `symbol` or `rule_id`, and a `doc_ref`.
No finding is ever a bare assertion. Inputs may be a string of code, or a
unified diff (tools that accept diffs parse added lines only).

Common response envelope:

```json
{
  "tool": "<name>",
  "sdk_version": "0.169.x",
  "ok": true,
  "result": "<tool-specific verdict>",
  "findings": [ { "...": "evidence object" } ],
  "checked": { "...": "what was inspected, for transparency" }
}
```

### 4.1 `validate_canvas_capability(feature_or_symbol, sdk_version)`

- **Checks:** whether `feature_or_symbol` exists in `capability_catalog.json`
  for the resolved version. Resolves through `aliases` first, then searches all
  six catalogs (handler base classes, data models, commands, effects, events,
  functions). Accepts a bare name or a fully dotted symbol: matching is by exact
  key, then by **leaf name** (the trailing `.`-segment), then by a catalog
  entry's trailing symbol segment — so a pasted module path that differs from the
  catalog's stored symbol (e.g. `effects.banner_alert.AddBannerAlert` vs the real
  `effects.add_banner_alert.AddBannerAlert`) still resolves.
- **Returns:** `result` ∈ `SUPPORTED` | `UNSUPPORTED` | `WORKAROUND`, plus the
  matched `symbol`, `doc_ref`, and (for `WORKAROUND`) `replacement`/`note`.
  Unknown symbol → `UNSUPPORTED` with `"reason": "not_in_catalog"` and nearest
  catalog suggestions (fuzzy match over keys; falls back to matching distinctive
  path segments against catalog symbols — no network).
- **Evidence:** the catalog `symbol` + `doc_ref`.

### 4.2 `check_fhir_immutability(code_or_diff)`

- **Checks:** AST scan (Python `ast`) for call sites that would perform a
  **forbidden** FHIR interaction on a resource listed in `fhir_rules.json` —
  e.g. `requests.put/patch/delete(...)` to a URL whose trailing resource segment
  matches a `resources` key, or ORM `.save()/.update()/.delete()` on a model the
  rules mark immutable. The canonical trap: any PATCH/PUT/DELETE on
  `Observation`.
- **Returns:** `ok=false` with one finding per forbidden call site:
  `{ "file", "line", "col", "resource": "Observation", "interaction": "patch", "evidence": "<source snippet>", "rule": "fhir.Observation.forbidden", "doc_ref": "..." }`.
- **Determinism:** purely AST + regex over the supplied text. `sdk_version`
  optional (defaults to newest bucket) since FHIR rules are resource-scoped.
- **Limits (stated honestly in output):** static call-site detection; dynamic
  method names / indirected URLs may not be caught. Never produces false
  *immutability passes* by calling anything live.

### 4.3 `validate_manifest(manifest_json)`

- **Checks:** parses `manifest_json` (string or object) and validates it against
  `manifest_schema.json` for the version (read from the manifest's own
  `sdk_version`, overridable by an explicit arg) using `jsonschema`
  (Draft 2020-12).
- **Returns:** `result` = `VALID` | `INVALID`; on invalid, one finding per
  schema violation: `{ "path": "components.handlers[0].class", "message": "...", "validator": "pattern", "doc_ref": "manifest-schema" }`.
- **Extras:** warns (non-fatal) when `data_access.read/write` entries don't
  resolve in the capability catalog (flagged as `severity: "warning"`).

### 4.4 `check_sandbox_imports(code)`

- **Highest-fidelity check.** Runs the code through
  **`RestrictedPython.compile_restricted`** with the same guard configuration
  the real `plugin_runner` sandbox uses (custom `RestrictingNodeTransformer`
  subclass enforcing `visit_Import`/`visit_ImportFrom` against the allow-list).
  This reports what the **real sandbox would reject** rather than hand-guessing.
- **Backstop:** if `compile_restricted` surfaces an import error, or to enrich
  messages, cross-reference `import_allowlist.json` to say *why* (module not in
  allow-list / forbidden name / star-import from unlisted module).
- **Returns:** `result` = `ACCEPTED` | `REJECTED`; findings carry
  `{ "file", "line", "message", "offending_import": "os.system", "rule": "not_in_allowlist" | "leading_underscore" | "star_import" | "dunder_assignment", "doc_ref": "..." }`.
- **Note:** `RestrictedPython` is a real dependency of this MCP (it is *analysis*
  tooling, not the executed plugin — we compile, we never `exec`).

### 4.5 `lint_canvas_field_names(code)`

- **Checks:** AST scan against `field_name_rules.json`:
  - `attribute_renames` — `obj.unit` where `obj` is an `Observation`/`obs` →
    suggest `.units`.
  - `kwarg_renames` — `...filter(id__in=...)` → suggest `dbid__in`.
  - `value_literals` — string literal `"lbs"` assigned to a `units` field →
    suggest `"lb"`.
  - `required_pragmas` — module missing `from __future__ import annotations` as
    its first statement.
  - `access_patterns` — subscripting an underscore-prefixed key
    (`d["_id"]`) → suggest `.get("_id")`.
- **Returns:** `result` = `CLEAN` | `ISSUES`; one finding per hit:
  `{ "file", "line", "col", "rule_id": "obs-units", "found": "unit", "suggested": "units", "message": "...", "doc_ref": "..." }`.

---

## 5. Repo-scaffold plan

```
canvas-sdk-tools/
├── REUSABILITY.md                # the contract (this repo's copy) — already added
├── TOOLS.md                      # this spec
├── README.md                     # what/why, run instructions, link to TOOLS.md
├── pyproject.toml                # deps; ruff + pytest config
├── .python-version               # pinned interpreter
├── .env.example                  # MCP_AUTH_TOKEN=, LOG_LEVEL=, HOST=, PORT=
├── .gitignore
├── .replit                       # Reserved VM B run config (operator deploys)
├── replit.nix                    # system deps for the Reserved VM
├── src/
│   └── canvas_sdk_tools/
│       ├── __init__.py
│       ├── __main__.py           # python -m canvas_sdk_tools
│       ├── config.py             # pydantic-settings: MCP_AUTH_TOKEN, host, port, log level, default_sdk_version
│       ├── app.py                # FastMCP server; bearer auth on /mcp; /healthz; structlog JSON; registers 5 tools
│       ├── logging.py            # structlog JSON config (no PHI/code bodies at INFO)
│       ├── reference.py          # version resolver + cached loader for reference/sdk_<ver>/*.json
│       ├── evidence.py           # shared finding/envelope builders
│       ├── diff.py               # unified-diff -> new-side source (for the AST tools)
│       └── tools/
│           ├── __init__.py
│           ├── capability.py     # validate_canvas_capability
│           ├── fhir.py           # check_fhir_immutability
│           ├── manifest.py       # validate_manifest
│           ├── sandbox.py        # check_sandbox_imports (RestrictedPython)
│           └── field_names.py    # lint_canvas_field_names
├── reference/
│   └── sdk_0.169.x/              # VERSION, PROVENANCE.md, + the 5 JSON files (§2–3)
├── scripts/
│   └── regenerate_reference.py   # builds reference/sdk_<ver>/ from a canvas-plugins checkout (dev-time only; offline at runtime)
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── good/                 # known-good plugin code + manifests
    │   └── bad/                  # known-bad: obs.unit, id__in, Observation PATCH, os import, missing __future__, bad manifest
    ├── test_capability.py
    ├── test_fhir.py
    ├── test_manifest.py
    ├── test_sandbox.py
    ├── test_field_names.py
    ├── test_reference_loader.py  # version resolution + unknown-version error
    └── test_app_health.py        # /healthz + bearer-auth gate on /mcp
```

### Dependencies (`pyproject.toml`)
`fastmcp`, `pydantic`, `pydantic-settings`, `structlog`, `jsonschema`,
`RestrictedPython`, `arrow`(only if a fixture needs it) · dev: `pytest`,
`ruff`. **Deliberately absent:** any DB driver, Neon client, Voyage/embeddings,
HTTP client to Canvas, Canvas SDK runtime.

### Server shape (matches memory server)
- `config.py` → `Settings(BaseSettings)` with `MCP_AUTH_TOKEN` (required),
  `host`, `port`, `log_level`, `default_sdk_version="0.169.x"`. No Canvas creds.
- `app.py` → `FastMCP` instance; bearer-token auth middleware on `/mcp`;
  unauthenticated `/healthz` returning `{status, version, supported_sdk}`;
  registers the five tools (+ optional `list_supported_versions`).
- `logging.py` → `structlog` JSON renderer; request logs include tool name and
  finding counts, **never** the submitted code/manifest bodies.

### CI — `.github/workflows/test.yml`
- Trigger: `push` + `pull_request`.
- Steps: checkout → setup Python (pinned) → install (`pip install -e ".[dev]"`)
  → `ruff check` → `pytest -q`.
- **No services, no DB** → fast CI. Tests run the analyzers against the
  `good/` (expect pass) and `bad/` (expect specific findings) fixture pairs, and
  assert the reference loader rejects unknown versions.

### Delivered
Server + analyzers, the populated `reference/sdk_0.169.x/*.json` data (generated
from `canvas-plugins@0.169.1`), the regenerate script, fixtures, and the
workflow are all in the repo. `pytest -q` and `ruff check .` pass.

---

## 6. Cross-cutting decisions (call out for review)

1. **Pin = `0.169.x`** as the first vendored bucket (upstream latest, tag
   `0.169.1`). Adding an older bucket like `0.163.x` later is a data-only drop.
2. **`RestrictedPython` is a runtime dependency** of this MCP — used only to
   *compile* (never `exec`) user code, which is the highest-fidelity sandbox
   check available offline.
3. **No DB / no embeddings / no Canvas client** in `pyproject.toml` — enforced
   by review; their absence is the proof of the "static/stateless" constraint.
4. **PHI/secret hygiene in logs:** code/manifest bodies are never logged at
   INFO; only metadata (tool, version, finding counts) is.
5. **Honest limits surfaced in tool output:** `check_fhir_immutability` and
   `lint_canvas_field_names` are static and may miss dynamically-constructed
   calls; each response states this so a green result is never over-trusted.
```
