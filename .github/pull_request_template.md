<!--
  Pull requests are merge-committed, NOT squashed. Every commit on your branch lands on
  main as written, and Release Please parses all of them to build the changelog -- so
  each commit must be a valid Conventional Commit, not just this title:

      <type>(<optional scope>): <subject>

  Types: feat fix docs style refactor perf test build ci chore revert
  Subject: lowercase, imperative, no trailing period.

  Tidy the branch before asking for a merge: squash fixup commits into what they fix, so
  the public history shows real steps rather than you changing your mind.

  See CONTRIBUTING.md for the full guide.
-->

## What changed

<!-- One or two sentences. What does this do for someone using the tool? -->

## Why

<!-- Link the issue, or explain the problem this solves. -->

## Checklist

- [ ] PR title is a valid Conventional Commit
- [ ] **Every commit on the branch** is a valid Conventional Commit — all of them land on `main`
      and each one is a changelog candidate
- [ ] Branch tidied: fixup commits squashed into what they fix
- [ ] Breaking? Marked with `!` or a `BREAKING CHANGE:` footer in the PR description.
      Remember: any change to a command name, flag, exit code, or output format is breaking.
- [ ] Tests added or updated
- [ ] `uv run pytest`, `ruff check`, `mypy`, and `pylint src tests` all pass locally
- [ ] No secret value can reach `argv`, logs, stdout/stderr, an exception, or a file.
      Deliberate exceptions are recorded in `SECURITY-EXCEPTIONS.md`.
- [ ] Did **not** hand-edit the version in `pyproject.toml`, `__version__`, the `keychain-cli`
      version in `uv.lock`, `.release-please-manifest.json`, or `CHANGELOG.md` — Release Please
      owns those
