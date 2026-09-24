# Implementation Plan: Keychain Secret Manager

**Branch**: `001-keychain-secret-manager` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-keychain-secret-manager/spec.md`, plus the
planning constraints supplied with the `/speckit.plan` request (Python 3 CLI managed with
`uv`, macOS only, no secrets in `argv`, no shell for `run`, lowercase-normalized namespaces,
mockable Keychain layer, macOS integration tests, installable with `uv tool install`).

## Summary

A small Python CLI that replaces plaintext `.env` files with secrets stored in the macOS
Keychain. Values enter through hidden prompts or stdin, are stored as generic-password items
stamped with a tool-specific creator code, and are delivered to a target process by
`exec`-ing that process with the namespace overlaid on its environment. The Keychain is
driven directly through the Security framework via `ctypes`, so no secret ever passes
through `argv`, a shell, a temp file, or a log. All research decisions are in
[research.md](research.md); every one that carried risk was verified by a runnable probe
against a throwaway keychain.

## Technical Context

**Language/Version**: Python 3.11+ (`tomllib` floor). Developed and CI-tested on 3.11 and
3.14.

**Primary Dependencies**: none at runtime. Standard library only: `ctypes`, `argparse`,
`getpass`, `os`, `subprocess`, `tomllib`, `json`, `hashlib`. Dev-only: `pytest`, `ruff`,
`mypy`, `pip-audit` (justified in research R-012).

**Storage**: macOS login Keychain via Security.framework (`SecItemAdd`,
`SecItemCopyMatching`, `SecItemUpdate`, `SecItemDelete`). Item layout in research R-002
and [data-model.md](data-model.md).

**Testing**: `pytest`. Unit tests against an in-memory `SecretStore`; integration tests
(marker `integration`) against the real backend targeting a temporary keychain created with
`SecKeychainCreate`. Leak tests run every command end to end and assert placeholder values
are absent from stdout, stderr, and every recorded `argv`.

**Target Platform**: macOS 13+ on Apple silicon and Intel. Exits with code 6 elsewhere.

**Project Type**: single-package CLI, `src/` layout, `uv_build` backend, installable with
`uv tool install`.

**Performance Goals**: added latency for `run` under 1 second (SC-007); expected well under
200 ms. Lazy imports for `manifest`, `envfile`, `clipboard`.

**Constraints**: no secret in `argv`, logs, temp files, exceptions, or error output; no
shell for `run`; fail closed on any Keychain error; owner-only permissions on any created
file (the tool creates none in this release).

**Scale/Scope**: single developer's Keychain; tens of namespaces, hundreds of variables.
Eight commands, roughly 1,500 lines of source plus tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle | Status | Evidence in this plan |
|---|---|---|
| I. Security and simplicity over breadth | PASS | Zero runtime deps; `exec` instead of process supervision; manifest current-directory only; two additions beyond the spec's minimum (`list --all`, bounded `copy --clear-after`), both justified in Complexity Tracking. |
| II. Secrets never surface (NON-NEGOTIABLE) | PASS with one registered exception | Keychain via `ctypes` keeps values in memory (R-001). `pbcopy` and the clear helper receive data on stdin (R-010). `SecretValue` redacts `repr` and never rides on exceptions (data-model). Exception **CLIP-001** for the optional clipboard command must be approved and registered before Story 7 is implemented; declining it omits the command (FR-019a is a MAY). |
| III. Keychain is the system of record | PASS | No cache, index, or mirror; namespace listing is a live attribute query (R-002). Non-macOS exits 6 before any storage code loads. `security` CLI not used at all. |
| IV. Least privilege | PASS | `run` delivers only to the exec'd process; parent shell untouched. Attribute-only queries for every listing so no secret data is read unless needed. `exec` drops all secret memory. No files created. |
| V. Standard library first | PASS | Runtime is stdlib only. Four dev-only tools each justified in R-012. `uv.lock` committed; `pip-audit` in CI. |
| VI. Readable, testable, maintainable | PASS | `SecretStore` protocol is the single seam to the Keychain; prompts, `execvpe`, and `Popen` are injected. `ruff` + `mypy --strict` in CI. Exit codes and commands documented in [contracts/cli.md](contracts/cli.md). |
| VII. Security behavior is tested (NON-NEGOTIABLE) | PASS | Leak tests on success and failure paths, `argv` assertions for every spawned process, fail-closed exit-code tests, malformed-input tests for `.env`, manifest, names, and Keychain status codes. Integration suite on a temp keychain runs in CI. |
| VIII. Fail safely | PASS | Every `OSStatus` maps to exit 5 with OS message and next step (R-014). Nothing launched or written on any error. Destructive ops require confirmation or `--force`. Stable exit-code table. |
| IX. Usable by default | PASS | Preferred command shape adopted verbatim. Common tasks are one invocation with no setup. `--help` requirements stated in the contract. README install-to-first-secret path is a deliverable. |
| Additional: threat model, exception register, CI gates | PASS (deliverables) | `docs/threat-model.md`, `SECURITY-EXCEPTIONS.md`, and `.github/workflows/ci.yml` are part of this feature's structure below. |

**Gate result**: no unjustified violation. The one Principle II exception uses the
constitution's own exception process and is gated on maintainer approval.

## Project Structure

### Documentation (this feature)

```text
specs/001-keychain-secret-manager/
├── spec.md
├── plan.md                    # this file
├── research.md                # Phase 0: decisions R-001 … R-014
├── research/
│   └── keychain-probe.py      # runnable ctypes probe that verified R-001/R-002/R-012
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/
│   ├── cli.md                 # commands, flags, streams, exit codes
│   └── manifest.md            # .keychain-cli.toml schema
├── checklists/
│   └── requirements.md
└── tasks.md                   # Phase 2 (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
pyproject.toml                 # uv_build backend, requires-python >=3.11, no runtime deps
uv.lock
README.md                      # install → first secret path; troubleshooting (auth prompts)
CHANGELOG.md
SECURITY.md                    # disclosure contact, supported versions
SECURITY-EXCEPTIONS.md         # exception register; CLIP-001 once approved
docs/
└── threat-model.md

src/keychain_cli/
├── __init__.py                # __version__
├── __main__.py                # python -m keychain_cli
├── cli.py                     # argv split on '--', argparse tree, dispatch, exit-code mapping
├── errors.py                  # exception hierarchy ↔ exit codes; never carries secrets
├── platform_check.py          # macOS 13+ / Python 3.11+ guard, exit 6
├── names.py                   # namespace + variable validation, lowercase key
├── secret.py                  # SecretValue with redacted repr
├── prompt.py                  # getpass wrapper, confirm(), is_interactive(), stdin reader
├── output.py                  # stdout/stderr helpers, --json emitter, StoreReport printer
├── envfile.py                 # .env parser (R-008); returns EnvFileParse
├── manifest.py                # tomllib loader + validation (contracts/manifest.md)
├── clipboard.py               # pbcopy via stdin; spawns _clipclear (Story 7)
├── _clipclear.py              # detached helper: sleep, hash-compare, clear
├── keychain/
│   ├── __init__.py            # SecretStore protocol, Namespace, store exceptions
│   ├── _cf.py                 # CoreFoundation ctypes bindings + Python converters
│   ├── _sec.py                # Security.framework bindings, constants, OSStatus → message
│   └── store.py               # SecurityFrameworkStore(keychain=None)
└── commands/
    ├── __init__.py
    ├── set_.py
    ├── list_.py
    ├── run.py                 # builds env, os.execvpe
    ├── import_.py
    ├── delete.py
    ├── init.py
    ├── check.py
    └── copy.py

tests/
├── conftest.py                # fixtures: InMemoryStore, fake prompt, recorded exec/Popen
├── fakes.py                   # InMemoryStore implementing SecretStore
├── unit/
│   ├── test_names.py
│   ├── test_secret_redaction.py
│   ├── test_envfile.py
│   ├── test_manifest.py
│   ├── test_cli_parsing.py    # '--' split, usage errors, exit codes
│   ├── test_cmd_set.py … test_cmd_copy.py
│   └── test_no_leaks.py       # every command, success + failure, placeholder absent
└── integration/               # marker: integration; macOS only
    ├── conftest.py            # temp keychain via SecKeychainCreate / SecKeychainDelete
    ├── test_store.py          # backend CRUD, duplicate, not-found, unicode round-trip
    ├── test_end_to_end.py     # subprocess-driven commands, env delivery, exit codes
    └── test_clipboard.py      # pbcopy/pbpaste, clear-only-if-ours

.github/workflows/
├── ci.yml                     # macos-latest × {3.11, 3.14}: ruff, mypy, pytest (unit+integration), uv lock --check, pip-audit, gitleaks
└── release.yml                # on tag: uv build, attach artifacts, changelog check
```

**Structure Decision**: single package with a `src/` layout. The `keychain/` subpackage is
the only code permitted to import `ctypes` bindings for Security or CoreFoundation, and
`commands/` depends only on the `SecretStore` protocol. This makes the constitution's
"single reader, single sitting" audit tractable: a security review reads `keychain/`,
`secret.py`, `prompt.py`, and `commands/run.py`, and everything else is plain data handling.

## Design notes that tasks must respect

1. **Namespace normalization**: `key = display.lower()` after FR-007a validation. Service
   attribute is `keychain-cli:<key>`. Display name is stored on every item and inherited by
   later items in the same namespace (R-003).
2. **Enumeration**: attribute-only queries filtered by creator stamp `kccl`; never request
   `kSecReturnData` in a list operation (R-002).
3. **`run`**: split argv at first `--` before argparse; build env; `os.execvpe`. Map
   `FileNotFoundError`/`PermissionError` to exit 8 (R-004, R-005).
4. **Overwrite**: try `add`, catch `AlreadyExists`, then confirm/force/refuse; `import`
   confirms once for the whole conflicting set (R-007).
5. **Stdin mode**: engaged by `--stdin` or non-TTY stdin; one variable only, checked before
   reading; strip one trailing newline; empty is exit 7 (R-006).
6. **Clipboard** (optional): gated on CLIP-001 approval; only `commands/copy.py` may import
   `clipboard.py`; helper receives hash and interval over stdin; default 45 s, `--clear-after`
   bounded 1–300 and validated before copying; helper spawn failure clears immediately and
   exits 9; confirmation always carries the clipboard-manager warning; excluded from primary
   README guidance (R-010).
7. **Test isolation**: integration tests always pass a temporary keychain handle; a test
   asserts the backend refuses to run integration fixtures without one.
8. **Exceptions**: store errors carry `OSStatus` and OS message only. A unit test walks the
   exception hierarchy and asserts no constructor accepts a `SecretValue`.

## Complexity Tracking

| Addition beyond the spec | Why needed | Simpler alternative rejected because |
|---|---|---|
| `list --all` flag | When a manifest is present in the current directory, bare `list` infers that namespace (FR-020a); the developer still needs a way to list namespaces from inside a project. | Making bare `list` always list namespaces would break inference consistency with `run`/`init`/`check`, violating Principle IX's "a flag means the same thing everywhere". Requiring `cd` elsewhere is friction, which Principle IX treats as a security risk. |
| Optional `keychain` handle on the backend | Integration tests must never touch the developer's login keychain, and CI runners need a keychain they own. | Running integration tests against the login keychain risks real data and prompts, and fails headless in CI. |
| `copy --clear-after SECONDS` (default 45, bounded 1–300) | Spec FR-019a/e require a configurable short timeout; some destinations need more than 45 s to reach the paste field. | A fixed interval contradicts the spec. An unbounded or zero value would be a way to disable clearing, which Principle I forbids; the bound and the non-disableable default keep the option from being a way to be insecure. |

No constitution violations to justify.

## Post-design Constitution re-check

Re-evaluated after writing data-model, contracts, and quickstart. Unchanged: PASS on all
nine principles. Two items require action before the corresponding tasks start, and are
recorded here so `/speckit-tasks` can sequence them:

- **CLIP-001** approval by a maintainer and entry in `SECURITY-EXCEPTIONS.md` before any
  `copy` command code is written (constitution II exception process).
- **Threat model** (`docs/threat-model.md`) drafted alongside the `keychain/` package,
  since that is the first storage interaction and Additional Constraints require it.

## Phase 2 handoff

Tasks should be ordered so the MVP (Stories 1 and 2: `set`, `run`, and the `keychain/`
backend with its integration tests) is complete and releasable before `list`, `import`,
`delete`, `init`/`check`, and `copy` follow, matching the priority order in the spec.
