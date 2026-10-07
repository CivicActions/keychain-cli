# Copilot instructions for keychain-cli

A security-focused macOS CLI that stores project secrets in the login Keychain and injects them
into a single command's environment. Python 3.11+, `uv`, no runtime dependencies.

Full detail lives in [CONTRIBUTING.md](../CONTRIBUTING.md). The essentials:

## Commit messages

Every commit and every pull request title must be a
[Conventional Commit](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <subject>
```

Allowed types, and nothing else: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`.

The subject is lowercase, imperative ("add", not "added"), and has no trailing period. Scopes in
use: `cli`, `keychain`, `manifest`, `clipboard`, `env`, `prompt`, `output`, `security`, `deps`,
`ci`.

Any change to a command name, flag, exit code, or output format is breaking — mark it with `!`
after the type/scope or a `BREAKING CHANGE:` footer. Security fixes use `fix(security): ...`, never
a `security:` type, because a non-standard type produces no version bump.

Pull requests are squash-merged, so the pull request title is what lands on `main` and what
Release Please parses. It must be valid on its own.

## Never edit versions or the changelog by hand

Release Please owns the version in `pyproject.toml`, `__version__` in
`src/keychain_cli/__init__.py`, the `keychain-cli` package version in `uv.lock`, the `"."` entry in
`.release-please-manifest.json`, and all of `CHANGELOG.md`. It rewrites them together in a release
pull request.

The `__version__` line carries a `# x-release-please-version` annotation — that comment is
load-bearing. Do not remove it. `tests/unit/test_version_sync.py` fails if these drift.

Regenerating `uv.lock` with `uv lock` after a dependency change is fine and expected; editing the
`version` under its `name = "keychain-cli"` entry is not.

## The security invariant

A secret value must never reach:

- `argv` (so: no secrets as command-line arguments, ever)
- log output, stdout, or stderr
- an exception message or traceback
- a temporary file or any file on disk

Secrets are read at a hidden prompt or from stdin, held in `SecretValue` (which has a redacted
`repr` and refuses to be formatted), and written to the Keychain through the Security framework via
`ctypes` — never by shelling out to the `security` command, whose arguments would be visible in the
process table.

Deliberate exceptions require an entry in
[SECURITY-EXCEPTIONS.md](../SECURITY-EXCEPTIONS.md); `CLIP-001` (clipboard copy) is the worked
example. The threat model is in [docs/threat-model.md](../docs/threat-model.md).

## Code conventions

- `from __future__ import annotations` at the top of every module.
- Fully type-annotated; `mypy` runs in `strict` mode over `src` and `tests`.
- `ruff` with a 100-character line length; `pylint` must score at least 8.0.
- Errors derive from the hierarchy in `src/keychain_cli/errors.py` and map to the documented exit
  codes (0–10, 130) in the README. Adding or changing one is a breaking change.
- Unit tests run against `InMemoryStore` in `tests/fakes.py`. Integration tests are marked
  `@pytest.mark.integration` and must use a temporary keychain, never the login keychain.
