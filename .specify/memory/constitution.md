# Keychain CLI Constitution

Keychain CLI is a small, security-focused command-line tool for storing and retrieving
secrets on macOS. It is maintained by CivicActions developers and written in Python.

## Core Principles

### I. Security and Simplicity Over Feature Breadth (NON-NEGOTIABLE)

When security, simplicity, and features conflict, they are ranked in that order. This
ordering is not advisory and MUST NOT be reweighted per feature.

- A feature that cannot be implemented securely MUST NOT be implemented.
- The simplest design that satisfies the requirement wins. Abstraction, configurability,
  and indirection MUST be justified by a present need, never an anticipated one.
- Scope growth MUST be resisted by default. "It would also be nice if" is grounds for
  rejection, not for a new flag.
- Every added configuration option is an added way to be insecure and MUST be justified
  against a secure default that needs no option at all.

*Rationale: a small tool that does one thing safely is auditable by a single reader in a
single sitting. That property is the product.*

### II. Secrets Never Surface (NON-NEGOTIABLE)

Secrets MUST NOT be exposed through shell history, logs, temporary files, error messages, or
command-line arguments under normal operation. Secret transfer to external processes MUST
use stdin, file descriptors, or platform APIs where available. Any exception MUST be
explicit, documented, and justified.

The channels named above are illustrative, not exhaustive. The following apply in
particular:

- `argv` is readable by other local users via `ps`. The prohibition covers the arguments of
  this tool **and of any process it spawns**.
- Exception objects MUST NOT carry secret values, since any uncaught handler may print them.
  This holds even where the message is never expected to reach a user.
- Committed files MUST NOT contain secrets. Test fixtures, examples, and documentation MUST
  use obvious placeholder values. A real secret reaching the repository is a security
  incident, not a cleanup task.
- Echo of secret input MUST be suppressed at interactive prompts.
- Caches, swap-backed buffers, and any path the tool creates are covered by the temporary
  files clause.

**Documented exceptions.** An exception is a deliberate, bounded departure — not a
convenience. To be explicit, documented, and justified, it MUST:

- Be recorded in the security exception register (see Additional Constraints), naming the
  exact invocation or code path, the exposure window, and who or what can observe it.
- State why no stdin, file-descriptor, or platform-API alternative is available, and what
  was tried.
- Be approved by a project maintainer. Ordinary reviewer discretion is not sufficient.
- Be pinned by an automated test that asserts the boundary, so the exception cannot silently
  widen.
- Carry a re-evaluation trigger — the API, dependency, or platform change that would remove
  the need for it.

An undocumented departure is a violation of this principle, not an exception to it.

*Rationale: every channel named here has leaked a credential in a real incident, and each
leak is silent — the user has no way to observe it. Exceptions are survivable; undocumented
ones are not, because nobody knows to look.*

### III. macOS Keychain Is the System of Record

- Secrets at rest MUST be stored in the macOS Keychain. The tool MUST NOT implement its own
  storage, encryption, or key management for secret material.
- Keychain access SHOULD use an API integration that does not expose secrets in process
  arguments. `/usr/bin/security` MAY be used where its invocation does not place secret
  values in `argv` — for example, paths that read the secret from stdin or that handle no
  secret value at all. An invocation that would place a secret in `argv` requires a
  documented exception under Principle II.
- The tool MUST NOT maintain a plaintext copy, cache, index, or mirror of secret values
  outside the Keychain. Non-secret metadata may be stored elsewhere only if it cannot be
  used to infer a secret.
- macOS is the only supported platform for the initial release. Cross-platform support is
  explicitly out of scope; code MUST NOT be complicated by portability abstractions for
  backends that are not yet in scope.
- On a non-macOS platform the tool MUST exit with a clear, non-zero failure rather than
  degrade to a less protected fallback.

*Rationale: the Keychain is audited, OS-integrated, and already trusted by the user's
machine. Reimplementing it would be the least defensible code in the project.*

### IV. Least Privilege

Secret material MUST be exposed to the narrowest possible scope, for the shortest possible
time, to the fewest possible processes.

- A secret MUST be delivered only to the process that needs it. Broadcast mechanisms —
  exporting into a shell environment inherited by unrelated children, writing to a shared
  location — MUST NOT be the default path.
- The tool MUST request the narrowest Keychain access that satisfies the operation and MUST
  NOT require elevated privileges for normal use.
- Secret material MUST be held in memory for the shortest practical time and dropped as soon
  as it is consumed.
- Files the tool creates MUST be created with owner-only permissions, set at creation time
  rather than adjusted afterward.

*Rationale: exposure scope is the blast radius of every other mistake in this list.*

### V. Standard Library First

- The Python standard library MUST be preferred. An external dependency requires a
  substantial, stated security or maintainability benefit over a standard-library
  implementation — convenience alone does not qualify. Eliminating a Principle II exception
  is such a benefit.
- Each dependency MUST be recorded with the justification that admitted it, so a future
  maintainer can re-evaluate rather than guess.
- Dependencies MUST be pinned to resolved versions in a committed lockfile and scanned for
  known vulnerabilities in CI. A build with a known-exploitable high or critical advisory
  MUST NOT ship.
- Cryptographic primitives, if any are ever needed beyond what the Keychain provides, MUST
  come from a vetted maintained library. Hand-rolled crypto is forbidden.

*Rationale: every dependency is code this project has not reviewed but is nonetheless
trusted with secrets, and it is code that can be compromised upstream.*

### VI. Readable, Testable, Maintainable Code

The standard is that a CivicActions developer who has never seen this codebase can read a
module, understand what it does, and change it safely.

- Clarity beats cleverness. Code that requires a comment to explain *what* it does SHOULD be
  rewritten rather than annotated; comments explain *why*.
- Functions MUST have a single clear responsibility and MUST be callable in tests without
  elaborate setup. Code that is hard to test is hard to trust and MUST be restructured.
- Side effects — Keychain access, subprocess invocation, filesystem writes — MUST be
  isolated behind narrow seams so they can be exercised and substituted in tests.
- Formatting and linting MUST be automated and enforced in CI; style MUST NOT be a topic of
  human review. Warnings MUST be treated as errors.
- Errors MUST be handled explicitly where they can be acted on. Silently swallowing an
  exception is forbidden.
- Commands, flags, exit codes, and output formats MUST be documented at the point of
  definition, and user-visible changes MUST update their documentation in the same change
  set.

*Rationale: this tool will be read far more often than it is written, and most of those
readings will be security reviews.*

### VII. Security-Sensitive Behavior Is Tested (NON-NEGOTIABLE)

Any behavior covered by Principles II, III, IV, or VIII MUST have automated tests, written
in the same change set as the behavior. Such a change MUST NOT merge without them.

Required coverage includes:

- Secret values are absent from logs, `stdout`, `stderr`, and exception text on both the
  success and failure paths.
- Secrets do not appear in the argv of the tool or of any spawned subprocess, except where a
  documented Principle II exception applies — in which case a test MUST pin the exception's
  exact boundary and assert that no other path shares it.
- Failure paths fail closed, with the documented non-zero exit code.
- Malformed, hostile, and unexpected input — arguments, stdin, files, and Keychain
  responses — is rejected rather than misinterpreted.
- Created files carry owner-only permissions.

Additional requirements:

- Every bug fix MUST begin with a regression test that fails before the fix.
- Tests MUST be deterministic and order-independent. A flaky test MUST be fixed or removed,
  never retried into passing.
- Tests MUST NOT contain real secrets.

*Rationale: a leak is invisible to the user, so tests are the only place where the absence
of a leak is ever actually checked.*

### VIII. Fail Safely

- On any unverifiable precondition or unexpected state, the tool MUST abort with a non-zero
  exit code rather than continue in a degraded or less protected mode.
- Error messages MUST state what failed, why, and the next action the user can take. They
  MUST NOT include secret values, and MUST NOT include details that narrow a secret's value
  — no lengths, prefixes, character classes, or partial matches.
- Whether an item exists in the Keychain is itself information; error text MUST NOT
  distinguish "wrong secret" from "no such item" in a way that aids enumeration beyond what
  the user is already authorized to see.
- Destructive operations MUST require interactive confirmation, and an explicit force-style
  flag when not interactive.
- Exit codes MUST be documented and stable, so callers can distinguish failure modes without
  parsing message text.

*Rationale: the moment of failure is exactly when a tool is most likely to print something
it should not, and most likely to be retried by a script that ignores the difference.*

### IX. Usable by Default

The audience is CivicActions developers using this tool as part of daily work. The bar is
that a developer who has not used it before can accomplish a common task from `--help`
alone, without reading source, copying an incantation from a teammate, or consulting an
internal wiki page.

- Common operations MUST work in a single invocation with no prior configuration step.
  Defaults MUST be secure; a flag MUST NOT be required in order to be safe.
- The safe path MUST be the default path and the convenient path. Where an unsafe usage
  exists, it MUST be harder to reach than the safe one — never the reverse.
- Users MUST NOT be required to assemble the secure invocation themselves. If correct use
  depends on the caller remembering to pipe, quote, or redirect correctly, the interface is
  the defect.
- Command names, flag names, and output shapes MUST be predictable and consistent across
  commands. A flag meaning one thing in one command and something else in another is a bug.
- Friction MUST be treated as a security risk rather than an inconvenience. A workflow that
  is awkward enough to be worked around produces the workaround this tool exists to
  prevent — a secret in a dotfile, an exported environment variable, a note in a ticket.
  Repeated friction reports are evidence of a design defect and MUST be triaged as such.
- The README MUST carry a short documented path from install to first stored secret, and it
  MUST be verified to work on a clean machine at each release.
- Interface mechanics — streams, exit codes, machine-readable output, `--help` — are
  specified under Additional Constraints, "CLI surface", and are requirements of this
  principle.

Where usability genuinely conflicts with Principle I or Principle II, I and II win. Such a
conflict MUST be recorded rather than absorbed silently: a security constraint that keeps
producing painful ergonomics usually indicates the design is wrong, not that the user is.

*Rationale: usability is a security control. A credential tool is only protective while it
is actually used, and a team that finds it tedious will quietly return to the plaintext
file it replaced. "Reasonably easy" is therefore a security requirement, not a nicety.*

## Additional Constraints

**Platform and language.** macOS only, Python only, for the initial release. The minimum
supported macOS and Python versions MUST be stated in the README and enforced at startup
with a clear error.

**Security exception register.** A single file in the repository MUST list every active
Principle II exception, each with its justification, exposure window, approving maintainer,
pinning test, and re-evaluation trigger. An empty register is the expected steady state. The
register MUST be reviewed at each release; an exception whose re-evaluation trigger has
fired MUST be closed or renewed.

**CLI surface.** Input arrives via stdin, interactive no-echo prompt, or a caller-supplied
file path — never via a secret-bearing argument. Normal output goes to `stdout`, diagnostics
and errors to `stderr`, `0` on success and documented non-zero codes on failure. Commands
whose output is intended to be consumed by scripts MUST offer a machine-readable output
mode, so the tool composes without screen-scraping. `--help` MUST be sufficient to use a
command without external documentation.

**Threat model.** A written threat model MUST exist and MUST be revisited whenever a new
input path, subprocess invocation, or storage interaction is added. At minimum it MUST
account for other local processes reading `argv` and environment; other users on a shared
host; backup, sync, and crash-reporting systems capturing files at rest; shell history and
terminal scrollback; and untrusted input reaching the parser.

**Supply chain.** Builds MUST be reproducible from the committed lockfile. Release artifacts
MUST be produced by CI, not from a developer workstation. A secret-scanning check MUST run
in CI and MUST block the merge on a hit.

**Vulnerability response.** A security defect takes priority over all feature work. A
disclosure contact and a supported-versions statement MUST be published before the first
public release.

## Development Workflow & Quality Gates

- **Merge gates.** No change merges unless formatting, linting, the full test suite, the
  dependency vulnerability scan, and the secret scan all pass. These gates MUST be
  automated; manual attestation does not satisfy them.
- **Review.** Every change requires review by someone other than its author. For any change
  touching secret handling, Keychain access, subprocess invocation, file creation, or error
  and log output, the reviewer MUST explicitly confirm compliance with Principles II, IV,
  VII, and VIII. A review that does not state this confirmation does not clear the gate.
- **Planning.** Features proceed through the Spec Kit flow — specify, plan, tasks, implement.
  Implementation plans MUST record a Constitution Check against each principle and MUST
  justify any deviation in the plan's complexity-tracking section. A plan that selects a
  Keychain access mechanism MUST state whether it places secrets in `argv`, and if so MUST
  open a Principle II exception before implementation begins.
- **Usability check.** A change that adds or alters a command, flag, prompt, or output
  format MUST be exercised by someone other than its author, using only `--help` and the
  README. If that reviewer needs to read the source or ask the author how to run it,
  Principle IX is not satisfied and the change does not clear the gate.
- **Deviations.** A principle may be departed from only with a recorded justification naming
  the simpler alternative that was rejected and why. An unjustified deviation blocks the
  merge. Principles marked NON-NEGOTIABLE are not subject to this escape hatch; where such a
  principle defines its own exception process, that process is the only available route.
- **Release.** Releases MUST be tagged, built by CI, and accompanied by a changelog
  separating breaking changes, features, fixes, and security fixes. The tool follows semantic
  versioning; any change to a command name, flag, exit code, or output format is breaking and
  MUST land in a MAJOR release with a documented migration path.

## Governance

This constitution supersedes all other development practices for this project. Where other
guidance conflicts with it, this document controls.

- **Amendments** MUST be proposed as a change to this file, MUST state the rationale and the
  version bump with its justification, and MUST be approved by project maintainers before
  merging. An amendment that invalidates existing code MUST include a migration plan.
- **Versioning** of this constitution follows semantic versioning:
  - MAJOR — a principle is removed, or redefined in a backward-incompatible way. Relaxing a
    NON-NEGOTIABLE principle is always MAJOR.
  - MINOR — a principle or section is added, or existing guidance is materially expanded.
  - PATCH — clarifications, wording, and typo fixes that do not change obligations.
- **Compliance review.** Every pull request MUST be checked against these principles, and
  every implementation plan MUST carry an explicit Constitution Check. NON-NEGOTIABLE
  principles MUST NOT be waived by reviewer discretion. Where a NON-NEGOTIABLE principle
  defines its own exception process, that process — including its maintainer approval and
  register entry — is the only route to a departure, and using it is not a waiver.
- **Normative language.** MUST and MUST NOT are hard requirements. SHOULD indicates a strong
  default that requires a recorded reason to depart from.
- **Runtime guidance.** Day-to-day contributor and agent guidance lives in the repository's
  agent guidance file and in `.specify/`. Those documents MUST remain consistent with this
  constitution; on conflict, this constitution wins and the other document MUST be corrected.

**Version**: 3.1.0 | **Ratified**: 2026-09-18 | **Last Amended**: 2026-09-19
