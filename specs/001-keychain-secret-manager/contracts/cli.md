# CLI Contract: `keychain-cli`

**Feature**: `001-keychain-secret-manager` | **Date**: 2026-09-24

This is the user-facing interface. Any change to a command name, positional order, flag,
exit code, or output shape is a breaking change under the constitution's release rules.

## Global conventions

- **Streams**: results on stdout; prompts, progress, warnings, and errors on stderr.
- **Secrets never appear** on either stream, in any argument, or in any file the tool writes.
- **Namespace argument**: case-insensitive; displayed with the casing first given.
- **`--json`**: on listing commands, emit a JSON array of strings and nothing else on stdout.
- **`--force`**: skip interactive confirmation for overwrite (`set`, `import`) or deletion
  (`delete`). It is the only way to perform those actions non-interactively.
- **`--help`**: every command's help states what it does, its exit codes, and, where
  relevant, its security caveat. `keychain-cli --version` prints the version.
- **Non-interactive** means stdin is not a TTY. Confirmations then fail closed (exit 4)
  unless `--force` is given.

## Namespace inference

`run`, `list`, `init`, and `check` may omit the namespace when `.keychain-cli.toml` in the
current directory declares one. The tool then prints `using namespace <name> from
.keychain-cli.toml` on stderr. An explicit namespace always wins. `set`, `import`,
`delete`, and `copy` always require the namespace explicitly.

## Commands

### `set` — store one or more variables

```
keychain-cli set <namespace> <VAR> [<VAR> ...] [--force] [--stdin]
```

- Validates the namespace and every variable name before prompting for anything.
- Interactive: one hidden prompt per variable, `Value for <namespace>/<VAR>:` on stderr.
  An empty entry asks `Store an empty value for <VAR>? [y/N]`.
- Existing variable, interactive, no `--force`: asks `<VAR> already exists in <namespace>.
  Overwrite? [y/N]`. Declining skips it.
- Existing variable, non-interactive, no `--force`: nothing is changed; exit 4.
- `--stdin`, or stdin not a TTY: reads the single value from stdin. Exactly one `<VAR>` is
  allowed, checked before reading. One trailing newline is stripped. Empty input: exit 7.
- Summary on stderr: `stored: A, B` / `skipped: C` / `overwritten: D`.

Exit: 0 all requested variables stored or overwritten; 4 at least one skipped or refused;
7 invalid name, empty stdin value, or multiple variables in stdin mode; 5 Keychain error.

### `list` — list namespaces or a namespace's variables

```
keychain-cli list [<namespace>] [--json]
```

- No namespace and no manifest: lists namespaces, one per line, in their display casing,
  sorted by lowercase key. Zero namespaces prints nothing and exits 0.
- No namespace, manifest present: lists that namespace's variables (inference reported on
  stderr). To list namespaces from inside a project directory, use `list --all`.
- With a namespace: variable names one per line, sorted. Never values.
- `--json`: `["A","B"]` on stdout.

```
keychain-cli list --all [--json]        # always lists namespaces, ignoring any manifest
```

Exit: 0 success; 3 named namespace does not exist.

### `run` — run a command with the namespace in its environment

```
keychain-cli run [<namespace>] -- <command> [<arg> ...]
```

- Everything after the first `--` is the command; nothing after it is interpreted by the
  tool. `--` is mandatory; its absence is exit 2 with the correct form shown.
- The child inherits the tool's environment with the namespace's variables overlaid
  (namespace wins on collision). No shell is involved; `<command>` is resolved on `PATH`.
- The tool's process is replaced by the command (`exec`). Exit status, signals, and stdio
  are the command's own.
- Nothing is launched if the namespace does not exist or the Keychain cannot be read.

Exit (before launch): 2 usage; 3 namespace not found; 5 Keychain error; 8 command not
found or not executable. After launch: the command's own status.

### `import` — load a `.env`-style file into a namespace

```
keychain-cli import <namespace> <file> [--force]
```

- Parses per the rules in research R-008. The file is never modified.
- Malformed lines: warning `line 12: malformed entry` or `line 12 (DB_URL): malformed
  entry` on stderr; content never shown. Processing continues.
- Duplicate keys: last wins; `duplicate key DB_URL (lines 3, 9): last value used`.
- Existing variables: collected and confirmed once, `3 variables already exist: A, B, C.
  Overwrite all? [y/N]`; declined or non-interactive without `--force` skips them all.
- Summary on stderr with counts and names: stored, overwritten, skipped, malformed.

Exit: 0 every parsed entry stored or overwritten; 4 entries skipped; 3 file not found; 7
file unreadable, not a regular file, or every line malformed; 5 Keychain error.

### `delete` — remove one variable or a whole namespace

```
keychain-cli delete <namespace> <VAR>            # one variable, no confirmation
keychain-cli delete <namespace> [--force]        # whole namespace, confirmation required
```

- Namespace deletion asks `Delete namespace <name> and its N variables? Type the namespace
  name to confirm:` and requires the exact display or lowercase name. Non-interactive
  requires `--force`.
- The namespace is never inferred for `delete`.

Exit: 0 deleted; 3 variable or namespace not found (nothing changed); 4 declined or
non-interactive without `--force` (nothing changed); 5 Keychain error.

### `init` — store missing variables declared by the manifest

```
keychain-cli init [<namespace>]
```

- Reads `.keychain-cli.toml` from the current directory. Prompts (hidden) only for declared
  variables not already stored. Existing values are never touched. All present: prints
  `namespace <name> is complete` and exits 0.
- Non-interactive with missing variables: exit 7, listing the missing names.

Exit: 0 complete; 3 manifest missing; 7 manifest malformed, or missing variables and no
TTY; 5 Keychain error.

### `check` — report which manifest variables are missing

```
keychain-cli check [<namespace>] [--json]
```

- Prints missing variable names one per line (or a JSON array). Stores nothing.

Exit: 0 nothing missing; 1 one or more missing (names printed); 3 manifest missing; 7
manifest malformed.

### `copy` — copy one value to the clipboard (optional capability)

```
keychain-cli copy <namespace> <VAR> [--clear-after SECONDS]
```

- Exists only for destinations that cannot read environment variables. It is never the
  default way to reach a value, and no other command touches the clipboard.
- `--clear-after`: integer seconds, default 45, allowed 1–300. Out-of-range values are
  rejected (exit 2) before anything is copied.
- Places the value on the system clipboard via `pbcopy` stdin. Prints on stderr:

  ```
  copied <namespace>/<VAR> to clipboard; it will be cleared in 45 seconds.
  warning: clipboard managers, history tools, and clipboard sync may keep a copy.
  ```

- After the interval the clipboard is cleared **only if it still holds this value**.
- If the clearing helper cannot be started, the clipboard is cleared immediately and the
  command exits 9 with `value was not left on the clipboard`.
- Refuses any form that names more than one variable or none. There is no bulk copy.
- Help text states: the clipboard is readable by every application running as you and by
  clipboard managers and sync services, which can defeat automatic clearing; the value
  remains for up to the interval; if the tool is killed before then, the value remains until
  you copy something else.

Exit: 0 copied and clear scheduled; 2 interval out of range; 3 not found (clipboard
untouched); 5 Keychain error (clipboard untouched); 9 clipboard write failed, or clear
could not be scheduled (clipboard cleared).

## Exit codes

| Code | Meaning | Nothing changed? |
|---|---|---|
| 0 | Success (for `check`: nothing missing) | — |
| 1 | Unexpected internal error (for `check`: variables missing) | yes |
| 2 | Usage error: bad arguments, missing `--` | yes |
| 3 | Not found: namespace, variable, file, or manifest | yes |
| 4 | Refused: overwrite or deletion declined, or non-interactive without `--force` | yes |
| 5 | Keychain error: locked, denied, canceled, unavailable, or unexpected status | yes |
| 6 | Unsupported platform or Python version | yes |
| 7 | Invalid input: bad name, malformed manifest, empty or ambiguous stdin value, unreadable file | yes |
| 8 | `run`: command not found or not executable | yes |
| 9 | `copy`: clipboard write failed, or clearing could not be scheduled (clipboard cleared) | yes |

`run` after a successful launch exits with the command's own status, which may coincide
with any value above.

## Error message form

Every error is one or two lines on stderr:

```
keychain-cli: <what failed>. <what to do next>
```

Never includes a secret value, its length, or any fragment. Keychain failures append the OS
message from `SecCopyErrorMessageString`, which never contains item data.

## Help text requirements (constitution IX)

`keychain-cli --help` must let a first-time user complete: store a secret, run a command
with it, list what is stored, import a `.env` file. Each subcommand's `--help` includes one
example invocation and its exit codes.
