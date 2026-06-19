# Replit Agent — deploy `canvas-sdk-tools` (Reserved VM B)

Copy everything in the **PROMPT** block below into the Replit Agent for this repo.
Then paste the two values it returns (deployment URL + `MCP_AUTH_TOKEN`) back to
Claude Code so the Canvas MCP can be wired into the surfaces.

> **No database.** `canvas-sdk-tools` is a static, offline, **stateless** service.
> It uses only the vendored `reference/` data baked into the image. Do **not**
> provision Postgres/Neon or any database for it — that belongs to the *separate*
> `mcp-assist-memory` service, not this one. The only secret this service needs is
> its own `MCP_AUTH_TOKEN`.

---

## PROMPT

You are deploying a Python MCP server named **canvas-sdk-tools** from this repo
(branch `claude/sleepy-cannon-d804yq`, or `main` once merged). It is a static,
offline, **stateless** analysis service. Follow these steps exactly and do not
add anything beyond them.

**1. Environment**
- Use **Python 3.11** (see `.python-version`).
- Install dependencies: `pip install -e ".[dev]"`.

**2. Verify the build before deploying**
- Run `ruff check .` — it must pass.
- Run `pytest -q` — all tests must pass (expect ~34 passing). If anything fails,
  stop and report the failure; do not deploy a broken build.

**3. Secrets**
- Generate one strong random token (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- Add it as a Replit **Secret** named `MCP_AUTH_TOKEN`.
- Do **not** set any Canvas credentials, database URL, or embedding/API keys.
  This service has none and needs none.

**4. Do NOT add a database**
- This service is stateless. If you are prompted to attach Postgres, Neon, or any
  database/storage add-on, **decline**. The only persistent data is the
  read-only `reference/` directory already in the repo.

**5. Deploy as a Reserved VM**
- Deployment type: **Reserved VM** (always-on), matching the included `.replit`
  and `replit.nix`.
- Run command: `python -m canvas_sdk_tools`.
- The server binds `0.0.0.0:8000`; map it to external `80`/`443` (already declared
  in `.replit` `[[ports]]`).

**6. Smoke-test the running deployment**
- `GET /healthz` (no auth) must return HTTP 200 with JSON like
  `{"status":"ok","version":"...","supported_sdk":["0.169.x"]}`.
- `POST /mcp` **without** an `Authorization` header must return **401**.
- `POST /mcp` **with** header `Authorization: Bearer <MCP_AUTH_TOKEN>` must be
  accepted (the MCP handshake responds).

**7. Report back exactly these two things**
- The public **deployment base URL** (and therefore the MCP endpoint, `<URL>/mcp`).
- The value of **`MCP_AUTH_TOKEN`** you generated.

Do not open the Canvas instance, do not add CI changes, and do not modify the
analyzer code or the `reference/` data.

---

## After the agent finishes

Give Claude Code:
1. `MCP endpoint`: `https://<your-replit-url>/mcp`
2. `MCP_AUTH_TOKEN`: `<the generated token>`

Claude will register this as MCP #2 (Canvas-only, read+write on CLI/build,
read on Desktop/review, planning checks on Web) per the access matrix in
`REUSABILITY.md`, keeping it distinct from the memory server's token.
