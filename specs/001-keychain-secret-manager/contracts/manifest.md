# Manifest Contract: `.keychain-cli.toml`

**Feature**: `001-keychain-secret-manager` | **Date**: 2026-09-24

A committed, plaintext TOML file declaring what a project needs. It contains names only and
there is no key under which a value could be written (FR-032).

## Location

The current working directory only. Parent directories are not searched (research R-009).

## Schema

```toml
# Namespace whose variables this project needs. Case-insensitive.
namespace = "client-a"

# Environment variable names the project requires. Names only, never values.
variables = [
  "API_TOKEN",
  "DB_PASSWORD",
]
```

| Key | Type | Required | Rule |
|---|---|---|---|
| `namespace` | string | yes | Matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` |
| `variables` | array of strings | yes | Non-empty; each matches `^[A-Za-z_][A-Za-z0-9_]*$`; no duplicates |

Any other top-level key, any nested table, or a wrong type is a malformed manifest
(exit 7). The error names the offending key and the allowed keys.

## Consumers

| Command | Uses |
|---|---|
| `run`, `list`, `init`, `check` | `namespace` as the default when none is given (reported on stderr) |
| `init` | `variables` to decide what to prompt for |
| `check` | `variables` to report what is missing |

`set`, `import`, `delete`, and `copy` ignore the manifest entirely.

## Precedence

An explicitly named namespace always wins over the manifest. When they differ, the tool
prints `using namespace <explicit> (manifest declares <other>)` on stderr so the mismatch is
visible.

## Guarantees

- The tool only ever **reads** this file. No command writes or modifies it.
- Parsing uses Python's standard `tomllib`; parse errors are reported with the parser's
  line and column, without echoing file content beyond what `tomllib` includes in its own
  message.
