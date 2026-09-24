# Data Model: Keychain Secret Manager

**Feature**: `001-keychain-secret-manager` | **Date**: 2026-09-24

The tool has no database. The macOS Keychain is the only store of secret values
(constitution III); everything below is either a Keychain attribute mapping or a transient
in-memory type. Types marked **sensitive** may hold a secret and are governed by the rules at
the end of this document.

## Entities

### Namespace

A named grouping of variables for one project or context.

| Field | Type | Rule |
|---|---|---|
| `key` | `str` | `display.lower()`. Used for every lookup and as the Keychain service suffix. |
| `display` | `str` | Casing as first given by the developer. Shown in all output. |

**Validation** (FR-007a), applied before any Keychain call:

```
^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$
```

**Existence** (spec Key Entities): a namespace exists exactly when at least one item with
service `keychain-cli:<key>` and the creator stamp exists. There is no create or empty
state.

**Display-name rule** (FR-007b): when adding a variable to an existing namespace, the
display name is read from any existing item and reused. When the namespace does not yet
exist, the display name is the casing given in this invocation.

**Relationships**: has 1..n Variables. Independent of all other namespaces.

### Variable

A named secret within a namespace.

| Field | Type | Rule |
|---|---|---|
| `name` | `str` | Case-sensitive environment variable name. |
| `namespace` | `Namespace` | Owner. |

**Validation** (FR-007), applied before prompting for any value:

```
^[A-Za-z_][A-Za-z0-9_]*$
```

`(namespace.key, name)` is unique. `Api_Token` and `API_TOKEN` are distinct variables.

### SecretValue — **sensitive**

The value of a variable while it is in process memory.

| Field | Type | Rule |
|---|---|---|
| `data` | `bytes` | UTF-8. Round-trips byte-exact; may contain newlines and non-ASCII. |

- `__repr__` and `__str__` return `SecretValue(<redacted>)`. There is no accidental way to
  format the value into a string.
- Never stored on an exception object, never logged, never passed to `str.format` or
  f-strings in tool code. A unit test asserts the redaction.
- Lifetime: created at prompt/stdin/Keychain read; consumed by `SecItemAdd`, the child
  environment dict, or `pbcopy` stdin; then dereferenced. Python cannot guarantee
  zeroization; the `run` path sidesteps this by `exec`, which discards the whole image.
- An empty value is legal in the Keychain but requires interactive confirmation to store,
  and is an error (exit 7) in stdin mode.

### KeychainItem

The stored representation of one Variable. Mapping to generic-password attributes:

| Attribute | Value | Notes |
|---|---|---|
| `kSecClass` | `kSecClassGenericPassword` | |
| `kSecAttrService` | `"keychain-cli:" + namespace.key` | Exact-match key. |
| `kSecAttrAccount` | `variable.name` | |
| `kSecAttrCreator` | `0x6B63636C` (`'kccl'`) | Ownership stamp; SInt32 CFNumber. Enumeration key. |
| `kSecAttrGeneric` | `namespace.display.encode()` | Display casing. |
| `kSecAttrLabel` | `f"keychain-cli: {display}/{name}"` | Keychain Access "Name" column. Not parsed. |
| `kSecValueData` | `secret.data` | Requested only by `get`; never by list operations. |

An item the tool did not create (no stamp, or service without the prefix) is invisible to
every command. The tool never reads, lists, or deletes it.

### Manifest

A committed, plaintext TOML file `.keychain-cli.toml` in the current directory.

| Field | TOML key | Type | Rule |
|---|---|---|---|
| `namespace` | `namespace` | string | Must pass Namespace validation. |
| `variables` | `variables` | array of strings | Non-empty; each passes Variable validation; no duplicates. |

Unknown top-level keys are an error (FR-034), which is also what makes FR-032 hold: there is
no key under which a value could be written. See [contracts/manifest.md](contracts/manifest.md).

### EnvFileEntry and EnvFileParse — **sensitive**

Result of parsing a `.env`-style file for `import`.

| Type | Fields |
|---|---|
| `EnvFileEntry` | `line: int`, `name: str`, `value: SecretValue` |
| `MalformedLine` | `line: int`, `name: str \| None` (only if safely derivable; never content) |
| `DuplicateKey` | `name: str`, `first_line: int`, `last_line: int` |
| `EnvFileParse` | `entries: list[EnvFileEntry]` (post-dedup, last wins), `malformed: list[MalformedLine]`, `duplicates: list[DuplicateKey]` |

### StoreReport

Returned by `set`, `import`, and `init`; printed as the completion summary (FR-008, FR-013).

| Field | Type |
|---|---|
| `stored` | `list[str]` variable names |
| `skipped` | `list[str]` existing names left untouched |
| `overwritten` | `list[str]` |
| `malformed` | `list[MalformedLine]` (import only) |
| `duplicates` | `list[DuplicateKey]` (import only) |

Contains names and line numbers only. Safe to print.

## SecretStore interface (the test seam)

The only module allowed to import the Security framework implements this protocol. Every
command depends on the protocol, never the implementation (constitution VI).

```
list_namespaces() -> list[Namespace]                 # attrs-only query by stamp
list_variables(ns: Namespace) -> list[str]           # attrs-only query by stamp+service
exists(ns, name) -> bool                             # attrs-only
get(ns, name) -> SecretValue                         # data query; raises NotFound
get_all(ns) -> dict[str, SecretValue]                # for run; raises NotFound if empty
add(ns, name, value) -> None                         # raises AlreadyExists
update(ns, name, value) -> None                      # raises NotFound
delete_variable(ns, name) -> None                    # raises NotFound
delete_namespace(ns) -> int                          # returns count; raises NotFound if 0
```

Implementations:

- `SecurityFrameworkStore(keychain: KeychainHandle | None = None)` — production. When a
  handle is given, every query adds `kSecUseKeychain` / `kSecMatchSearchList`, which is how
  integration tests target a temporary keychain.
- `InMemoryStore` (tests only) — a `dict[(key, name)] -> (display, SecretValue)`.

Errors raised by the store carry the `OSStatus` code and the OS message string, never the
value or the attributes dictionary.

## State transitions

```
Variable:   (absent) --set/import/init--> (stored) --set --force / confirmed--> (stored, new value)
                                          (stored) --delete--> (absent)

Namespace:  (absent) --first variable stored--> (exists)
            (exists) --last variable deleted, or delete namespace--> (absent)
```

There are no other states. Nothing is soft-deleted or versioned (Out of Scope).

## Ordering guarantees (FR-017)

- Variable names: sorted by Unicode code point (`sorted()`), so `API_TOKEN` precedes
  `Api_Token`.
- Namespaces: sorted by `key` (lowercase), displayed with `display`.

## Rules for sensitive types

1. Only `SecretValue` may hold a secret. Plain `str`/`bytes` variables holding secrets are
   a review defect.
2. A `SecretValue` never appears in an exception, a log call, a `print`, a format string, or
   an `argv` list. Tests assert this for every command on success and failure paths.
3. `StoreReport`, `MalformedLine`, `DuplicateKey`, `Namespace`, and `Manifest` contain no
   secret material by construction and may be printed or JSON-encoded freely.
