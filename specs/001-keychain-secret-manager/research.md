# Phase 0 Research: Keychain Secret Manager

**Feature**: `001-keychain-secret-manager` | **Date**: 2026-09-24

Every unknown in the plan's Technical Context is resolved here. Each entry records the
decision, the rationale, and the alternatives considered. Where a decision was verified by
running code, the probe is noted; the probe script is kept at
[research/keychain-probe.py](research/keychain-probe.py) and uses placeholder values only.

---

## R-001: Keychain access mechanism

**Decision**: Call the macOS Security framework directly from Python via `ctypes`
(`SecItemAdd`, `SecItemCopyMatching`, `SecItemUpdate`, `SecItemDelete`), with
CoreFoundation helpers for dictionaries, strings, data, and numbers. No secret value is ever
placed in `argv`; values travel as `CFData` inside process memory.

**Rationale**:

- Satisfies the constitution's Principle III preference for an API integration and the
  user's constraint that secrets never appear in `argv`. No Principle II exception is needed
  for storage.
- `ctypes` is standard library, satisfying Principle V with zero runtime dependencies.
- Only the Security framework offers a **multi-match attribute query**, which namespace
  listing requires. The `security` command has no equivalent: `find-generic-password`
  returns one item, and `dump-keychain` walks the whole keychain unfiltered and can trigger
  authorization prompts on unrelated items.
- **Verified by probe** on macOS 26.7 / Python 3.14.7: create a temp keychain, add stamped
  items, enumerate by creator stamp with attributes only, read data by exact match, update,
  delete a whole namespace, and confirm `errSecDuplicateItem` (-25299) and
  `errSecItemNotFound` (-25300) surface as expected. Multi-line UTF-8 values round-trip
  byte-exact.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| `/usr/bin/security add-generic-password -w VALUE` | Places the secret in `argv`; forbidden without a Principle II exception. |
| `/usr/bin/security add-generic-password` with `-w` omitted (prompts) | No `argv` exposure, but no multi-match listing, and the interactive prompt cannot be driven from tests or stdin mode. |
| `keyring` package | Its macOS backend also uses `ctypes`, but it exposes no enumeration API, so listing would need our own bindings anyway. Adds a dependency for no gain. |
| PyObjC `pyobjc-framework-Security` | Correct and typed, but a large compiled dependency for five function calls. Convenience alone does not qualify under Principle V. |
| Data-protection keychain (`kSecUseDataProtectionKeychain`) | Requires code-signing entitlements (`keychain-access-groups`) that a Python script cannot carry. The login keychain is the only option for an unsigned CLI. |

**Consequence to document**: items in the login keychain trust the *application* that
created them, and for this tool that application is the Python interpreter binary. A
different interpreter path (after `uv tool upgrade` changes the managed Python, or when
running from a dev checkout) triggers a one-time macOS authorization prompt. This is expected
OS behavior, not a defect, and belongs in the README troubleshooting section.

---

## R-002: Keychain item layout and ownership stamp

**Decision**: Each variable is one generic-password item with these attributes:

| Attribute | Value | Purpose |
|---|---|---|
| `kSecClass` | `kSecClassGenericPassword` | Item class |
| `kSecAttrService` | `keychain-cli:<namespace-key>` | Namespace grouping; exact-match key |
| `kSecAttrAccount` | `<VAR_NAME>` | Variable name; case-sensitive |
| `kSecAttrCreator` | FourCharCode `kccl` (0x6B63636C) | Ownership stamp; enumeration key |
| `kSecAttrGeneric` | UTF-8 bytes of the namespace display name | Preserves first-given casing (FR-007b) |
| `kSecAttrLabel` | `keychain-cli: <Display>/<VAR>` | Human-readable name in Keychain Access |
| `kSecValueData` | UTF-8 bytes of the value | The secret |

`<namespace-key>` is the namespace name lowercased. `(service, account)` is unique within
a keychain, so `SecItemAdd` returns `errSecDuplicateItem` for an existing variable, which
maps directly onto overwrite protection (FR-006).

**Rationale**: `kSecAttrCreator` is an exact-match filter, **verified by probe**, and gives
"list everything this tool owns" in one attribute-only query that requests no secret data
and therefore raises no authorization prompt. Service prefix alone would not suffice
because `SecItemCopyMatching` has no prefix match.

**Alternatives considered**: storing display casing in the label and parsing it back
(fragile; label is for humans); a single "index" item listing namespaces (a second source
of truth that can drift; forbidden as an index under Principle III).

---

## R-003: Namespace case handling

**Decision**: Normalize to lowercase for every lookup and for the service attribute. Store
the first-given casing in `kSecAttrGeneric` on every item in the namespace. When adding a
variable to a namespace that already exists, copy the existing display name rather than the
casing typed in this invocation. Listing shows the display name.

**Rationale**: FR-007a restricts names to ASCII, so `str.lower()` is unambiguous. Keychain
attribute matching is case-sensitive and `kSecMatchCaseInsensitive` is not documented to
apply to `kSecAttrService`, so normalization must happen in the tool.

**Alternatives considered**: `kSecMatchCaseInsensitive` (unreliable for this attribute);
rejecting mixed case entirely (worse ergonomics for no security gain).

---

## R-004: Launching the target command (`run`)

**Decision**: Build the child environment as a copy of `os.environ` with namespace values
overlaid, then replace the current process with `os.execvpe(argv[0], argv, env)`. No shell
is invoked. The command list is exactly what follows `--` on the tool's command line.

**Rationale**: `exec` satisfies four requirements at once with zero code: the exit status is
the child's (FR-023); signals reach the child directly because it *is* the process (FR-024);
no orphan is possible; stdio is untouched (FR-026). Secret material leaves Python memory the
instant the image is replaced, meeting Principle IV. The parent shell is never modified
(FR-021). **Verified**: CPython's `execvpe` resolves the executable using `PATH` from the
*new* environment, which inherits the parent's `PATH` unless the namespace overrides it.

`FileNotFoundError` / `PermissionError` from `execvpe` are raised **before** the image is
replaced, so a missing command maps to exit code 8, distinguishable from a Keychain failure
(spec Story 2, scenario 6).

**Alternatives considered**: `subprocess.run` with signal forwarding (more code, a window
where both processes hold the secrets, orphan risk on SIGKILL of the parent);
`subprocess` with `shell=True` (forbidden by the user constraint; also an injection surface).

---

## R-005: Argument parsing and the `--` separator

**Decision**: `argparse` from the standard library, with one pre-processing step: the CLI
splits `sys.argv` at the first literal `--` **before** handing the head to argparse and
treats everything after it as the command for `run`. `run` rejects invocation without `--`
(exit 2) with a message showing the correct form.

**Rationale**: **Verified**: with `nargs=REMAINDER`, argparse consumes the `--` itself, so
`run -- npm run dev` (namespace omitted, to be inferred from a manifest) misparses `npm` as
the namespace. Splitting first removes the ambiguity and keeps `--` mandatory, which the spec
edge case on missing separators also asks for.

**Alternatives considered**: `click` or `typer` (external dependencies; convenience only);
`nargs=REMAINDER` without pre-splitting (misparses the omitted-namespace form).

---

## R-006: Hidden interactive input and confirmations

**Decision**: `getpass.getpass()` for secret values, prompting on stderr. **Verified**: it
opens `/dev/tty` directly, so it works even when stdin is redirected. `sys.stdin.isatty()`
decides interactive versus non-interactive for confirmations and for FR-004a stdin mode.
Confirmations read one line from `/dev/tty`, default No.

**Rationale**: standard library; suppresses echo and shows no length indicator (FR-003).

**Stdin mode rule (FR-004a)**: engaged when `--stdin` is passed **or** stdin is not a TTY.
Exactly one variable name must be given, checked before any read. Read all of stdin as
UTF-8, strip exactly one trailing `\n` (and a preceding `\r` if present). Empty result is
an error (exit 7) because there is no way to confirm intent.

---

## R-007: Overwrite protection semantics

**Decision**: `set` and `import` attempt `SecItemAdd` first. On `errSecDuplicateItem`, the
tool either fails with exit 4 (non-interactive, no `--force`), prompts (interactive, no
`--force`), or calls `SecItemUpdate` (`--force` or confirmed). For `import`, existing keys
are collected and confirmed **once** as a named list, not per entry, addressing the spec
edge case on large files. Declined confirmation leaves everything unchanged and exits 4.

---

## R-008: `.env` parsing rules

**Decision**: Hand-written parser in the standard library. Rules, documented in `--help`
and README:

- Blank lines and lines whose first non-space character is `#` are ignored.
- Optional leading `export `.
- `KEY=value`; key must satisfy the variable-name rule or the line is malformed.
- Values in matching single or double quotes have the quotes removed; inside double quotes,
  `\n`, `\t`, `\\`, `\"` escapes are interpreted; inside single quotes nothing is.
- Unquoted values have surrounding whitespace stripped, and a trailing ` #...` comment
  (space before `#`) removed.
- **Single-line only.** A quoted value whose closing quote is missing on the same line is
  malformed. Multi-line values are not supported in this release; the spec edge case is
  satisfied by rejecting them with a line number, not by parsing them.
- Duplicate keys: last occurrence wins; the summary reports the collapsed name.
- Malformed lines are reported by line number and, if a plausible key was found before the
  `=`, by that key. Line content is never printed (FR-012).

**Alternatives considered**: `python-dotenv` (external dependency, and its parser prints
warnings that could include line content).

---

## R-009: Manifest format and discovery

**Decision**: `.keychain-cli.toml` in the **current directory only**; no upward search.
Parsed with `tomllib` (Python 3.11+). Schema:

```toml
namespace = "client-a"
variables = ["API_TOKEN", "DB_PASSWORD"]
```

Both keys required; `variables` may not be empty; every name must be a valid variable name;
unknown keys are rejected. See [contracts/manifest.md](contracts/manifest.md).

**Rationale**: current-directory-only is the simplest predictable rule (Principle I) and
matches how `.env` loaders behave, which is the mental model being replaced. Upward search
can be added later without breaking anything; removing it later would be breaking.

---

## R-010: Clipboard copy and auto-clear (Story 7, optional capability)

**Decision**: Write the value to `/usr/bin/pbcopy` via its **stdin**. Spawn a detached
helper (`python -m keychain_cli._clipclear`, `start_new_session=True`, stdio to
`/dev/null` except a stdin pipe) and pass it, over that pipe, the SHA-256 of the value and
the interval. The helper sleeps for the interval, reads the clipboard via `pbpaste` stdout,
and clears it with `pbcopy` **only if** the hash matches. The parent exits immediately.

**Timeout**: default 45 seconds, overridable with `--clear-after SECONDS`, bounded to
1–300. The bound is validated before anything is copied. This is the one configurable
option in the tool; the spec (FR-019a, FR-019e) requires it, and the bound plus the secure
default satisfy Principle I's test that an option must not be a way to be insecure: the
worst case is five minutes, and there is no way to disable clearing.

**Fail closed**: if the helper cannot be spawned or fed, the command immediately runs
`pbcopy` with empty input to clear the clipboard and exits 9. The value is never left on
the clipboard without a scheduled clear (FR-019e).

**Warning**: the confirmation line always carries the caveat that clipboard managers,
history tools, and sync services may retain the value after clearing (FR-019f). It is not
suppressible.

**Isolation**: `clipboard.py` is imported only by `commands/copy.py`; a unit test asserts
no other module imports it and that no other command's code path spawns `pbcopy`
(FR-019b).

**Rationale**: no secret in any `argv`; the helper holds only a hash during the wait, so it
cannot leak the value if it is dumped; the hash comparison implements "clear only if still
ours" without a compiled AppKit binding.

**Constitution exception**: the clipboard is an exposure channel readable by every app
running as the user, and by clipboard managers and Universal Clipboard sync. Because the
copy command's *purpose* is that exposure, this plan records it as exception **CLIP-001** in
the security exception register, with a pinning test asserting the value reaches only
`pbcopy` stdin, and re-evaluation trigger "macOS offers a CLI-accessible transient
pasteboard API". **Maintainer approval is required before Story 7 is implemented.** Because
FR-019a is a MAY, declining the exception simply omits the command; nothing else changes.

**Documentation placement** (FR-019h): `copy` is excluded from the README walkthrough and
the quickstart's primary path. It lives in a separate "Occasional: pasting a value into a
web console" section with the full caveat.

**Alternatives considered**: `NSPasteboard.changeCount` via `ctypes`/`objc_msgSend` (avoids
reading the clipboard back, but the Objective-C runtime bridge is the least readable code
in the project for a P3 story); a fixed, non-configurable interval (rejected by the spec's
FR-019e); unbounded or zero timeout (a way to disable clearing; rejected).

---

## R-011: Exit codes

**Decision**: fixed table, documented in `--help` and README. See
[contracts/cli.md](contracts/cli.md#exit-codes). For `run`, after `exec` the exit status is
entirely the child's and may collide with this table; that is inherent and documented.

---

## R-012: Testing strategy and Keychain isolation

**Decision**:

- **Unit tests** (`tests/unit/`): the CLI takes a `SecretStore` implementation through a
  seam; tests inject an in-memory fake. Prompts, `execvpe`, and subprocess spawning are also
  injected so tests can assert exact `argv` and environment contents.
- **Integration tests** (`tests/integration/`, marker `integration`, macOS only): exercise
  the real `ctypes` backend against a **temporary keychain** created with
  `SecKeychainCreate` under a temp directory and deleted with `SecKeychainDelete` in
  teardown. **Verified by probe.** The backend accepts an optional keychain handle and adds
  `kSecUseKeychain` / `kSecMatchSearchList` when given one. The developer's login keychain
  is never touched by the test suite.
- **Leak tests** (Principle VII): every command is run end-to-end via `subprocess` with a
  distinctive placeholder value, and stdout, stderr, and recorded `argv` of every spawned
  process are asserted not to contain it. A test asserts `repr()`/`str()` of every
  exception and of the `SecretValue` type never includes the value.
- **CI**: GitHub Actions on `macos-latest`, Python 3.11 and 3.14, running lint, format
  check, type check, unit and integration tests, lockfile check, dependency audit, and
  secret scan. The Keychain on hosted runners is usable because tests use their own
  temporary keychain.

**Dev-only dependencies** (none at runtime), each justified per Principle V:

| Tool | Why not stdlib |
|---|---|
| `pytest` | Fixtures, parametrization, and `capsys` make leak assertions short and readable; `unittest` equivalents triple the boilerplate. Dev-only; never installed with the tool. |
| `ruff` | Constitution VI requires automated format and lint in CI; no stdlib equivalent. |
| `mypy` (strict) | `ctypes` bindings are the riskiest code; type checking catches wrong `argtypes`/`restype` wiring. |
| `pip-audit` | Constitution V requires a vulnerability scan; run via `uvx`, not installed in the env. |

---

## R-013: Packaging and installation

**Decision**: `pyproject.toml` with the `uv_build` backend, `requires-python = ">=3.11"`,
no runtime dependencies, `[project.scripts] keychain-cli = "keychain_cli.cli:main"`, and
a committed `uv.lock`. Install with `uv tool install keychain-cli` (PyPI, later) or
`uv tool install git+https://github.com/civicactions/keychain-cli` (works immediately).

**Startup guard**: before any Security import, exit 6 unless `sys.platform == "darwin"`,
`platform.mac_ver()` major is at least 13, and Python is at least 3.11. macOS 13 is the
stated and tested floor; the APIs used exist since 10.6, so the floor is a support
statement, not an API constraint.

**Performance (SC-007)**: loading two frameworks through `ctypes` and one attribute query
costs tens of milliseconds; Python startup dominates. Import `clipboard`, `manifest`, and
`envfile` lazily inside their commands so `run` pays for nothing it does not use.

---

## R-014: Locked keychain and headless sessions

**Decision**: map `errSecInteractionNotAllowed` (-25308), `errSecAuthFailed` (-25293),
`errSecUserCanceled` (-128), and any other non-zero `OSStatus` to exit 5 with a message
naming the condition and the next step, using `SecCopyErrorMessageString` for the OS text.
No command is launched and no partial state is written (FR-040).

**Rationale**: when the login keychain is locked, the Security framework shows a GUI unlock
dialog; over SSH there is no GUI and the call fails. Both cases must fail closed.

---

## Resolved items carried from the spec checklist

| Item | Resolution |
|---|---|
| Manifest parent-directory search | Not searched; current directory only (R-009). |
| Clipboard in the exception register | Yes, as CLIP-001, approval required before Story 7 (R-010). |
| Storage identification scheme | Creator stamp + service prefix, verified (R-001, R-002). |
| Interpreter-path authorization prompts | Documented in README troubleshooting (R-001). |
| Command shape | `list` bare lists namespaces; `list <ns>` lists variables (contracts/cli.md). |

No `NEEDS CLARIFICATION` markers remain.
