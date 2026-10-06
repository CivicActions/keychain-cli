<!--
  The PR title becomes the commit message on main (PRs are squash-merged), and Release
  Please parses it to decide the next version. It must be a Conventional Commit:

      <type>(<optional scope>): <subject>

  Types: feat fix docs style refactor perf test build ci chore revert
  Subject: lowercase, imperative, no trailing period.

  See CONTRIBUTING.md for the full guide.
-->

## What changed

<!-- One or two sentences. What does this do for someone using the tool? -->

## Why

<!-- Link the issue, or explain the problem this solves. -->

## Checklist

- [ ] PR title is a valid Conventional Commit
- [ ] Breaking? Marked with `!` or a `BREAKING CHANGE:` footer in the PR description.
      Remember: any change to a command name, flag, exit code, or output format is breaking.
- [ ] Tests added or updated
- [ ] `uv run pytest`, `ruff check`, `mypy`, and `pylint src tests` all pass locally
- [ ] No secret value can reach `argv`, logs, stdout/stderr, an exception, or a file.
      Deliberate exceptions are recorded in `SECURITY-EXCEPTIONS.md`.
- [ ] Did **not** hand-edit the version in `pyproject.toml`, `__version__`,
      `.release-please-manifest.json`, or `CHANGELOG.md` — Release Please owns those
