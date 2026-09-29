# keychain-cli

Store project secrets in the macOS Keychain and hand them to one command's environment,
instead of keeping a plaintext `.env` file.

**Status**: pre-release. The storage layer is complete and tested; the commands are not
yet implemented. See [CHANGELOG.md](CHANGELOG.md).

## What it is

A small Python command-line tool for macOS. Each project gets a *namespace* in your login
Keychain holding named environment variables. You store values at a hidden prompt, then run
your development command through the tool, which places the variables in that command's
environment and nowhere else. Your shell is never modified. Nothing is written to disk.

Requires macOS 13 or later and Python 3.11 or later. There is no fallback storage on other
platforms; the tool exits with code 6.

## Install

```sh
uv tool install git+https://github.com/civicactions/keychain-cli
keychain-cli --version
```

To uninstall:

```sh
uv tool uninstall keychain-cli
```

## First secret in 60 seconds

*To be completed when the `set` and `run` commands land.*

## Commands

*To be completed as commands land. The command contract is in
`specs/001-keychain-secret-manager/contracts/cli.md`.*

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected internal error |
| 2 | Usage error: bad arguments, missing `--`, out-of-range option |
| 3 | Not found: namespace, variable, file, or manifest |
| 4 | Refused: overwrite or deletion declined, or non-interactive without `--force` |
| 5 | Keychain error: locked, denied, canceled, unavailable, or unexpected status |
| 6 | Unsupported platform or Python version |
| 7 | Invalid input: bad name, malformed manifest, empty or ambiguous stdin value |
| 8 | `run`: command not found or not executable |
| 9 | `copy`: clipboard write failed, or clearing could not be scheduled |
| 10 | `check`: one or more required variables are missing |
| 130 | Interrupted during `set`, `import`, or `init` |

## Troubleshooting

**macOS asks me to allow keychain-cli to access an item.** Items in the login Keychain
trust the *application* that created them, and for this tool that application is the Python
interpreter. After `uv tool upgrade` switches to a different Python, or when you run from a
development checkout, macOS asks once per item. Click **Always Allow**. This is the
operating system protecting the item, not a defect.

**"Keychain operation failed ... interaction not allowed" over SSH.** The login Keychain is
locked and there is no screen on which macOS can show the unlock dialog. Unlock it at the
console, or run the command locally.

**Exit code 6.** You are not on macOS 13 or later, or Python is older than 3.11. Reinstall
with `uv tool install`, which brings its own supported interpreter.

## Security notes

- Secret values never appear in command-line arguments, shell history, log output, error
  messages, temporary files, or exception text. The Keychain is driven directly through the
  Security framework, not through the `security` command.
- Each developer's Keychain holds their own values. The tool never syncs or shares them.
- The threat model is in [docs/threat-model.md](docs/threat-model.md). Deliberate
  exceptions to the rules above are listed in [SECURITY-EXCEPTIONS.md](SECURITY-EXCEPTIONS.md).
  Report vulnerabilities as described in [SECURITY.md](SECURITY.md).
