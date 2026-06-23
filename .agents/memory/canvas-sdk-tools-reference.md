---
name: canvas-sdk-tools reference generation
description: How reference/ JSON is produced and the lookup quirk in validate_canvas_capability
---

# reference/ JSON is generated — edit the generator too, or a regen reverts you

`scripts/regenerate_reference.py` is the source of truth for everything under
`reference/sdk_<ver>/`. `capability_catalog.json`, `import_allowlist.json`,
`manifest_schema.json` are machine-extracted from a canvas-plugins checkout;
`field_name_rules.json` and `fhir_rules.json` are emitted from **constants inside
the generator**.

**Why:** the running service only reads the JSON, but any hand-edit to the JSON is
silently lost the next time someone runs the generator. The field_name_rules were
shipped *inverted* (flagged `.unit`→`.units`, `id__in`→`dbid__in`) — fixing the
JSON without fixing `build_field_name_rules` would reintroduce the bug on regen.

**How to apply:** when changing any `reference/` JSON, mirror the change in the
matching `build_*` function. The `commands` and `functions` catalog categories are
derived from `import_allowlist.json`'s `allowed_modules` (commands = names ending
in `Command` under `canvas_sdk.commands`; functions = public names under
`canvas_sdk.utils*`, most-specific module wins), so the generator and any in-repo
catalog edit must use that same allowlist-derived logic to stay in lock-step.

# validate_canvas_capability must match on the query LEAF, not the whole path

A pasted dotted symbol's module segment can differ from the catalog's stored
symbol (user pastes `canvas_sdk.effects.banner_alert.AddBannerAlert`; real symbol
is `...add_banner_alert.AddBannerAlert`). Lookup resolves by short key, then by
`leaf = key.rsplit('.',1)[-1]`, then by symbol-leaf/exact-symbol match. This is
intentionally lenient: a wrong module path with a real leaf still resolves
SUPPORTED. The UNSUPPORTED negative case is a fake *leaf*, not a fake path.
