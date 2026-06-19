"""Unified-diff handling shared by the AST-based tools.

When given a unified diff, we reconstruct the *new* side (context + added lines)
so that ast line numbers correspond to the post-change file.  Plain source is
returned unchanged.
"""

from __future__ import annotations

import re

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def looks_like_diff(text: str) -> bool:
    for line in text.splitlines()[:50]:
        if line.startswith("@@ ") and _HUNK_RE.match(line):
            return True
        if line.startswith("diff --git "):
            return True
    return False


def extract_source(code_or_diff: str) -> str:
    """Return parseable source.

    For a diff, reconstruct the new-side content using hunk headers so line
    numbers line up; deletions are dropped.  For plain code, return as-is.
    """
    if not looks_like_diff(code_or_diff):
        return code_or_diff

    lines_out: dict[int, str] = {}
    new_lineno = 0
    in_hunk = False
    for raw in code_or_diff.splitlines():
        m = _HUNK_RE.match(raw)
        if m:
            new_lineno = int(m.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            lines_out[new_lineno] = raw[1:]
            new_lineno += 1
        elif raw.startswith("-"):
            continue  # deletion: not present on the new side
        elif raw.startswith(" "):
            lines_out[new_lineno] = raw[1:]
            new_lineno += 1
        else:
            # end of hunk / non-diff trailer
            in_hunk = False

    if not lines_out:
        return code_or_diff
    last = max(lines_out)
    return "\n".join(lines_out.get(i, "") for i in range(1, last + 1))
