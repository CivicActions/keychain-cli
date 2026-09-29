# Changelog

All notable changes to keychain-cli. The format follows Keep a Changelog; versions follow
semantic versioning. Any change to a command name, flag, exit code, or output format is
breaking and lands in a major release.

## Unreleased

### Added

- Storage layer: `SecretStore` protocol and its Security framework implementation. Items
  are generic passwords stamped with creator code `kccl` under service
  `keychain-cli:<namespace>`; listing is attribute-only and never reads secret data.
- Core types: `SecretValue` (redacted `repr`, unformattable), namespace and variable name
  validation (namespaces case-insensitive, variables case-sensitive), error hierarchy with
  the documented exit-code table, platform guard (macOS 13+, Python 3.11+).
- CLI dispatcher with the `--` separator split, `--help`, and `--version`. Every command is
  registered and returns "not implemented" with exit 1 in this build.
- Test suite: unit tests against an in-memory store; integration tests against a temporary
  keychain that never touches the login keychain.

### Security

- No secret value can appear in `argv`, an exception, a log, or a temporary file: the
  Security framework is called directly through `ctypes`, and the `security` command-line
  tool is not used.
- Exception CLIP-001 (clipboard copy) approved 2026-09-25; see `SECURITY-EXCEPTIONS.md`.
  The command itself is not yet implemented.

### Known limitations

- `set`, `run`, `import`, `list`, `delete`, `init`, `check`, and `copy` are not implemented.
