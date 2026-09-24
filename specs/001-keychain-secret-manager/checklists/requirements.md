# Specification Quality Checklist: Keychain Secret Manager

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Validation run 1 — 2026-09-22.** 15/16 pass. Three open [NEEDS CLARIFICATION] markers at
FR-031, FR-019a, and FR-020, presented to the user as Questions 1–3.

**Validation run 2 — 2026-09-22.** 16/16 pass. All three questions answered (option A each):

- **FR-031** — manifest format resolved to TOML (`.keychain-cli.toml`). Parseable by the
  standard library, satisfying the constitution's Principle V with no external dependency.
  Consequence recorded in Assumptions: minimum Python 3.11.
- **FR-019a–e** — a single-variable, clipboard-only reveal is in scope. Added User Story 7
  (P3), five functional requirements, four clipboard edge cases, and SC-010. Standard-output
  and bulk reveal are now explicitly listed under Out of Scope.
- **FR-020a–d** — the namespace may be inferred from a manifest in the current directory when
  omitted, an explicit name always wins, the selection is always reported on standard error,
  and destructive commands never infer.

**Content Quality, item 1 — passes with a noted exception.** The spec names the macOS Keychain
and TOML. Neither is a design-time technology choice: Keychain storage is the defining product
requirement, and the manifest format is a user-visible, committed file that developers edit by
hand. The Assumptions section names Python 3.11 as an inherited project constraint from the
constitution; no functional requirement depends on it.

**Carried into planning** (recorded in Assumptions, not blocking this spec):

- Whether the tool searches parent directories for a manifest. Must be decided and documented
  either way; FR-020a–c hold regardless.
- Whether the clipboard reveal warrants an entry in the constitution's security exception
  register. The clipboard is readable by other applications running as the same user, which
  makes it an exposure channel in the sense of Principle II even though it is deliberate,
  bounded, and explicitly invoked.

**Testability note.** SC-002, SC-003, SC-006, SC-009, and SC-010 are written as assertions an
automated test can make directly, supporting the constitution's requirement that
security-sensitive behavior be tested. FR-036 through FR-040 are phrased as negative
requirements so each maps to a specific failing test.

**Amendment 2026-09-24.** Seven gaps found while checking the spec against two real
migration sources (an AWS credentials file and single-line token files). All closed in the
spec; checklist result unchanged at 16/16:

- Namespace listing (FR-019) gained acceptance scenarios 5–7 under User Story 4, including the
  empty-store case, and FR-018 now covers machine-readable namespace output.
- A namespace now exists exactly when it holds at least one variable (Key Entities, FR-025,
  User Story 5 scenario 6), removing the contradiction with the former "zero or more" wording.
- Namespace name rules added as FR-007a (allowed form) and FR-007b (case-insensitive match,
  original casing displayed). Variable names remain case-sensitive (FR-007). The former edge
  case forbidding case merges was replaced accordingly.
- Standard-input value entry promoted from an assumption to FR-004a, single variable only,
  one trailing newline stripped; User Story 1 scenarios 7–8 and two edge cases added.
- INI-style, profile-sectioned import and credential-helper integrations added to Out of
  Scope.

**Carried into planning** from the same review:

- The Keychain attribute layout that lets the tool find its own items (a fixed ownership
  stamp plus a per-namespace service string, with the case-folded name in the match key and
  the display casing stored alongside), and the choice of the Security framework over the
  `security` command, which has no multi-match query.
- Keychain items are trusted to the interpreter binary that created them, so a different
  Python path triggers an authorization prompt by design. Document to prevent misdiagnosis.
- The command shape: a bare list command enumerates namespaces; the same command with a
  namespace argument enumerates its variables.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
