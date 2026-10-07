---
name: "conventional-commits"
description: "Write Conventional Commit messages and pull request titles for keychain-cli, pick the right type and scope for an ambiguous change, and mark breaking changes correctly so Release Please computes the intended version."
compatibility: "Requires Release Please config at release-please-config.json"
metadata:
  author: "CivicActions"
  source: "CONTRIBUTING.md"
---

## When to use this

Use this skill whenever you are about to:

- write a commit message in this repository
- write or rename a pull request title
- decide whether a change is breaking
- work out why Release Please produced an unexpected version

The short version lives in `.github/copilot-instructions.md`; the authoritative version lives in
`CONTRIBUTING.md`. This skill is the reasoning guide for the cases those two don't settle.

## Why it matters here

Release Please parses the commit history on `main` to decide the next version, generate
`CHANGELOG.md`, tag the release, and cut the GitHub Release. A commit message is not documentation of
work that happened — it is **the input to an automated release**. Mislabel a user-visible fix as
`chore` and it ships to nobody, because `chore` produces no version bump and no changelog entry.

Pull requests are squash-merged, so **the pull request title is the commit that lands on `main`.**
Perfect commits on a branch do not rescue a malformed pull request title.

## Format

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer>
```

Subject rules: lowercase first letter, imperative mood, no trailing period, says what changes for
someone using the tool.

Note that the two enforcement gates differ. The local `commit-msg` hook
(`conventional-pre-commit`) checks only the type and header shape — it has no option for subject
casing. The `Commit Lint` workflow checks the pull request title and additionally rejects a
capitalised subject or a trailing period. Since pull requests are squash-merged, the title is the
message that survives; write both to the stricter standard.

## Picking a type

| Type | Version effect | Shows in changelog |
|---|---|---|
| `feat` | minor | yes |
| `fix` | patch | yes |
| `perf` | patch | yes |
| `docs` | none | yes |
| `revert` | none | yes |
| `refactor`, `test`, `build`, `ci`, `style`, `chore` | none | no |

No other type is accepted. The `commit-msg` hook and the `Commit Lint` workflow both reject
anything else.

### The decision that actually trips people up

Ask: **does a user of the installed tool observe a difference?**

- Yes, and it is new capability → `feat`
- Yes, and the old behaviour was wrong → `fix`
- Yes, and it is the same behaviour but faster → `perf`
- No → one of the silent types

Worked examples of the ambiguous cases:

| Change | Type | Why |
|---|---|---|
| Reword an error message a user sees | `fix` | Observable output changed; if it was misleading before, it was a defect |
| Reword a docstring | `docs` | Not observable from the CLI |
| Reword `--help` text | `docs` | Observable, but documentation is what it is |
| Add a new exit code | `feat!` | New capability **and** breaking — the exit-code table is contract |
| Correct an exit code that was wrong | `fix!` | A defect, but scripts branching on it break |
| Extract a helper, no behaviour change | `refactor` | Internal only |
| Add a test for existing behaviour | `test` | No shipped change |
| Add a test *and* the fix it covers | `fix` | Classify by the shipped change, not the diff size |
| Bump a dev dependency | `build(deps)` | Does not reach the published wheel |
| Add PyPI classifiers to `pyproject.toml` | `build` | Packaging metadata |
| Change a GitHub workflow | `ci` | Not shipped |

When a change genuinely spans two types, **split it into two commits**. If it cannot be split,
classify by the highest version effect: `feat` over `fix` over `perf` over everything silent.

## Scopes

Optional. Use one when it tells the reader where to look:

`cli`, `keychain`, `manifest`, `clipboard`, `env`, `prompt`, `output`, `security`, `deps`, `ci`

Prefer no scope over a vague one. `feat: add --json to list` beats `feat(stuff): add --json`.

## Breaking changes

`CHANGELOG.md` states the project's contract explicitly: **any change to a command name, flag, exit
code, or output format is breaking.** That is broader than most projects — a renamed flag or a
reordered `--json` key counts.

Two ways to mark it. Use `!` when the subject is self-explanatory:

```
feat(cli)!: rename --clear-after to --expire-after
```

Use a footer when a reader needs to know what to do about it. This is almost always the better
choice:

```
feat(cli): rename --clear-after to --expire-after

BREAKING CHANGE: `--clear-after` no longer exists. Scripts passing it fail with exit
code 2. Use `--expire-after`, which accepts the same 1-300 second range.
```

The footer must be the literal string `BREAKING CHANGE:` (uppercase, with the colon) at the start
of a line in the footer block. `Breaking change:` or `BREAKING-CHANGE` in the body will not be
detected, and the release will silently come out as a minor bump.

**Pre-1.0 behaviour:** the project is at `0.x`, and `release-please-config.json` sets
`bump-minor-pre-major: true`. A breaking change bumps `0.1.0` → `0.2.0`; it does not jump to
`1.0.0`. Both `feat` and breaking changes land on the minor, so during `0.x` the two are
indistinguishable in the version number — which is exactly why the `BREAKING CHANGE:` footer text
matters, since that is what a reader actually sees in the changelog.

## Security fixes

Always `fix(security): ...`. Never invent a `security:` type: it is not in the allowed list, so it
is rejected locally — and if it slipped through, it would produce no version bump, leaving the fix
unreleased.

Before committing anything security-relevant:

- If it warrants coordinated disclosure, follow `SECURITY.md` and do not open a public pull
  request.
- Never put the details of an unfixed vulnerability in a commit message.
- If the change deliberately bends the project's secret-handling rules, add an entry to
  `SECURITY-EXCEPTIONS.md` in the same change. `CLIP-001` is the worked example of the format.

## Checklist before committing

1. Is the type in the allowed list?
2. Does the type match the observable effect, not the size of the diff?
3. Lowercase subject, imperative, no trailing period?
4. Does the subject describe the change, not the file touched?
5. If it touches a command name, flag, exit code, or output format — is it marked breaking?
6. If this becomes the pull request title, does it still stand alone?
7. Did you leave `pyproject.toml` version, `__version__`, the `keychain-cli` version in `uv.lock`,
   `.release-please-manifest.json`, and `CHANGELOG.md` untouched?
