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
| `.release-please-manifest.json` | the `"."` entry |
| `CHANGELOG.md` | anything |

[Release Please](https://github.com/googleapis/release-please) owns all four. It derives the next
version from your commit messages and rewrites them together in a release pull request. Editing one
by hand desynchronises them; `tests/unit/test_version_sync.py` will fail if you do.

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
`feat: Add JSON output.` passes locally and fails on the pull request title. That is tolerable
because branch commits are squashed away; the pull request title is the only message that survives
onto `main`. Write both to the same standard anyway.

## Pull requests

Pull requests are **squash-merged**, which means **the pull request title becomes the commit
message on `main`** — and that is the string Release Please reads. The title must be a valid
Conventional Commit even when the individual commits on your branch already are. The `Commit Lint`
workflow enforces this.

Branch names follow `<type>/<short-description>`, e.g. `feat/json-output`, `fix/locked-keychain`.

## How a release happens

1. Your pull request merges to `main`.
2. Release Please reads every commit since the last release and opens (or updates) a release pull
   request titled `chore(main): release X.Y.Z`. That pull request contains the version bumps and the
   generated changelog section — review it, don't edit it.
3. Merging the release pull request tags `vX.Y.Z`, publishes a GitHub Release, builds the sdist and
   wheel, and publishes to [PyPI](https://pypi.org/p/keychain-cli) via Trusted Publishing.

If no commit since the last release bumps the version, no release pull request appears. That is
correct behaviour, not a failure.

### Publishing a tag by hand

The `Release` workflow also has a `workflow_dispatch` trigger taking an existing tag. It builds
that tag and runs the same publish path, skipping Release Please entirely. Two uses:

- **Bootstrapping.** The `v0.1.0` tag was created by hand, not by Release Please, so nothing
  automatically published it to PyPI. Dispatching the workflow against `v0.1.0` does that.
- **Retrying.** If a publish fails after the tag and GitHub Release already exist, Release Please
  will not re-run for a version it considers released. Dispatch against the tag instead.

It cannot be used to publish something that is not already tagged, and it never invents a version.
