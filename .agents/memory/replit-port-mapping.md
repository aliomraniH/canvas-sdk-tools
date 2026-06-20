---
name: Replit port mapping side-effect
description: configureWorkflow rewrites .replit [[ports]] externalPort to match the internal port (1:1), which can clobber a hand-authored externalPort=80 needed for root-domain serving.
---

# Replit [[ports]] externalPort drift from configureWorkflow

When you call `configureWorkflow` with a console `outputType` and `waitForPort = N`, the platform writes/normalizes `.replit` `[[ports]]` so that `localPort = N` maps to `externalPort = N` (1:1). If the repo shipped a deliberate non-1:1 mapping (e.g. `localPort = 8000` / `externalPort = 80`), this side-effect overwrites `externalPort` to `8000`, and it does NOT revert when you `removeWorkflow`. `deployConfig` does not touch `[[ports]]` either.

**Why it matters:** Replit routes the root domain (HTTPS/443) to `externalPort = 80` only. Any other external port is served at `domain:<port>/`, not the root. So a deployment that must answer at `<URL>/<path>` (root) requires `externalPort = 80`. With `externalPort = 8000` the service would only be reachable at `<URL>:8000/<path>`.

**How to apply / fix:**
- There is NO agent tool to set a console internal port to `externalPort = 80`. `configureWorkflow` forces 1:1 for console ports; webview maps to 80 but is locked to internal port 5000. Direct edits to `.replit` are blocked, and `git checkout/restore` is sandbox-blocked for the main agent.
- Resolution is a user action: open the Networking/Ports tool (gear icon in the Ports pane) and set internal `8000` → external `80`; or roll back to a checkpoint that still has the correct mapping.
- Practical guard: if a repo ships a hand-authored non-1:1 `[[ports]]` mapping, avoid running `configureWorkflow` on that same port, or expect to restore the mapping via the UI afterward.
