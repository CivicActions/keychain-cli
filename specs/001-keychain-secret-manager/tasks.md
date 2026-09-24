# Tasks: Keychain Secret Manager

**Input**: Design documents from `/specs/001-keychain-secret-manager/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md,
contracts/manifest.md, quickstart.md

**Tests**: INCLUDED. The constitution's Principle VII (NON-NEGOTIABLE) requires tests for
every security-relevant behavior in the same change set, and spec SC-002 and SC-006 require
automated proof that no secret surfaces. Test tasks precede implementation within each
story and must fail before the implementation task lands.

**Organization**: Grouped by user story in spec priority order (US1, US2 = P1; US3, US4,
US5 = P2; US6, US7 = P3). Each story phase is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US7) for story-phase tasks only
- Every task names the exact file path it touches

## Path Conventions

Single project, `src/` layout: `src/keychain_cli/`, `tests/unit/`, `tests/integration/`.
Exit codes, flags, and messages are defined in `contracts/cli.md` and are not restated in
every task; "per contract" means that file.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Installable, lint-clean, CI-gated empty package.

- [ ] T001 Create `pyproject.toml` at repo root: `[build-system]` using `uv_build`; `[project]` name `keychain-cli`, `requires-python = ">=3.11"`, no runtime dependencies, `[project.scripts] keychain-cli = "keychain_cli.cli:main"`; dev dependency group `pytest`, `ruff`, `mypy`; `[tool.pytest.ini_options]` registering marker `integration`; `[tool.ruff]` with `select = ["ALL"]` minus documented ignores; `[tool.mypy] strict = true`
- [ ] T002 Create package skeleton `src/keychain_cli/__init__.py` (with `__version__ = "0.1.0"`), `src/keychain_cli/__main__.py` (calls `cli.main()`), `src/keychain_cli/commands/__init__.py`, `src/keychain_cli/keychain/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- [ ] T003 Run `uv sync` and commit `uv.lock`; verify `uv run keychain-cli --version` fails only because `cli.py` does not exist yet
- [ ] T004 [P] Create `.github/workflows/ci.yml`: matrix `macos-latest` × Python `3.11`, `3.14`; steps `uv sync`, `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, `uv run pytest -m "not integration"`, `uv run pytest -m integration`, `uvx pip-audit`, and a secret-scan step (gitleaks action)
- [ ] T005 [P] Create `SECURITY-EXCEPTIONS.md` with the register table (columns: ID, code path, exposure window, observer, why no alternative, approving maintainer, pinning test, re-evaluation trigger) and no rows; add `SECURITY.md` with disclosure contact placeholder and supported-versions statement; add `CHANGELOG.md` with an `Unreleased` section
- [ ] T006 [P] Create `README.md` stub with sections: What it is, Install (`uv tool install`), First secret in 60 seconds, Commands, Exit codes, Troubleshooting (interpreter-path authorization prompt from research R-001), Security notes. Fill Install and Troubleshooting now; leave other sections as headings to complete in Phase 10
- [ ] T007 [P] Create `.gitignore` for Python/uv (`.venv/`, `dist/`, `__pycache__/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`) and a `.gitleaks.toml` allowlisting the placeholder token pattern `LEAKCHECK-` used by tests

**Checkpoint**: `uv sync` succeeds, CI workflow file is valid YAML, no source yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Everything every command depends on: platform guard, errors and exit codes,
secret type, name rules, prompts, output, the Keychain backend behind its protocol, the CLI
dispatcher, and the test fixtures.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Core types and rules

- [ ] T008 [P] Implement `src/keychain_cli/errors.py`: base `KeychainCliError(message, next_step, exit_code)`; subclasses `UsageError`(2), `NotFoundError`(3), `RefusedError`(4), `KeychainError`(5, carries `os_status: int` and `os_message: str`), `UnsupportedPlatformError`(6), `InvalidInputError`(7), `CommandNotFoundError`(8), `ClipboardError`(9); `format_error()` producing `keychain-cli: <what failed>. <what to do next>`; no constructor accepts bytes or a `SecretValue`
- [ ] T009 [P] Implement `src/keychain_cli/secret.py`: `SecretValue` wrapping `data: bytes`; `__repr__` and `__str__` return exactly `SecretValue(<redacted>)`; `__eq__` by bytes; `from_text(str)` encodes UTF-8; `__format__` raises `TypeError` so f-strings cannot leak it
- [ ] T010 [P] Implement `src/keychain_cli/names.py`: `validate_namespace(display) -> Namespace` enforcing `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` and returning `Namespace(key=display.lower(), display=display)`; `validate_variable(name)` enforcing `^[A-Za-z_][A-Za-z0-9_]*$`; both raise `InvalidInputError` whose message states the allowed form; `Namespace` dataclass (frozen) lives here
- [ ] T011 [P] Implement `src/keychain_cli/platform_check.py`: `ensure_supported()` raising `UnsupportedPlatformError` unless `sys.platform == "darwin"`, `platform.mac_ver()` major ≥ 13, and `sys.version_info >= (3, 11)`; message names the detected platform and the supported floor
- [ ] T012 [P] Implement `src/keychain_cli/prompt.py`: `is_interactive()` (`sys.stdin.isatty()`); `read_secret(prompt) -> SecretValue` via `getpass.getpass` writing the prompt to stderr; `confirm(question, *, default=False) -> bool` reading one line from `/dev/tty`; `confirm_exact(question, expected) -> bool`; `read_secret_from_stdin() -> SecretValue` reading all of `sys.stdin.buffer`, stripping exactly one trailing `\n` (and preceding `\r`), raising `InvalidInputError` on empty result. All prompt functions accept an injectable `tty` reader for tests
- [ ] T013 [P] Implement `src/keychain_cli/output.py`: `out(line)` to stdout, `err(line)` to stderr, `emit_names(names, json_mode)` printing one per line or a compact JSON array, `print_report(report: StoreReport)` rendering `stored:` / `skipped:` / `overwritten:` / `malformed:` / `duplicates:` lines to stderr, omitting empty categories; `StoreReport`, `MalformedLine`, `DuplicateKey` dataclasses per data-model.md

### Keychain backend

- [ ] T014 Define `src/keychain_cli/keychain/__init__.py`: `SecretStore` `Protocol` with methods exactly as data-model.md "SecretStore interface" (`list_namespaces`, `list_variables`, `exists`, `get`, `get_all`, `add`, `update`, `delete_variable`, `delete_namespace`); store exceptions `AlreadyExists`, `NotFound`, `StoreError(os_status, os_message)`; re-export `Namespace`
- [ ] T015 [P] Implement `src/keychain_cli/keychain/_cf.py`: CoreFoundation bindings via `ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")` with `argtypes`/`restype` for `CFStringCreateWithCString`, `CFDataCreate`, `CFNumberCreate`, `CFDictionaryCreate`, `CFArrayCreate`, `CFRelease`, `CFArrayGetCount`, `CFArrayGetValueAtIndex`, `CFDictionaryGetValue`, `CFGetTypeID`, `CFStringGetLength`, `CFStringGetCString`, `CFDataGetLength`, `CFDataGetBytePtr`; converters `cfstr`, `cfdata`, `cfnum32`, `cfdict`, `cfarray`, `to_str`, `to_bytes`; a `Released` context manager that releases every created object; use `research/keychain-probe.py` as the reference
- [ ] T016 [P] Implement `src/keychain_cli/keychain/_sec.py`: Security.framework bindings for `SecItemAdd`, `SecItemCopyMatching`, `SecItemUpdate`, `SecItemDelete`, `SecKeychainCreate`, `SecKeychainDelete`, `SecCopyErrorMessageString`; constants loaded with `in_dll` (`kSecClass`, `kSecClassGenericPassword`, `kSecAttrService`, `kSecAttrAccount`, `kSecAttrCreator`, `kSecAttrGeneric`, `kSecAttrLabel`, `kSecValueData`, `kSecReturnAttributes`, `kSecReturnData`, `kSecMatchLimit`, `kSecMatchLimitAll`, `kSecUseKeychain`, `kSecMatchSearchList`); status constants `ERR_DUPLICATE = -25299`, `ERR_NOT_FOUND = -25300`, `ERR_INTERACTION_NOT_ALLOWED = -25308`, `ERR_AUTH_FAILED = -25293`, `ERR_USER_CANCELED = -128`; `status_message(status) -> str`; `CREATOR_STAMP = 0x6B63636C`, `SERVICE_PREFIX = "keychain-cli:"`
- [ ] T017 Implement `src/keychain_cli/keychain/store.py`: `SecurityFrameworkStore(keychain: KeychainHandle | None = None)` implementing `SecretStore` per data-model.md KeychainItem mapping. Every query includes `kSecAttrCreator = CREATOR_STAMP`; list operations set `kSecReturnAttributes` and never `kSecReturnData`; `add` sets `kSecAttrGeneric` to the existing namespace display name if the namespace exists, else the given display; `delete_namespace` uses `kSecMatchLimitAll`; when `keychain` is given add `kSecUseKeychain` (writes) and `kSecMatchSearchList` (reads/deletes); map -25299 → `AlreadyExists`, -25300 → `NotFound`, anything else non-zero → `StoreError(status, status_message(status))`. No attribute dictionary or value is ever included in an exception
- [ ] T018 Implement `TemporaryKeychain` in `src/keychain_cli/keychain/store.py` (or `_sec.py`): context manager calling `SecKeychainCreate(path, password_bytes, prompt=False)` and `SecKeychainDelete` on exit, yielding a `KeychainHandle`. Used only by integration tests; documented as such

### CLI dispatcher

- [ ] T019 Implement `src/keychain_cli/cli.py`: `main(argv=None, *, store_factory=None, prompts=None, exec_fn=None, spawn_fn=None) -> int`; call `platform_check.ensure_supported()` first; split `argv` at the first literal `--` into `head` and `command_tail` before argparse (research R-005); argparse tree with subcommands `set`, `list`, `run`, `import`, `delete`, `init`, `check`, `copy` and `--version`; dispatch to `commands/*`; catch `KeychainCliError` → print via `format_error()` to stderr and return its exit code; catch `StoreError` → exit 5 with OS message and next step; any other exception → exit 1 with a generic message and **no traceback** (traceback only when `KEYCHAIN_CLI_DEBUG=1`, and even then `SecretValue` repr is redacted)
- [ ] T020 Add a `resolve_namespace(explicit: str | None, *, allow_infer: bool) -> Namespace` helper in `src/keychain_cli/cli.py` that, for now, requires `explicit` and raises `UsageError` naming both ways to supply it when missing; manifest inference is wired in Phase 8

### Test fixtures

- [ ] T021 [P] Implement `tests/fakes.py`: `InMemoryStore` implementing `SecretStore` over `dict[tuple[str, str], tuple[str, SecretValue]]` keyed by `(namespace.key, name)`, honoring display-name inheritance and raising the same exceptions as the real store; `FakePrompts` with scripted answers and a record of prompts shown; `RecordingExec` and `RecordingSpawn` capturing `argv` and `env`
- [ ] T022 [P] Implement `tests/conftest.py`: fixtures `store` (InMemoryStore), `prompts`, `exec_fn`, `spawn_fn`, `run_cli(argv, stdin_text=None, tty=True)` returning `(exit_code, stdout, stderr)` by calling `cli.main` with injected seams and `capsys`; a `LEAK = "LEAKCHECK-7f3a-placeholder"` constant; helper `assert_no_leak(*texts)`
- [ ] T023 [P] Implement `tests/integration/conftest.py`: skip the whole directory unless `sys.platform == "darwin"`; fixture `temp_keychain` using `TemporaryKeychain` under `tmp_path`; fixture `real_store` returning `SecurityFrameworkStore(keychain=temp_keychain)`; fixture `cli_env` that runs the installed `keychain-cli` via `subprocess` with `KEYCHAIN_CLI_TEST_KEYCHAIN=<path>` so end-to-end tests also hit the temp keychain (the store factory honors that variable **only** when set, and `cli.py` logs a stderr notice when it is)

### Foundational tests

- [ ] T024 [P] Unit tests `tests/unit/test_names.py`: valid and invalid namespaces (empty, 65 chars, leading `-`, space, `!`, unicode), lowercase key derivation, display preserved, valid and invalid variable names (digit-first, hyphen, empty), case-distinct variables
- [ ] T025 [P] Unit tests `tests/unit/test_secret_redaction.py`: `repr`, `str`, `f"{v}"` (raises), `"{}".format(v)` (raises), `json.dumps` (raises), `SecretValue` inside every `errors.py` exception is rejected by type; `format_error()` output for each exception class contains no `LEAK`
- [ ] T026 [P] Unit tests `tests/unit/test_prompt.py`: stdin reader strips exactly one `\n` and one `\r\n`, keeps interior newlines, rejects empty and newline-only input with exit 7; `confirm` defaults No on empty line; `confirm_exact` accepts display or lowercase namespace
- [ ] T027 [P] Unit tests `tests/unit/test_cli_parsing.py`: `--` split for `run ns -- cmd`, `run -- cmd`, `run ns -- env -- x`; `run` without `--` → exit 2 with the correct form in stderr; unknown command → 2; `--version` prints version; non-darwin (monkeypatched `sys.platform`) → exit 6 before any Keychain import (assert `keychain_cli.keychain.store` not in `sys.modules`)
- [ ] T028 [P] Integration tests `tests/integration/test_store.py` against `real_store`: add/get round-trip for ASCII, multi-line, non-ASCII, 16 KiB value; `add` twice → `AlreadyExists`; `get` missing → `NotFound`; `list_variables` sorted and returns no data; `list_namespaces` returns display casing and groups by lowercase key; display inheritance when adding `Client-A` then `client-a`; `update`; `delete_variable`; `delete_namespace` count and subsequent `NotFound`; items without the creator stamp added directly via `_sec` are invisible to every method
- [ ] T029 Draft `docs/threat-model.md`: assets, trust boundaries, and the channels the constitution requires (other local processes reading `argv`/environment, other users on a shared host, backup/sync/crash-reporting of files at rest, shell history and scrollback, untrusted input reaching parsers), plus the interpreter-trust note from research R-001; mark sections to extend in Phases 5, 8, 9

**Checkpoint**: `uv run pytest` passes (unit + integration), `uv run keychain-cli --version` works, every command name is recognized and returns "not implemented" exit 1.

---

## Phase 3: User Story 1 — Store project secrets in the Keychain (Priority: P1) 🎯 MVP

**Goal**: `keychain-cli set <ns> VAR...` stores values via hidden prompt or stdin with
overwrite protection.

**Independent Test**: spec Story 1 independent test plus quickstart scenarios 1, 2, 5, 6.

### Tests for User Story 1

- [ ] T030 [P] [US1] Unit tests `tests/unit/test_cmd_set.py`: three variables prompted once each with prompt text `Value for <ns>/<VAR>:`; names validated before any prompt (invalid second name → exit 7, zero prompts shown); existing variable interactive → asks overwrite, `n` skips and exit 4, `y` updates and exit 0; `--force` updates without asking; non-interactive existing without `--force` → exit 4, value unchanged; empty value interactive → confirmation, declined → skipped; stdin mode with one var strips newline and stores; stdin mode with two vars → exit 7 before reading (stdin reader not called); summary lines list names only; duplicate variable in one invocation → exit 7
- [ ] T031 [P] [US1] Leak tests in `tests/unit/test_no_leaks.py` (create file): for `set` on success, on declined overwrite, on Keychain error (fake store raising `StoreError`), assert `LEAK` absent from stdout, stderr, and every exception `repr` captured by a wrapping handler
- [ ] T032 [P] [US1] Integration test `tests/integration/test_end_to_end.py::test_set_and_stdin` (create file): run installed CLI with stdin value into temp keychain, then read back with `real_store.get` and compare bytes; assert process stdout and stderr contain no value

### Implementation for User Story 1

- [ ] T033 [US1] Implement `src/keychain_cli/commands/set_.py`: `run_set(args, store, prompts) -> int` following research R-006 and R-007: validate namespace then all variable names (reject duplicates within the invocation), decide stdin vs interactive mode, collect values, `store.add` with `AlreadyExists` handling (confirm / `--force` / refuse), build `StoreReport`, return 0 if nothing skipped else 4
- [ ] T034 [US1] Wire `set` subparser in `src/keychain_cli/cli.py` with positionals `namespace`, `variables` (nargs `+`), flags `--force`, `--stdin`; help text with one example, the stdin rule, and exit codes per contract

**Checkpoint**: Story 1 passes its independent test; the tool already delivers value on its own.

---

## Phase 4: User Story 2 — Run a command with project secrets (Priority: P1) 🎯 MVP

**Goal**: `keychain-cli run <ns> -- cmd args` execs the command with the namespace in its
environment and nothing else changed.

**Independent Test**: spec Story 2 independent test plus quickstart scenario 3.

### Tests for User Story 2

- [ ] T035 [P] [US2] Unit tests `tests/unit/test_cmd_run.py` with `RecordingExec`: env passed to exec equals `os.environ` overlaid with namespace values (namespace wins on collision); `argv` passed to exec equals the tail after `--` verbatim including a second `--`; no shell in `argv[0]`; namespace missing → exit 3 and exec not called; store raising `StoreError` → exit 5 and exec not called; exec raising `FileNotFoundError` → exit 8 with message distinct from Keychain errors; exec raising `PermissionError` → exit 8; `run` with no `--` → exit 2
- [ ] T036 [P] [US2] Leak tests added to `tests/unit/test_no_leaks.py`: `run` failure paths (missing namespace, store error, command not found) contain no `LEAK`; the only place `LEAK` may appear is the recorded exec `env` dict, never in exec `argv`
- [ ] T037 [P] [US2] Integration tests in `tests/integration/test_end_to_end.py`: `run ns -- /usr/bin/env` output contains the variables; parent test process environment unchanged before and after; `run ns -- sh -c 'exit 42'` returns 42; `run ns -- no-such-cmd-xyz` returns 8; a child that sleeps receives SIGINT sent to the tool's PID and exits (no orphan: `pgrep` for the child finds nothing after)

### Implementation for User Story 2

- [ ] T038 [US2] Implement `src/keychain_cli/commands/run.py`: `run_run(args, command_tail, store, exec_fn) -> int`: raise `UsageError` if `command_tail` is empty; `values = store.get_all(ns)` (raises `NotFound` when the namespace has no variables); `env = {**os.environ, **{name: v.data.decode() for ...}}`; `exec_fn(command_tail[0], command_tail, env)` (`os.execvpe` by default); map `FileNotFoundError`/`PermissionError` → `CommandNotFoundError`; never invoke a shell
- [ ] T039 [US2] Wire `run` subparser in `src/keychain_cli/cli.py` with optional positional `namespace` and pass the pre-split `command_tail`; help text explains `--` and that exit status after launch is the command's own
- [ ] T040 [US2] Complete `README.md` "First secret in 60 seconds" section using `set` and `run` only, mirroring quickstart scenarios 1 and 3

**Checkpoint**: MVP complete. A developer can delete a `.env` file and keep working. Tag `0.1.0` candidate.

---

## Phase 5: User Story 3 — Import an existing .env file (Priority: P2)

**Goal**: `keychain-cli import <ns> <file>` loads a `.env` file with malformed-line
reporting that never shows content.

**Independent Test**: spec Story 3 independent test plus quickstart scenario 4.

### Tests for User Story 3

- [ ] T041 [P] [US3] Unit tests `tests/unit/test_envfile.py` covering every rule in research R-008: comments, blank lines, `export ` prefix, single and double quotes, escapes only inside double quotes, unquoted trailing ` #` comment, `#` inside quotes preserved, unterminated quote → malformed with line number and key, invalid key → malformed with line number and no key, duplicate keys → last wins with both line numbers recorded, CRLF line endings, empty file → zero entries, value with `=` inside, whitespace around `=`; assert `MalformedLine` never carries content
- [ ] T042 [P] [US3] Unit tests `tests/unit/test_cmd_import.py`: stores all valid entries; malformed warning format `line N: malformed entry` / `line N (KEY): malformed entry`; duplicate notice; existing keys collected and confirmed **once** with names listed; declined → all skipped, exit 4; `--force` overwrites; non-interactive without `--force` → skipped, exit 4; missing file → 3; directory → 7; unreadable (chmod 000) → 7; all lines malformed → 7; source file bytes and mtime unchanged after import; summary contains counts and names only
- [ ] T043 [P] [US3] Leak tests added to `tests/unit/test_no_leaks.py`: import a file whose malformed line **is** `LEAK`, and whose valid values are `LEAK`; assert absent from stdout and stderr on success, on decline, and on store error
- [ ] T044 [P] [US3] Integration test in `tests/integration/test_end_to_end.py`: import quickstart scenario 4's file into the temp keychain, then `run ns -- sh -c 'printf ...'` reproduces `one|override|single # not a comment|three`

### Implementation for User Story 3

- [ ] T045 [US3] Implement `src/keychain_cli/envfile.py`: `parse_env_file(path) -> EnvFileParse` per research R-008, reading bytes and decoding UTF-8 with `errors="strict"` (decode failure → `InvalidInputError` naming the line, not the bytes); raise `NotFoundError` for missing path, `InvalidInputError` for non-regular or unreadable file
- [ ] T046 [US3] Implement `src/keychain_cli/commands/import_.py`: `run_import(args, store, prompts) -> int`: parse; for each entry attempt `store.add`, collecting `AlreadyExists` names; if any, one confirmation (or `--force` / non-interactive refuse) then `store.update` for all; build `StoreReport` including malformed and duplicates; return 0 if nothing skipped, 4 otherwise, 7 if `entries` empty and `malformed` non-empty
- [ ] T047 [US3] Wire `import` subparser in `src/keychain_cli/cli.py` with positionals `namespace`, `file`, flag `--force`; help lists the parsing rules briefly and states the file is never modified
- [ ] T048 [US3] Extend `docs/threat-model.md` with the "untrusted input reaching the parser" section for `.env` files (hostile line content, huge files, binary files)

**Checkpoint**: Adoption path complete. A dozen-variable `.env` migrates in one command.

---

## Phase 6: User Story 4 — See which namespaces exist and what each holds (Priority: P2)

**Goal**: `keychain-cli list [<ns>] [--all] [--json]` shows names only, stably ordered.

**Independent Test**: spec Story 4 independent test plus quickstart scenario 1 and 6.

### Tests for User Story 4

- [ ] T049 [P] [US4] Unit tests `tests/unit/test_cmd_list.py`: variables one per line sorted by code point (`API_TOKEN` before `Api_Token`); `--json` emits compact array and nothing else on stdout; missing namespace → exit 3 with message not implying a value was withheld; bare `list` (no manifest) → namespaces in display casing sorted by lowercase key; zero namespaces → empty stdout, exit 0, empty stderr; `--all` lists namespaces; `--all` with a namespace positional → exit 2; namespace listing `--json`
- [ ] T050 [P] [US4] Integration test in `tests/integration/test_end_to_end.py`: store into `Client-A` and `other`, `list --all` prints `Client-A` then `other`; `list client-a` prints sorted variables; stdout contains no value

### Implementation for User Story 4

- [ ] T051 [US4] Implement `src/keychain_cli/commands/list_.py`: `run_list(args, store) -> int`: if `--all` or no namespace resolvable → `store.list_namespaces()` sorted by `key`, emit `display`; else `store.list_variables(ns)` sorted, `NotFound` → exit 3; use `output.emit_names(names, args.json)`
- [ ] T052 [US4] Wire `list` subparser in `src/keychain_cli/cli.py` with optional positional `namespace`, flags `--all`, `--json`; help explains bare form vs namespace form and that values are never shown

**Checkpoint**: The store is no longer write-only.

---

## Phase 7: User Story 5 — Remove a secret or a whole namespace (Priority: P2)

**Goal**: `keychain-cli delete <ns> [VAR] [--force]` with confirmation for namespace deletion.

**Independent Test**: spec Story 5 independent test plus quickstart scenario 9.

### Tests for User Story 5

- [ ] T053 [P] [US5] Unit tests `tests/unit/test_cmd_delete.py`: delete one variable removes only it, no confirmation; delete namespace interactive asks `Type the namespace name to confirm:` and proceeds only on exact display or lowercase match, wrong text → exit 4 nothing deleted; non-interactive without `--force` → exit 4; `--force` deletes; missing variable → 3; missing namespace → 3; deleting the last variable makes the namespace disappear from `list --all`; `delete` never consults a manifest (namespace positional required → exit 2 when absent)
- [ ] T054 [P] [US5] Integration test in `tests/integration/test_end_to_end.py`: three variables, delete one, two remain; `delete ns --force` removes all and `list --all` no longer shows it

### Implementation for User Story 5

- [ ] T055 [US5] Implement `src/keychain_cli/commands/delete.py`: `run_delete(args, store, prompts) -> int` per contract; count variables before namespace deletion so the confirmation names `N`; `store.delete_variable` / `store.delete_namespace`; `NotFound` → exit 3 with nothing changed
- [ ] T056 [US5] Wire `delete` subparser in `src/keychain_cli/cli.py` with required positional `namespace`, optional `variable`, flag `--force`; help states the confirmation rule and that the namespace is never inferred

**Checkpoint**: Full secret lifecycle. All P1 and P2 stories complete.

---

## Phase 8: User Story 6 — Set up a project from a committed manifest (Priority: P3)

**Goal**: `.keychain-cli.toml` drives `init` and `check`, and supplies the default
namespace for `run`, `list`, `init`, `check`.

**Independent Test**: spec Story 6 independent test plus quickstart scenario 7.

### Tests for User Story 6

- [ ] T057 [P] [US6] Unit tests `tests/unit/test_manifest.py`: valid manifest parses; missing file → `NotFoundError`; each of: missing `namespace`, missing `variables`, empty `variables`, non-string entry, invalid variable name, invalid namespace, duplicate variable, unknown top-level key, nested table, TOML syntax error → `InvalidInputError` naming the key or the parser position; the loader has no write path (assert module exposes no function accepting values)
- [ ] T058 [P] [US6] Unit tests `tests/unit/test_cmd_init_check.py`: `init` prompts only for missing variables in manifest order, existing untouched; all present → `namespace <name> is complete`, exit 0, zero prompts; non-interactive with missing → exit 7 listing names; malformed manifest → exit 7 and store unchanged; `check` prints missing names (and `--json`), exit 1 when missing, exit 0 when complete; manifest missing → exit 3 for both
- [ ] T059 [P] [US6] Unit tests `tests/unit/test_namespace_inference.py`: with manifest in cwd, `run -- cmd`, `list`, `init`, `check` use its namespace and print `using namespace <name> from .keychain-cli.toml` on stderr; explicit namespace wins and stderr prints `using namespace <explicit> (manifest declares <other>)`; no manifest and no namespace → exit 2 naming both remedies; manifest present but namespace has no stored values → `run` exit 3 with a message pointing at `init`; manifest in parent directory only is **not** found; `set`, `import`, `delete`, `copy` ignore the manifest
- [ ] T060 [P] [US6] Integration test in `tests/integration/test_end_to_end.py`: quickstart scenario 7 end to end in a temp cwd

### Implementation for User Story 6

- [ ] T061 [US6] Implement `src/keychain_cli/manifest.py`: `MANIFEST_NAME = ".keychain-cli.toml"`; `load_manifest(directory) -> Manifest` using `tomllib`, validating per `contracts/manifest.md` (required keys, types, non-empty, name rules via `names.py`, no duplicates, no unknown keys); `Manifest` frozen dataclass with `namespace: Namespace`, `variables: list[str]`; read-only module
- [ ] T062 [US6] Implement `src/keychain_cli/commands/init.py`: `run_init(args, store, prompts) -> int` and `src/keychain_cli/commands/check.py`: `run_check(args, store) -> int` per contract; `init` reuses the prompting and add logic from `set_.py` (extract a shared `store_values(...)` helper into `set_.py` if needed rather than duplicating)
- [ ] T063 [US6] Replace the Phase 2 stub `resolve_namespace` in `src/keychain_cli/cli.py`: when `explicit` is None and `allow_infer` is True, try `load_manifest(Path.cwd())`; on success return its namespace and print the inference notice; on `NotFoundError` raise `UsageError` naming both remedies; when `explicit` is given and a manifest declares a different namespace, print the mismatch notice; `allow_infer` is True only for `run`, `list`, `init`, `check`
- [ ] T064 [US6] Wire `init` and `check` subparsers in `src/keychain_cli/cli.py` (optional positional `namespace`; `check` has `--json`); update `run` and `list` help to mention manifest inference
- [ ] T065 [US6] Add a "Team setup with a manifest" section to `README.md` with the schema from `contracts/manifest.md` and the `init` / `check` flow; extend `docs/threat-model.md` with manifest parsing as an input path

**Checkpoint**: Onboarding and drift detection work; all namespace-inference behavior is tested.

---

## Phase 9: User Story 7 — Retrieve one value for use elsewhere (Priority: P3)

**Goal**: `keychain-cli copy <ns> VAR` puts one value on the clipboard and clears it after
45 seconds only if still present.

**Independent Test**: spec Story 7 independent test plus quickstart scenario 8.

**⚠️ GATE**: T066 must be complete and approved before any other task in this phase starts
(constitution Principle II exception process).

### Governance

- [ ] T066 [US7] Add exception **CLIP-001** to `SECURITY-EXCEPTIONS.md`: code path `commands/copy.py` → `clipboard.py` → `/usr/bin/pbcopy` stdin; exposure window 45 s or until overwritten; observers: any process running as the user, clipboard managers, Universal Clipboard; why no alternative: the command's purpose is to hand the value to another application; pinning test `tests/unit/test_clipboard.py::test_value_reaches_only_pbcopy_stdin`; re-evaluation trigger: macOS provides a CLI-accessible transient or app-scoped pasteboard. Obtain and record maintainer approval (name and date) in the row

### Tests for User Story 7

- [ ] T067 [P] [US7] Unit tests `tests/unit/test_clipboard.py` with `RecordingSpawn`: `copy_to_clipboard(value)` spawns exactly `["/usr/bin/pbcopy"]` and writes the bytes to its stdin; the clear helper is spawned as `[sys.executable, "-m", "keychain_cli._clipclear"]` with `start_new_session=True`, stdout/stderr `DEVNULL`, and receives `sha256hex + "\n" + "45\n"` on stdin; **pinning test** `test_value_reaches_only_pbcopy_stdin` asserts the value bytes appear in no spawned `argv` and only in the `pbcopy` stdin record; `pbcopy` non-zero exit → `ClipboardError` exit 9
- [ ] T068 [P] [US7] Unit tests `tests/unit/test_cmd_copy.py`: success prints `copied <ns>/<VAR> to clipboard; it will be cleared in 45 seconds` on stderr and nothing on stdout; missing variable → exit 3 and no spawn at all; more than one variable positional → exit 2; no wildcard or namespace-only form
- [ ] T069 [P] [US7] Integration tests `tests/integration/test_clipboard.py` (marker `integration`, additionally skipped when `DISPLAY`-less CI lacks a pasteboard server — detect by running `pbpaste` once): `copy` then `pbpaste` equals the placeholder; run `_clipclear` directly with interval `1` and matching hash → clipboard empty after 2 s; run with interval `1` after `pbcopy` of other text → other text survives; restore the prior clipboard content in teardown

### Implementation for User Story 7

- [ ] T070 [US7] Implement `src/keychain_cli/_clipclear.py`: `main()` reads two lines from stdin (hex digest, interval seconds); sleeps; runs `/usr/bin/pbpaste` capturing stdout; if `sha256(stdout) == digest` runs `/usr/bin/pbcopy` with empty stdin; exits 0 always; holds only the digest during the wait; no logging
- [ ] T071 [US7] Implement `src/keychain_cli/clipboard.py`: `CLEAR_AFTER_SECONDS = 45`; `copy_to_clipboard(value: SecretValue, spawn_fn) -> None` per research R-010; `schedule_clear(digest: str, spawn_fn)`; raise `ClipboardError` on any spawn or write failure with next step "copy something else to clear the clipboard"
- [ ] T072 [US7] Implement `src/keychain_cli/commands/copy.py`: `run_copy(args, store, spawn_fn) -> int`: `store.get(ns, name)` (exit 3 before any spawn), `copy_to_clipboard`, `schedule_clear`, confirmation message per contract
- [ ] T073 [US7] Wire `copy` subparser in `src/keychain_cli/cli.py` with required positionals `namespace`, `variable`; help text includes the full clipboard caveat from `contracts/cli.md` (readable by other apps, managers, sync; 45 s; residual exposure if killed)
- [ ] T074 [US7] Extend `docs/threat-model.md` with the clipboard channel and `README.md` Security notes with the same caveat and a link to `SECURITY-EXCEPTIONS.md`

**Checkpoint**: All seven stories complete.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T075 [P] Complete `README.md`: Commands section mirroring `contracts/cli.md` summaries, Exit codes table, minimum macOS 13 / Python 3.11 statement, `uv tool install` from git and from PyPI, uninstall
- [ ] T076 [P] Help-text audit: for every subcommand assert in `tests/unit/test_help.py` that `--help` output includes one example invocation, the exit codes it can return, and (for `copy`) the clipboard caveat; assert top-level `--help` lists all eight commands with one-line summaries
- [ ] T077 [P] Exit-code contract test `tests/unit/test_exit_codes.py`: parametrize every enumerated error condition in `contracts/cli.md` and assert the documented code; assert `errors.py` codes match the README table (parse the table)
- [ ] T078 [P] Performance check `tests/integration/test_perf.py`: `run ns -- /usr/bin/true` wall time under 1 s over 5 runs (SC-007); assert lazy imports by checking `sys.modules` after `run` excludes `keychain_cli.envfile`, `keychain_cli.manifest`, `keychain_cli.clipboard`
- [ ] T079 [P] Create `.github/workflows/release.yml`: on tag `v*`, `uv build`, verify `CHANGELOG.md` has a section for the tag, attach `dist/*` to a GitHub release
- [ ] T080 Finalize `docs/threat-model.md` (review every channel listed in the constitution's Additional Constraints; state that an attacker with code execution as the user is out of scope) and `SECURITY.md` disclosure contact
- [ ] T081 Run `quickstart.md` manually on a clean macOS user account using only `README.md` and `--help`, by someone other than the implementer (constitution usability gate); record findings in `specs/001-keychain-secret-manager/checklists/usability.md`
- [ ] T082 Update `CHANGELOG.md` `0.1.0` section (features, security notes, known limitations: single-line `.env` values, current-directory manifest only, clipboard exposure) and bump `__version__`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: no dependencies.
- **Phase 2 Foundational**: depends on Phase 1. **Blocks every story.**
- **Phases 3–9 (stories)**: each depends only on Phase 2, with two exceptions noted below.
- **Phase 10 Polish**: depends on all stories the release includes.

### User Story Dependencies

- **US1 set** (Phase 3): Foundational only.
- **US2 run** (Phase 4): Foundational only. Its integration tests store values through the
  real store fixture, not through `set`, so it does not depend on US1.
- **US3 import** (Phase 5): Foundational only. T062 later reuses a helper from `set_.py`;
  that is US6's dependency, not US3's.
- **US4 list** (Phase 6): Foundational only.
- **US5 delete** (Phase 7): Foundational only. Its "namespace disappears from list" test
  uses the store directly if US4 is not yet built.
- **US6 manifest** (Phase 8): depends on **US1** (shared prompting/add helper) and rewires
  `run` and `list` (US2, US4) for inference. Sequence after those three.
- **US7 copy** (Phase 9): Foundational only, gated on **T066 approval**.

### Within Each Story

Tests first and failing → module implementation → CLI wiring → docs. Commit per task or
per test/implementation pair.

### Parallel Opportunities

- Phase 1: T004–T007 in parallel after T001–T003.
- Phase 2: T008–T013 in parallel; T015 and T016 in parallel, then T017; T021–T029 in
  parallel once T014 exists.
- Stories: after Phase 2, US1, US2, US3, US4, US5 can proceed in parallel by different
  developers with no file overlap except `cli.py` wiring tasks (T034, T039, T047, T052,
  T056), which touch distinct subparser blocks and should be merged one at a time.
- Within any story, all `[P]` test tasks run in parallel.

---

## Parallel Example: Foundational Phase

```bash
# Batch A (no dependencies among them):
Task: "errors.py"            # T008
Task: "secret.py"            # T009
Task: "names.py"             # T010
Task: "platform_check.py"    # T011
Task: "prompt.py"            # T012
Task: "output.py"            # T013

# Batch B (after T014):
Task: "_cf.py"               # T015
Task: "_sec.py"              # T016
Task: "tests/fakes.py"       # T021
Task: "tests/conftest.py"    # T022

# Then T017 store.py, T018 TemporaryKeychain, T019 cli.py, T023 integration conftest,
# then T024–T029 in parallel.
```

## Parallel Example: User Story 1

```bash
Task: "tests/unit/test_cmd_set.py"                     # T030
Task: "tests/unit/test_no_leaks.py (set cases)"        # T031
Task: "tests/integration/test_end_to_end.py (set)"     # T032
# then T033 set_.py, then T034 cli wiring
```

---

## Implementation Strategy

### MVP First (User Stories 1 and 2)

1. Phase 1 Setup, Phase 2 Foundational.
2. Phase 3 (`set`) and Phase 4 (`run`).
3. **STOP and VALIDATE**: quickstart scenarios 1, 2, 3, 5, 6 pass; leak tests green;
   integration suite green on CI.
4. Tag `v0.1.0`. A developer can already delete a `.env` file.

### Incremental Delivery

1. `v0.2.0`: US3 `import`, US4 `list`, US5 `delete` (all P2; independent of each other).
2. `v0.3.0`: US6 manifest, `init`, `check`, namespace inference.
3. `v0.4.0`: US7 `copy`, only after CLIP-001 is approved.
4. Phase 10 polish rolls into whichever release is current; T081 usability check is
   required before the first release that is announced to the team.

### Parallel Team Strategy

Two developers: one takes Phase 2 Keychain backend (T014–T018, T023, T028) while the other
takes core types, prompts, CLI dispatcher, and unit fixtures (T008–T013, T019–T022,
T024–T027). After Phase 2, split stories: A takes US1 then US3 then US6; B takes US2 then
US4 then US5, then US7 once approved.

---

## Notes

- Every test that could touch a secret uses the `LEAK` placeholder constant and asserts
  its absence from all captured output. Never use a realistic-looking token in tests.
- `cli.py` is the one shared file; keep each subparser in its own clearly delimited block
  to minimize merge conflicts.
- No task creates a file at runtime. If one is ever added, it must use `os.open` with
  mode `0o600` at creation (constitution IV), and a test must assert the mode.
- Constitution review gate: every PR touching `keychain/`, `prompt.py`, `secret.py`,
  `commands/run.py`, `clipboard.py`, or `errors.py` needs the reviewer's explicit
  Principles II, IV, VII, VIII confirmation in the review text.
