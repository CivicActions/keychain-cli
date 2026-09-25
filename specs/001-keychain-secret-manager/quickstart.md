# Quickstart: validating the Keychain Secret Manager

**Feature**: `001-keychain-secret-manager` | **Date**: 2026-09-24

A run guide proving the feature works end to end. Every value below is a placeholder.
Command shapes are defined in [contracts/cli.md](contracts/cli.md).

## Prerequisites

- macOS 13 or later, logged in at the console (the login keychain must be unlockable).
- `uv` 0.12 or later.
- A clone of the repository.

## Setup

```sh
uv sync                        # creates .venv with dev dependencies, no runtime deps
uv run keychain-cli --version
```

Or install the tool the way an end user would:

```sh
uv tool install .
keychain-cli --help
```

## Automated validation

```sh
uv run ruff format --check . && uv run ruff check .
uv run mypy
uv run pytest -m "not integration"         # unit tests: in-memory store, no Keychain access
uv run pytest -m integration               # real Security framework against a temp keychain
```

The integration suite creates its own keychain file under a temp directory and deletes it on
teardown. It never touches your login keychain. Expected: all green on macOS; the
integration suite reports `skipped` on any other platform.

## Manual scenarios

Use a scratch namespace so cleanup is one command. Run these from an empty directory.

### 1. Store and list (Stories 1, 4)

```sh
keychain-cli set qs-demo API_TOKEN DB_PASSWORD
#   prompted twice, nothing echoed; stderr ends with "stored: API_TOKEN, DB_PASSWORD"
keychain-cli list qs-demo
#   API_TOKEN
#   DB_PASSWORD
keychain-cli list
#   qs-demo   (plus any other namespaces you already have)
keychain-cli list qs-demo --json
#   ["API_TOKEN","DB_PASSWORD"]
history | tail -5           # command lines contain names only
```

### 2. Overwrite protection (Story 1, scenarios 4–5)

```sh
keychain-cli set qs-demo API_TOKEN
#   "API_TOKEN already exists in qs-demo. Overwrite? [y/N]" -> n
echo "exit=$?"              # exit=4, value unchanged
```

### 3. Run a command (Story 2)

```sh
keychain-cli run qs-demo -- /usr/bin/env | grep -c -E '^(API_TOKEN|DB_PASSWORD)='
#   2
env | grep -c -E '^(API_TOKEN|DB_PASSWORD)='
#   0   (parent shell untouched)
keychain-cli run qs-demo -- sh -c 'exit 42'; echo "exit=$?"
#   exit=42
keychain-cli run qs-demo -- no-such-command-xyz; echo "exit=$?"
#   keychain-cli: command not found: no-such-command-xyz. ...   exit=8
keychain-cli run qs-demo /usr/bin/env; echo "exit=$?"
#   usage error explaining the -- separator, exit=2
```

### 4. Import a `.env` file (Story 3)

```sh
cat > demo.env <<'EOF'
# comment
export ALPHA=one
BETA="two words"
GAMMA='single # not a comment'
DELTA=three # trailing comment
this line is malformed
BETA=override
EOF
keychain-cli import qs-demo demo.env
#   warning: line 6: malformed entry
#   duplicate key BETA (lines 3, 7): last value used
#   stored: ALPHA, BETA, DELTA, GAMMA
ls -l demo.env              # unchanged
keychain-cli run qs-demo -- sh -c 'printf "%s|%s|%s|%s\n" "$ALPHA" "$BETA" "$GAMMA" "$DELTA"'
#   one|override|single # not a comment|three
```

### 5. Stdin entry for a bare token file (FR-004a)

```sh
printf 'placeholder-token\n' > token.txt
keychain-cli set qs-demo GH_TOKEN < token.txt
keychain-cli run qs-demo -- sh -c 'printf "[%s]\n" "$GH_TOKEN"'
#   [placeholder-token]      (trailing newline stripped)
keychain-cli set qs-demo A B < token.txt; echo "exit=$?"
#   refused before reading, exit=7
```

### 6. Namespace casing (FR-007a/b)

```sh
keychain-cli set Qs-Demo EXTRA          # same namespace as qs-demo
keychain-cli list | grep -i qs-demo
#   qs-demo                              (first-given casing preserved)
keychain-cli set 'bad name!' X; echo "exit=$?"
#   exit=7, message states the allowed form
```

### 7. Manifest (Story 6)

```sh
cat > .keychain-cli.toml <<'EOF'
namespace = "qs-demo"
variables = ["API_TOKEN", "DB_PASSWORD", "NEW_ONE"]
EOF
keychain-cli check; echo "exit=$?"
#   NEW_ONE                  exit=10
keychain-cli init
#   prompted only for NEW_ONE
keychain-cli check; echo "exit=$?"
#   exit=0
keychain-cli run -- /usr/bin/env >/dev/null
#   stderr: using namespace qs-demo from .keychain-cli.toml
```

### 8. Clipboard (Story 7, optional; only after CLIP-001 is approved)

Not part of the normal workflow. Use it only for a destination that cannot read environment
variables, such as a vendor web console.

```sh
keychain-cli copy qs-demo API_TOKEN
#   copied qs-demo/API_TOKEN to clipboard; it will be cleared in 45 seconds.
#   warning: clipboard managers, history tools, and clipboard sync may keep a copy.
pbpaste | wc -c              # non-zero
sleep 50; pbpaste | wc -c    # 0
keychain-cli copy qs-demo API_TOKEN --clear-after 5; echo other | pbcopy; sleep 7; pbpaste
#   other                    (newer clipboard content survives)
keychain-cli copy qs-demo API_TOKEN --clear-after 0; echo "exit=$?"
#   exit=2, nothing copied
keychain-cli copy qs-demo; echo "exit=$?"
#   exit=2, no namespace-wide copy
```

### 9. Delete (Story 5)

```sh
keychain-cli delete qs-demo EXTRA
keychain-cli delete qs-demo
#   "Delete namespace qs-demo and its N variables? Type the namespace name to confirm:"
keychain-cli list qs-demo; echo "exit=$?"
#   exit=3
```

## Leak check (SC-002, SC-009)

Run the whole manual sequence inside `script -q session.log` with a distinctive placeholder
such as `LEAKCHECK-7f3a`, then:

```sh
grep -c LEAKCHECK-7f3a session.log      # 0
grep -rl LEAKCHECK-7f3a . --exclude=session.log   # nothing
```

The automated equivalent lives in `tests/unit/test_no_leaks.py` and
`tests/integration/test_end_to_end.py`.

## Cleanup

```sh
keychain-cli delete qs-demo --force
rm -f demo.env token.txt .keychain-cli.toml session.log
```
