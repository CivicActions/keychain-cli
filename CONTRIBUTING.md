# Contributing to keychain-cli

Thanks for helping out. This project is security-focused and fully automated from commit to
published release, so two things matter more here than in most repositories: **how you word your
commits**, and **what you must never edit by hand**.

## The one rule that surprises people

Releases are automated. **Never hand-edit any of these:**

| File | Field |
|---|---|
| `pyproject.toml` | `[project] version` |
| `src/keychain_cli/__init__.py` | `__version__` |
| `uv.lock` | the `version` of the `keychain-cli` package entry |
| `.release-please-manifest.json` | the `"."` entry |
| `CHANGELOG.md` | anything |

[Release Please](https://github.com/googleapis/release-please) owns all five. It derives the next
version from your commit messages and rewrites them together in a release pull request. Editing one
by hand desynchronises them; `tests/unit/test_version_sync.py` will fail if you do.

`uv.lock` is the odd one out: you *do* regenerate it by hand whenever you change a dependency
(`uv lock`, then commit it). What you must not touch is the `version` under its
`name = "keychain-cli"` entry — `uv.lock` records the project's own version alongside its
dependencies, and `uv lock --check` in CI fails if that falls out of step with `pyproject.toml`.

## Development setup

```sh
uv sync
uv run pre-commit install --install-hooks
```

`pre-commit install` wires up three hook types: `pre-commit` (formatting and linting),
`commit-msg` (the Conventional Commit check), and `pre-push` (the Argus SAST scan).

Before opening a pull request, run the same checks CI runs:

```sh
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pylint src tests
uv run pytest -m "not integration"
uv run pytest -m integration    # macOS only; uses a temporary keychain, never your login keychain
```

## Commit messages

Every commit must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer>
```

The subject starts with a **lowercase** letter, uses the **imperative mood** ("add", not "added" or
"adds"), and does **not** end with a period.

### Types

| Type | Use it for | Version effect |
|---|---|---|
| `feat` | A new capability users can reach — a command, a flag, an output mode | **minor** |
| `fix` | A defect in released behaviour | **patch** |
| `perf` | A change that makes existing behaviour faster | **patch** |
| `docs` | README, this file, `docs/`, docstrings, help text wording | none |
| `refactor` | Restructuring with no change in behaviour | none |
| `test` | Adding or correcting tests only | none |
| `build` | Packaging, `pyproject.toml` metadata, dependencies, `uv.lock` | none |
| `ci` | Workflows under `.github/`, pre-commit config, Argus config | none |
| `style` | Formatting only — whitespace, import order | none |
| `chore` | Housekeeping that fits nothing above | none |
| `revert` | Reverting an earlier commit | none |

Nothing outside this list is accepted; the `commit-msg` hook rejects it locally and the
`Commit Lint` workflow rejects the pull request title.

### Scopes

Optional, but useful. The ones in use here:

`cli`, `keychain`, `manifest`, `clipboard`, `env`, `prompt`, `output`, `security`, `deps`, `ci`

### Breaking changes

Per `CHANGELOG.md`, **any change to a command name, flag, exit code, or output format is
breaking.** Mark it either way:

```
feat(cli)!: rename --clear-after to --expire-after
```

or with a footer, which is preferred when the consequence needs explaining:

```
feat(cli): rename --clear-after to --expire-after

BREAKING CHANGE: `--clear-after` no longer exists. Scripts passing it will fail with
exit code 2. Use `--expire-after`, which takes the same 1-300 second range.
```

While the project is below `1.0.0`, a breaking change bumps the **minor** version
(`0.1.0` → `0.2.0`) rather than jumping to `1.0.0`.

### Security fixes

Use `fix(security): ...`, not a custom `security:` type. A non-standard type produces no version
bump at all — exactly wrong for a fix people need to pick up. If the issue warrants coordinated
disclosure, follow [SECURITY.md](SECURITY.md) first and do not open a public pull request.

Anything that deliberately bends the project's secret-handling rules needs an entry in
[SECURITY-EXCEPTIONS.md](SECURITY-EXCEPTIONS.md) in the same change (see `CLIP-001` for the shape).

### Examples

```
feat(cli): add --json to the list command
fix(keychain): return exit code 5 when the login keychain is locked
fix(security): stop the manifest parser echoing values in its warning text
perf(cli): defer the manifest import until a namespace is inferred
docs: document exit code 10 in the README table
ci: publish to PyPI with trusted publishing
build(deps): bump ruff to 0.9.3
```

Rejected, and why:

```
Update README                 # no type
fixed the copy bug            # no type, past tense
feat(cli): stuff              # subject says nothing
security: patch the parser    # `security` is not a type; use fix(security)
feat: Add JSON output.        # capitalised subject, trailing period
```

### Which gate catches what

Two checks run, and they are not identical:

| Check | Where | Catches |
|---|---|---|
| `conventional-pre-commit` | local `commit-msg` hook | missing or unknown type, malformed header |
| `amannn/action-semantic-pull-request` | `Commit Lint` workflow, on the PR title | all of the above, **plus** a capitalised subject or a trailing period |

The local hook cannot check subject casing — it has no option for it. So
`feat: Add JSON output.` passes locally and fails on the pull request title. Fix it in both places:
under merge commits every commit on your branch lands on `main` and is read by Release Please, so a
sloppy branch commit is not absorbed by the pull request title the way it would be under squashing.

## Pull requests

Pull requests are **merge-committed, not squashed.** Every commit on your branch lands on `main`
exactly as you wrote it, and Release Please reads **all of them** — not just the pull request
title.

This is deliberate. The project prefers a public history that shows how the work actually happened
over a tidy one commit per pull request. It also preserves changelog entries that squashing would
silently drop: if a pull request titled `ci: retune the matrix` contains a `fix:` commit, squashing
would reduce it to a `ci:` commit and that fix would never reach the changelog.

The trade-off, and the thing to actually watch: **every commit you write is a changelog
candidate.** A branch that goes `feat: add --json` → `fix: typo in --json` publishes two entries,
the second describing a bug no released version ever had. Before asking for a merge, tidy the
branch — `git rebase -i` to squash fixups into the commit they fix, reword anything vague. Keep the
commits that represent real steps; fold away the ones that only represent you changing your mind.

The pull request title still has to be a valid Conventional Commit — the `Commit Lint` workflow
enforces it, and the title is what a reader sees in the merge commit — but it is no longer the only
message that matters.

Branch names follow `<type>/<short-description>`, e.g. `feat/json-output`, `fix/locked-keychain`.

## How a release happens

1. Your pull request merges to `main`.
2. Release Please reads every commit since the last release and opens (or updates) a release pull
   request titled `chore(main): release X.Y.Z`. That pull request contains the version bumps and the
   generated changelog section — review it, don't edit it.
3. Merging the release pull request tags `vX.Y.Z`, publishes a GitHub Release, builds the sdist and
  wheel, publishes them to PyPI, and attaches them to that Release.

PyPI uses Trusted Publishing with GitHub Actions OIDC; no PyPI API token is needed. The publisher
must match owner `CivicActions`, repository `keychain-cli`, workflow `release-please.yml`, and
environment `pypi`. Before the first upload, register it as a pending publisher for project
`keychain-cli` under the CivicActions PyPI organization. The first successful upload creates the
project owned by that organization.

In GitHub repository **Settings > Environments**, create the `pypi` environment and configure any
required reviewers or deployment restrictions. It must allow the release tags and the branch used
for manual dispatch.

Release Please authenticates with the CivicActions GitHub App installed on this repository.
Provide its client ID as the Actions variable `RELEASE_APP_CLIENT_ID` and its generated PEM
private key as the Actions secret `RELEASE_APP_PRIVATE_KEY`. Organization settings may provide
both, with access restricted to selected repositories. This App key is not an SSH signing key.
The App needs **Contents**, **Pull requests**, and **Issues** read/write permissions; it does not
need webhooks, a hosted service, or a separate codebase.

The workflow creates a short-lived installation token scoped to this repository. The stock
Release Please action uses it to create release branches, PRs, labels, and GitHub releases, and
the normal PR CI runs automatically. A follow-up check requires GitHub to report newly created
or updated release-PR head commits as verified. Required-signature rules stay enabled. The old
`RELEASE_PLEASE_TOKEN` and `RELEASE_PLEASE_SSH_SIGNING_KEY` secrets are not used by this workflow.
PyPI authentication remains separate and uses OIDC through the `pypi` environment.

If no commit since the last release bumps the version, no release pull request appears. That is
correct behaviour, not a failure.

### If you ever edit `release-please-config.json`

One line in it looks like a typo and is not:

```json
"jsonpath": "$.package[?(@.name.value=='keychain-cli')].version"
```

Release Please parses TOML with a format-preserving parser that wraps every scalar as
`{"start": …, "end": …, "value": …}` so it can splice the file by byte range instead of
re-serialising it (which is why updating `uv.lock` leaves its generated header comment and
formatting intact). The consequence is that a filter has to compare `@.name.value`. The
natural-looking `@.name` matches nothing, and a JSONPath that matches nothing is a **silent
no-op** — the release pull request would simply not contain the `uv.lock` change, and CI would
fail on `uv lock --check`. `tests/unit/test_version_sync.py` pins the expression for this reason.

### Publishing an existing tag

The `Release` workflow also has a `workflow_dispatch` trigger taking an existing tag. It builds
that tag and runs the same path, skipping Release Please entirely. Two uses:

- **Bootstrapping.** The `v0.1.0` tag was created by hand, not by Release Please, so nothing
  automatically built and attached its artifacts. Dispatching the updated workflow from `main`
  against an existing tag builds it, publishes it to PyPI, and attaches its artifacts.
- **Retrying.** If publishing fails after the tag and GitHub Release already exist, Release Please
  will not re-run for a version it considers released. Dispatch against the tag instead. Files
  already uploaded to PyPI are skipped; PyPI does not allow replacing a published distribution.

After the publishing workflow is merged to `main`, open **Actions > Release > Run workflow**,
select branch `main`, and enter the existing tag (for example, `v0.1.1`). The corresponding GitHub
Release must already exist for the artifact attachment step. Approve the `pypi` deployment if
required by the environment's protection rules.

It cannot be used to build something that is not already tagged, and it never invents a version.
