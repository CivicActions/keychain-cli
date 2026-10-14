# keychain-cli

Store project secrets in the macOS Keychain and hand them to one command's environment,
instead of keeping a plaintext `.env` file.

## What it is

`keychain-cli` is a small, security-focused command-line tool for storing secrets in the macOS
Keychain and injecting them into a single command only when needed. It is designed for local
development workflows where you need API tokens, database passwords, or other environment
variables available to an application, but do not want those values written to disk or permanently
exported into your shell session.

Each project gets a *namespace* in your login Keychain holding named environment variables. You
store values at a hidden prompt, then run your development command through the tool, which places
the variables in that command's environment and nowhere else. Your shell is never modified.
Nothing is written to disk.

Requires macOS 13 or later and Python 3.11 or later.

## Install

From PyPI:

```sh
uv tool install keychain-cli
keychain-cli --version
```

Or from the git repository:

```sh
uv tool install git+https://github.com/civicactions/keychain-cli
keychain-cli --version
```

To uninstall:

```sh
uv tool uninstall keychain-cli
```

## First secret in 60 seconds

1. Store secrets in a project namespace:

   ```sh
   keychain-cli set my-project API_TOKEN DB_PASSWORD
   ```

   You are prompted for each value without terminal echo:

   ```text
   Value for my-project/API_TOKEN:
   Value for my-project/DB_PASSWORD:
   stored: API_TOKEN, DB_PASSWORD
   ```

2. Run your command with secrets injected:

   ```sh
   keychain-cli run my-project -- npm run dev
   ```

   The command starts with `API_TOKEN` and `DB_PASSWORD` available in its environment.
   When the process finishes, no secrets remain in your shell session.

## Team setup with a manifest

Projects can commit a `.keychain-cli.toml` manifest in the project root directory to declare
the namespace and required environment variable names (names only, never values):

```toml
# .keychain-cli.toml
namespace = "my-project"
variables = [
  "API_TOKEN",
  "DB_PASSWORD",
]
```

This gives the team a shared contract for local configuration without storing any secret values in the repository.

- Developers can run `keychain-cli check` to see what is missing
- Developers can run `keychain-cli init` to fill only missing values
- Developers can run their code without typing the namespace, e.g.:
   - `keychain-cli run -- npm run dev`
- CI and documentation can refer to variable names consistently

Good practice: commit variable names, never secret values. The manifest is for structure only.

## Commands

| Command | Summary |
|---|---|
| `set <namespace> <VAR>...` | Store one or more secrets via hidden prompt or standard input |
| `list [<namespace>]` | List namespaces, or variable names in a namespace |
| `run [<namespace>] -- <cmd>` | Run a command with secrets injected into its environment |
| `import <namespace> <file>` | Import an existing `.env` file into a namespace |
| `delete <namespace> [<VAR>]` | Remove a single variable or an entire namespace |
| `init [<namespace>]` | Prompt for missing secrets declared in `.keychain-cli.toml` |
| `check [<namespace>]` | Report which declared secrets are missing |

For full command documentation, options, and exit codes, run `keychain-cli <command> --help`.

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

## Occasional: pasting a value into a web console

For destinations that cannot read environment variables (such as a vendor web console),
a single secret can be copied to the system clipboard:

```sh
keychain-cli copy my-project API_TOKEN
```

**Security notice**:
- This is an occasional fallback, not the normal way to use secrets; prefer `keychain-cli run`.
- The clipboard is readable by every application running as your user. Clipboard managers,
  history tools, and clipboard sync services (such as Universal Clipboard) can defeat automatic clearing.
- The secret is automatically cleared after 45 seconds (configurable with `--clear-after SECONDS`, 1–300)
  only if the clipboard still contains the value.
- Governed by exception entry CLIP-001 in [SECURITY-EXCEPTIONS.md](https://github.com/CivicActions/keychain-cli/blob/main/SECURITY-EXCEPTIONS.md).

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
- The threat model is in [docs/threat-model.md](https://github.com/CivicActions/keychain-cli/blob/main/docs/threat-model.md). Deliberate
  exceptions to the rules above are listed in [SECURITY-EXCEPTIONS.md](https://github.com/CivicActions/keychain-cli/blob/main/SECURITY-EXCEPTIONS.md).
  Report vulnerabilities as described in [SECURITY.md](https://github.com/CivicActions/keychain-cli/blob/main/SECURITY.md).

## Contributing

Commit messages and pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/);
releases, version numbers, and the changelog are automated with Release Please. See
[CONTRIBUTING.md](https://github.com/CivicActions/keychain-cli/blob/main/CONTRIBUTING.md) before opening a pull request.
