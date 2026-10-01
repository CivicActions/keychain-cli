# Security Exception Register

This file lists every active exception to the constitution's Principle II, *Secrets Never
Surface*. An empty register is the expected steady state. Each entry must name the exact
code path, the exposure window, who or what can observe it, why no stdin, file-descriptor,
or platform-API alternative exists, the approving maintainer, the automated test that pins
the boundary, and the trigger that would remove the need for it.

The register is reviewed at each release. An exception whose re-evaluation trigger has fired
must be closed or renewed.

## Summary

| ID | Channel | Status | Approved by | Pinning test |
|---|---|---|---|---|
| CLIP-001 | System clipboard via `pbcopy` | Active (approved 2026-09-25) | Fen Labalme | `tests/unit/test_clipboard.py::test_value_reaches_only_pbcopy_stdin` |

## CLIP-001: clipboard copy of a single secret

**Status**: Active. Approved 2026-09-25. Implemented with pinning test
`tests/unit/test_clipboard.py::test_value_reaches_only_pbcopy_stdin` in Phase 9.

**Code path**: `keychain_cli/commands/copy.py` → `keychain_cli/clipboard.py` →
`/usr/bin/pbcopy`, with the value written to `pbcopy`'s **stdin**. The detached clearing
helper `keychain_cli/_clipclear.py` receives only a SHA-256 digest of the value and the
interval, also on stdin. No secret is placed in any process's arguments.

**Exposure window**: from the moment `pbcopy` returns until the clearing helper removes the
value, at most `--clear-after` seconds (default 45, maximum 300), or until the user copies
something else. If the helper cannot be started, the command clears the clipboard immediately
and exits non-zero. If the helper is killed before the interval elapses, the value remains
until the next copy; help text and README document this residual exposure.

**Who or what can observe it**: any process running as the same user that reads the
pasteboard; clipboard managers and history tools, which may retain the value after clearing;
Universal Clipboard and similar sync services, which may transmit it to other devices.

**Why no alternative**: the command's purpose is to deliver a value to an application that
cannot read environment variables, such as a vendor web console. The only channels such an
application accepts are the clipboard and the keyboard. Printing to stdout was considered
and rejected as strictly worse: it lands in terminal scrollback and shell logs with no
automatic clearing. A transient or app-scoped pasteboard is not reachable from an unsigned
command-line tool.

**Mitigations**: explicit command, never a default path (spec FR-019a, FR-019b); one variable
per invocation, no bulk form (FR-019c); value never printed (FR-019d); automatic clearing
that never overwrites newer clipboard content and fails closed (FR-019e); an unsuppressible
per-use warning (FR-019f); help and documentation state the exposure (FR-019g); excluded
from primary `.env`-replacement guidance (FR-019h).

**Approving maintainer**: Fen Labalme, 2026-09-25. Recorded by the git commit that adds this
entry.

**Pinning test**: `tests/unit/test_clipboard.py::test_value_reaches_only_pbcopy_stdin`
asserts that the value bytes appear in no spawned process's argv and only in the recorded
`pbcopy` stdin. `tests/unit/test_clipboard_isolation.py` asserts that no module other than
`commands/copy.py` imports `clipboard.py` and that no other command spawns `pbcopy`.

**Re-evaluation trigger**: macOS provides a transient, app-scoped, or expiring pasteboard
that a command-line tool can use without code-signing entitlements; or the team reports the
command is unused for two consecutive releases, in which case it should be removed.
