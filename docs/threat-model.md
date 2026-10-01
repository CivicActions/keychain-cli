# Threat Model

**Status**: finalized for version 0.1.0. Revisit whenever a new input path, subprocess
invocation, or storage interaction is added (project constitution, "Threat model").

## Assets

| Asset | Sensitivity | Where it lives |
|---|---|---|
| Secret values | High. The reason the tool exists. | macOS login Keychain only. In process memory as `SecretValue` while a command runs. |
| Namespace and variable names | Low. Treated as non-sensitive metadata. | Keychain item attributes; terminal output; committed manifests. |
| The Keychain unlock state | Medium. Controlled by macOS. | securityd. |

## Trust boundaries

1. **The developer's login session.** Everything running as the developer's user is inside
   the boundary. An attacker who already has code execution as that user is out of scope
   (spec Assumptions, "Trusted local machine").
2. **Other local users.** Outside. They can read `argv` and, on some configurations, the
   environment of processes they do not own.
3. **The filesystem at rest.** Outside, because backup, sync, and crash-reporting agents copy
   it elsewhere.
4. **The terminal.** Partially outside: scrollback, shell history, and session recorders
   persist what appears there.

## Channels the constitution requires us to address

### Other local processes reading `argv` and environment

- The tool never accepts a secret as an argument and never places one in the arguments of
  any process it starts. The Keychain is driven through the Security framework via
  `ctypes`, so no `security add-generic-password -w` ever runs.
- Secrets reach a child process only through its environment (`run`),
  and only the process the developer named. The parent shell is untouched.
- Tests assert placeholder values are absent from every recorded `argv`.

### Other users on a shared host

- Storage is per-user Keychain, protected by the login password and macOS access control.
- No file is created by the tool, so there is nothing for another user to read.

### Backup, sync, and crash-reporting systems capturing files at rest

- The tool writes no files. The Keychain file is already handled by macOS and Time Machine
  encryption policy; the tool adds nothing to that surface.
- Python tracebacks are never printed, so a crash reporter cannot capture a frame that
  holds a `SecretValue` through the tool's own output. Core dumps are out of scope (they
  require the attacker to be the user or root).

### Shell history and terminal scrollback

- Command lines carry names only. Secret entry uses `getpass`, which suppresses echo and
  shows no length indicator.
- Nothing the tool prints contains a value, a partial value, or a length.

### Untrusted input reaching the parser

- **Arguments**: namespace and variable names are validated against strict regular
  expressions before any Keychain call. Anything else is rejected with exit 7.
- **Standard input** (value entry): read as bytes, one trailing newline stripped, stored
  unchanged. Never interpreted.
- **Keychain responses**: every status code that is not success, duplicate, or not-found
  becomes a `StoreError` carrying the OS status and OS text only. Result objects are
  type-checked before conversion.
- **`.env` files**: parsed with strict rules in `envfile.py`:
  - Hostile or malformed line content: lines that fail syntax or variable name validation
    produce warnings with the line number and optional key name only. The line content itself
    is never printed or stored on an exception.
  - Binary / malformed files: strict UTF-8 decoding rejects non-UTF-8 content naming the line
    number without displaying unparsed bytes.
  - Non-regular files: directories, pipes, and sockets are rejected before reading (exit 7).
  - Immutability: the source file is never modified or rewritten.
- **Manifest files**: parsed using Python's standard `tomllib` (`.keychain-cli.toml`):
  - Read-only: the tool never writes or modifies `.keychain-cli.toml`.
  - Schema restrictions: only top-level `namespace` and `variables` keys are allowed. Tables,
    nested sections, and unexpected keys are rejected with exit 7 before any storage interaction.
  - Strict names: namespace and variable names must satisfy the same validation rules as CLI arguments.
  - Local directory boundary: manifests are read from the current working directory only; parent
    directories are never searched.

## Interpreter trust

The login Keychain grants silent access to the *application* that created an item. For this
tool that application is the Python interpreter binary. A different interpreter path (after
`uv tool upgrade`, or from a development checkout) triggers a one-time macOS prompt per item.
This is expected and is documented in the README so it is not misdiagnosed as a defect.

## Deliberate exposures

Every deliberate departure from "secrets never surface" is recorded in
`SECURITY-EXCEPTIONS.md`.

- **CLIP-001: Clipboard copy (`copy` command)**:
  - Exposure window: secret remains on the system pasteboard for `--clear-after` seconds
    (default 45, max 300) or until the developer copies something else.
  - Threat actors: any process running under the user's account with pasteboard access,
    plus third-party clipboard managers and cloud synchronization tools (e.g. Universal Clipboard).
  - Mitigations:
    - Never a default workflow; requires explicit `copy` command.
    - Single secret only; bulk copy is refused.
    - Automatic clearing helper checks SHA-256 hash so newer user content is never overwritten.
    - If the clearing helper fails to launch, the clipboard is immediately cleared and the command exits 9.
    - Unsuppressible warning printed on stderr upon every invocation.
    - Pinned by `test_value_reaches_only_pbcopy_stdin` asserting secret bytes reach only `pbcopy` stdin.

## Out of scope

- An attacker with code execution as the developer's user.
- Compromise of macOS, securityd, or the Keychain itself.
- A child process launched by `run` printing its own environment; that is the developer's
  program, not the tool.
