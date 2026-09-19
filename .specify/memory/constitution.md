<!--
SYNC IMPACT REPORT (temporary — remove before committing the amended file)

Version change: 1.0.0 → 2.0.0
Bump rationale: MAJOR. This amendment removes and redefines principles in
backward-incompatible ways, rather than merely expanding guidance:
  1. "II. Ease of Use" is removed as a standalone principle. Its still-applicable rules
     (CLI conventions, actionable errors, confirmation on destructive operations) are
     preserved under "VIII. Fail Safely" and "Additional Constraints".
  2. "IV. Test-First (NON-NEGOTIABLE)" is redefined. Mandatory red-green-refactor TDD for
     all code is no longer required; the NON-NEGOTIABLE obligation now attaches
     specifically to security-sensitive behavior (new Principle VII). Relaxing a
     NON-NEGOTIABLE principle is backward-incompatible by the versioning policy below.
  3. Secrets-at-rest is narrowed from "platform keychain or an equivalent audited backend"
     to the macOS Keychain specifically, with non-macOS platforms explicitly out of scope.

Modified principles:
- I. Secure by Default → split into II. Secrets Never Surface and IV. Least Privilege
- II. Ease of Use → REMOVED (absorbed into VIII. Fail Safely + Additional Constraints)
- III. Code Quality → VI. Readable, Testable, Maintainable Code
- IV. Test-First (NON-NEGOTIABLE) → VII. Security-Sensitive Behavior Is Tested
  (NON-NEGOTIABLE), narrowed in scope
- V. Maintainability → folded into VI; dependency discipline promoted to V. Standard
  Library First

Added sections:
- I. Security and Simplicity Over Feature Breadth (NON-NEGOTIABLE)
- III. macOS Keychain Is the System of Record
- IV. Least Privilege (promoted from the Security Requirements section)
- V. Standard Library First
- VIII. Fail Safely
- "Additional Constraints" replaces "Security Requirements", now covering platform scope,
  CLI surface, and supply chain

Removed sections: none beyond the principle noted above

Resolved from v1.0.0:
- TODO(PROJECT_DOMAIN) — RESOLVED. Confirmed: a small security-focused Python CLI that
  stores and retrieves secrets via the macOS Keychain.
- TODO(SUPPORTED_PLATFORMS) — RESOLVED. macOS only for the initial release.

Follow-up TODOs: none.
-->

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

A secret value MUST NOT appear anywhere except the destination the user explicitly asked
for on that invocation. Prohibited channels include, and are not limited to:

- Logs, debug output, and telemetry of any kind.
- Command-line arguments — of this tool **and of any subprocess it spawns**. `argv` is
  readable by other users via `ps`. Secrets MUST be passed to subprocesses over stdin or a
  file descriptor, never as an argument. This constraint applies directly to invocations of
  the macOS `security` binary.
- Exceptions, tracebacks, error messages, and crash reports. Exception objects MUST NOT
  carry secret values, since any uncaught handler may print them.
- Shell history. The tool MUST NOT require or document a usage pattern that places a secret
  on a shell command line.
- Temporary files, caches, swap-backed buffers, and any path the tool creates.
- Committed files. Test fixtures, examples, and documentation MUST use obvious placeholder
  values. A real secret reaching the repository is a security incident, not a cleanup task.

Echo of secret input MUST be suppressed at interactive prompts.

*Rationale: every one of these channels has leaked a credential in a real incident, and
each leak is silent — the user has no way to observe it.*

### III. macOS Keychain Is the System of Record

- Secrets at rest MUST be stored in the macOS Keychain. The tool MUST NOT implement its own
  storage, encryption, or key management for secret material.
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
- Secret material MUST be held in memory for the shortest practical time and dropped as
  soon as it is consumed.
- Files the tool creates MUST be created with owner-only permissions, set at creation time
  rather than adjusted afterward.

*Rationale: exposure scope is the blast radius of every other mistake in this list.*

### V. Standard Library First

- The Python standard library MUST be preferred. An external dependency requires a
  substantial, stated security or maintainability benefit over a standard-library
  implementation — convenience alone does not qualify.
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
- Secrets are never placed in the argv of the tool or of any spawned subprocess.
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
- Destructive operations MUST require interactive confirmation, and an explicit
  force-style flag when not interactive.
- Exit codes MUST be documented and stable, so callers can distinguish failure modes
  without parsing message text.

*Rationale: the moment of failure is exactly when a tool is most likely to print something
it should not, and most likely to be retried by a script that ignores the difference.*

## Additional Constraints

**Platform and language.** macOS only, Python only, for the initial release. The minimum
supported macOS and Python versions MUST be stated in the README and enforced at startup
with a clear error.

**CLI surface.** Input arrives via stdin, interactive no-echo prompt, or a caller-supplied
file path — never via a secret-bearing argument. Normal output goes to `stdout`,
diagnostics and errors to `stderr`, `0` on success and documented non-zero codes on
failure. Commands SHOULD offer a machine-readable output mode so the tool composes in
scripts without screen-scraping. `--help` MUST be sufficient to use a command without
external documentation.

**Threat model.** A written threat model MUST exist and MUST be revisited whenever a new
input path, subprocess invocation, or storage interaction is added. At minimum it MUST
account for other local processes reading `argv` and environment; other users on a shared
host; backup, sync, and crash-reporting systems capturing files at rest; shell history and
terminal scrollback; and untrusted input reaching the parser.

**Supply chain.** Builds MUST be reproducible from the committed lockfile. Release
artifacts MUST be produced by CI, not from a developer workstation. A secret-scanning check
MUST run in CI and MUST block the merge on a hit.

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
- **Planning.** Features proceed through the Spec Kit flow — specify, plan, tasks,
  implement. Implementation plans MUST record a Constitution Check against each principle
  and MUST justify any deviation in the plan's complexity-tracking section.
- **Deviations.** A principle may be departed from only with a recorded justification naming
  the simpler alternative that was rejected and why. An unjustified deviation blocks the
  merge. Principles marked NON-NEGOTIABLE are not subject to this escape hatch.
- **Release.** Releases MUST be tagged, built by CI, and accompanied by a changelog
  separating breaking changes, features, fixes, and security fixes. The tool follows
  semantic versioning; any change to a command name, flag, exit code, or output format is
  breaking and MUST land in a MAJOR release with a documented migration path.

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
  principles MUST NOT be waived by review discretion; changing one requires an amendment.
- **Normative language.** MUST and MUST NOT are hard requirements. SHOULD indicates a strong
  default that requires a recorded reason to depart from.
- **Runtime guidance.** Day-to-day contributor and agent guidance lives in the repository's
  agent guidance file and in `.specify/`. Those documents MUST remain consistent with this
  constitution; on conflict, this constitution wins and the other document MUST be
  corrected.

**Version**: 2.0.0 | **Ratified**: 2026-09-18 | **Last Amended**: 2026-09-19
