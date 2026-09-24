# Feature Specification: Keychain Secret Manager

**Feature Branch**: `001-keychain-secret-manager`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Build a small command-line secret management tool for developers using macOS. The purpose is to replace plaintext .env files with secrets stored securely in macOS Keychain while preserving a simple developer workflow."

## User Scenarios & Testing *(mandatory)*

The minimum viable product is **User Story 1 + User Story 2**: storing secrets and running a
command with them. Those two together let a developer delete a `.env` file and keep working.
Stories 3–6 make that transition easier, safer, and repeatable across a team, but the tool
delivers its core value without them.

### User Story 1 - Store project secrets in the Keychain (Priority: P1)

A developer working on a client project has API tokens and database passwords sitting in a
plaintext `.env` file. They create a named namespace for the project and type each secret
value at a prompt. The values go into the macOS Keychain. Nothing is echoed to the screen,
nothing lands in shell history, and nothing is written to a project file.

**Why this priority**: This is the foundational capability — no other story can function
without stored secrets. On its own it already delivers value: secrets move off disk and into
OS-protected storage.

**Independent Test**: Run the store command for a new namespace with three variable names,
enter values at the prompts, and confirm that (a) no value appeared on screen, (b) no value
appears in shell history, (c) the names are afterwards retrievable while the values are not
displayed, and (d) the values are present in the macOS Keychain.

**Acceptance Scenarios**:

1. **Given** no namespace named `client-a` exists, **When** the developer runs the store
   command naming `client-a` and three variable names, **Then** the tool prompts once per
   variable, accepts input without echoing it, stores each value in the Keychain, and reports
   success without printing any value.
2. **Given** a value is being typed at a prompt, **When** the developer looks at the terminal,
   **Then** no characters of the secret are visible, and no length indication is revealed.
3. **Given** the store command has completed, **When** the developer inspects their shell
   history, **Then** the command line appears but contains only the namespace and variable
   names, never a value.
4. **Given** the variable `API_TOKEN` already holds a value in namespace `client-a`, **When**
   the developer runs the store command for `API_TOKEN` again, **Then** the tool refuses to
   overwrite silently and requires an explicit confirmation or an explicit overwrite option.
5. **Given** the developer declines the overwrite confirmation, **When** the command ends,
   **Then** the previously stored value is unchanged and the exit status indicates no change
   was made.
6. **Given** the terminal cannot prompt (no interactive input available) and no alternative
   input has been supplied, **When** the store command runs, **Then** the tool fails with a
   clear non-zero error rather than storing an empty value.
7. **Given** a token sits alone in a single-line file, **When** the developer pipes that file
   into the store command naming exactly one variable, **Then** the value is read from standard
   input, a single trailing newline is removed, the remainder is stored unchanged, and nothing
   is displayed.
8. **Given** standard input is being used to supply a value, **When** the store command names
   more than one variable, **Then** the tool refuses before reading anything, because standard
   input can carry only one value unambiguously.

---

### User Story 2 - Run a command with project secrets (Priority: P1)

A developer starts their development server the way they always have, but prefixes it with
the tool and a namespace. The application receives its environment variables and behaves
exactly as it did with a `.env` file. The developer's own shell is untouched — after the
command finishes, no secret remains in their session.

**Why this priority**: This is the point of the tool. Without it, secrets are stored safely
but unusable, and the developer has no reason to give up their `.env` file.

**Independent Test**: Store a namespace, run a command that prints its own environment, and
confirm the variables are present in the child process. Then inspect the parent shell and
confirm the variables are absent there, both during and after the run.

**Acceptance Scenarios**:

1. **Given** namespace `client-a` holds three variables, **When** the developer runs a command
   through the tool with that namespace, **Then** the launched process and its descendants see
   all three variables in their environment.
2. **Given** a command has been run through the tool, **When** the developer inspects their own
   shell environment afterwards, **Then** none of the namespace's variables are present.
3. **Given** the launched command exits with a specific status code, **When** the tool returns,
   **Then** the tool exits with that same status code so scripts and task runners behave
   normally.
4. **Given** the named namespace does not exist (no variable is stored under it), **When** the
   developer runs a command with it, **Then** the tool fails with a clear non-zero error and
   **does not launch the command**, so nothing runs with credentials silently missing.
5. **Given** the developer interrupts the running command, **When** the interrupt is delivered,
   **Then** it reaches the child process and the tool exits without leaving an orphaned
   process.
6. **Given** the command to run does not exist, **When** the tool attempts to launch it,
   **Then** the tool reports a clear error distinguishable from a secret-retrieval failure.
7. **Given** any failure occurs during the run, **When** the error is displayed, **Then** it
   contains no secret value and no partial secret value.

---

### User Story 3 - Import an existing .env file (Priority: P2)

A developer has an existing `.env` file with a dozen variables. Rather than retyping each
value, they point the tool at the file and it loads the variables into a namespace in one
step. The file is left on disk — deleting it is the developer's decision, made deliberately.

**Why this priority**: This is the adoption path. Retyping a dozen secrets by hand is exactly
the friction that causes a team to abandon a tool and keep the `.env` file.

**Independent Test**: Create a `.env` file containing well-formed entries, a comment, a blank
line, and a malformed line. Import it. Confirm all valid variables are stored, the malformed
line produces a warning naming the line but not its content, and the original file still
exists unchanged.

**Acceptance Scenarios**:

1. **Given** a `.env` file with well-formed `KEY=value` entries, **When** the developer imports
   it into a namespace, **Then** every entry is stored and no value is displayed at any point.
2. **Given** the `.env` file contains comment lines and blank lines, **When** it is imported,
   **Then** those lines are ignored without warnings.
3. **Given** the `.env` file contains a malformed entry, **When** it is imported, **Then** the
   tool warns about that entry identifying it by line number and, where safely derivable, by
   variable name — **never by its content** — and continues processing the remaining entries.
4. **Given** the import has completed, **When** the developer checks the filesystem, **Then**
   the original `.env` file is still present and unmodified.
5. **Given** the `.env` file contains a variable that already exists in the namespace, **When**
   it is imported, **Then** the existing value is not overwritten without explicit
   confirmation or an explicit overwrite option.
6. **Given** the `.env` file contains a value wrapped in single or double quotes, **When** it is
   imported, **Then** the surrounding quotes are removed and the inner value is stored.
7. **Given** the import finishes, **When** the summary is printed, **Then** it reports counts
   of stored, skipped, and malformed entries and lists affected variable names, with no values.

---

### User Story 4 - See which namespaces exist and what each holds (Priority: P2)

A developer returning to a project after two weeks needs to know what a namespace contains
before running anything. They list the namespace and see variable names only. A developer
who cannot remember what they called a project lists the namespaces themselves and sees the
names, exactly as they originally typed them.

**Why this priority**: Verification and recall. Without it, the Keychain is a write-only
store and developers cannot confirm that a store or import actually did what they expected.

**Independent Test**: Store three variables in one namespace and one variable in a second
namespace. List the first namespace and confirm the output contains exactly those three
names, in a predictable order, with no values. List the namespaces and confirm exactly the
two names appear, in the casing originally given.

**Acceptance Scenarios**:

1. **Given** namespace `client-a` holds three variables, **When** the developer lists it,
   **Then** exactly those three variable names are printed, one per line, and no values appear.
2. **Given** the developer lists a namespace, **When** the output is compared across runs,
   **Then** the ordering is stable and predictable.
3. **Given** the named namespace does not exist, **When** the developer lists it, **Then** the
   tool reports that clearly with a non-zero status, without implying a value was withheld.
4. **Given** the developer requests machine-readable output, **When** the command runs, **Then**
   the output is parseable by a script and still contains no values.
5. **Given** namespaces `client-a` and `Client-B` hold at least one variable each, **When** the
   developer lists the namespaces, **Then** exactly those two names are printed, one per line,
   in the casing originally given, in a stable order, and no variable names or values appear.
6. **Given** no namespace holds any variable, **When** the developer lists the namespaces,
   **Then** the output is empty, the exit status indicates success, and the tool does not
   report an error, because an empty store is a valid state and not a failure.
7. **Given** the developer requests machine-readable output for the namespace listing, **When**
   the command runs, **Then** the output is parseable by a script and contains names only.

---

### User Story 5 - Remove a secret or a whole namespace (Priority: P2)

A client engagement ends. The developer deletes the entire namespace. Or a single token is
rotated out of use and they delete just that one variable.

**Why this priority**: Secret lifecycle. A store that cannot forget accumulates stale
credentials indefinitely, which is itself a security problem.

**Independent Test**: Store a namespace with three variables. Delete one and confirm the other
two remain. Delete the namespace and confirm all are gone and the namespace no longer lists.

**Acceptance Scenarios**:

1. **Given** a namespace with three variables, **When** the developer deletes one named
   variable, **Then** only that variable is removed and the others are untouched.
2. **Given** a namespace with three variables, **When** the developer deletes the namespace
   itself, **Then** the tool requires confirmation before proceeding, because the operation is
   destructive and irreversible.
3. **Given** the deletion is confirmed, **When** it completes, **Then** every variable in that
   namespace is removed from the Keychain and the namespace no longer appears in listings.
4. **Given** the developer is running non-interactively, **When** they delete without an
   explicit force option, **Then** the tool refuses rather than assuming consent.
5. **Given** the named variable or namespace does not exist, **When** deletion is attempted,
   **Then** the tool reports it clearly with a non-zero status and changes nothing.
6. **Given** a namespace holds exactly one variable, **When** the developer deletes that
   variable, **Then** the namespace no longer appears in the namespace listing, because a
   namespace exists only while it holds at least one variable.

---

### User Story 6 - Set up a project from a committed manifest (Priority: P3)

A developer joins a project. The repository contains a manifest listing the variable names the
project requires — names only, safe to commit. They run one command, are prompted for each
value they do not already have, and are then ready to work.

**Why this priority**: Team onboarding and drift detection. Valuable, but a solo developer
gets full value from the tool without it, and it depends on Stories 1 and 4 already working.

**Independent Test**: Write a manifest listing three variables, store one of them beforehand,
run the initialize command, and confirm the developer is prompted for exactly the two missing
variables and not the one already present.

**Acceptance Scenarios**:

1. **Given** a manifest listing three required variables and a namespace holding none of them,
   **When** the developer initializes from the manifest, **Then** they are prompted for all
   three, without echo, and the values are stored.
2. **Given** a manifest listing three variables and a namespace already holding one of them,
   **When** the developer initializes, **Then** they are prompted only for the two missing
   ones and the existing value is left untouched.
3. **Given** all manifest variables are already stored, **When** the developer initializes,
   **Then** the tool reports that the namespace is complete and prompts for nothing.
4. **Given** the manifest is malformed or missing required fields, **When** initialization is
   attempted, **Then** the tool reports a clear error and stores nothing.
5. **Given** a manifest exists, **When** its contents are inspected, **Then** it contains
   namespace and variable names only and no mechanism exists by which the tool would write a
   secret value into it.
6. **Given** the developer wants to verify readiness without storing anything, **When** they
   check the namespace against the manifest, **Then** the tool reports which required
   variables are missing, by name.

---

### User Story 7 - Retrieve one value for use elsewhere (Priority: P3)

A developer needs to paste an API token into a vendor's web console. They ask for that one
variable by name and it lands on the clipboard, ready to paste. It never appears on screen,
and it leaves the clipboard shortly afterwards.

**Why this priority**: Without a supported path for this, the developer's fallback is to copy
the value back into a plaintext file — reintroducing exactly the risk the tool removes. It is
P3 because it is occasional rather than daily, and everything else works without it. This
story is optional: the tool is complete without it, and it is never the default way to reach
a value.

**Independent Test**: Store a variable, request it, paste from the clipboard and confirm the
value is correct, confirm nothing was printed to the terminal, then wait past the documented
interval and confirm the clipboard no longer holds it.

**Acceptance Scenarios**:

1. **Given** namespace `client-a` holds `API_TOKEN`, **When** the developer requests that one
   variable, **Then** its value is placed on the clipboard and the terminal shows only a
   confirmation naming the variable, the clearing interval, and a warning that clipboard
   history tools may retain the value.
2. **Given** a value has been copied, **When** the documented interval elapses, **Then** the
   value is removed from the clipboard automatically.
3. **Given** a value has been copied and the developer then copies something else, **When** the
   interval elapses, **Then** the developer's newer clipboard content is left intact.
4. **Given** the developer requests a variable that does not exist, **When** the command runs,
   **Then** it fails clearly and the clipboard is not modified.
5. **Given** the developer asks for an entire namespace rather than one named variable, **When**
   the command runs, **Then** it is refused — there is no bulk reveal.
6. **Given** the automatic clearing helper cannot be started, **When** the command runs,
   **Then** the clipboard is cleared immediately, the command exits non-zero, and the
   developer is told the value was not left on the clipboard.
7. **Given** the developer supplies a clearing interval outside the documented bounds,
   **When** the command runs, **Then** it is rejected before anything is copied.
8. **Given** any command other than the copy command runs, **When** it completes or fails,
   **Then** the clipboard is untouched.

---

### Edge Cases

**Secret handling**

- A secret value containing spaces, quotes, newlines, or non-ASCII characters must round-trip
  through storage and into the child process unchanged.
- An empty value entered at a prompt: the tool must confirm intent rather than silently
  storing an empty secret, since an empty secret usually means a mistyped prompt.
- A very long secret value (for example a multi-kilobyte private key) must either store
  correctly or fail with a clear limit message — never truncate silently.

**Storage and platform**

- The Keychain is locked, or the user denies or cancels the Keychain authorization prompt: the
  tool must fail closed with a clear message and must not launch any command.
- The Keychain is unavailable or returns an unexpected error: fail closed, non-zero, no
  partial state.
- The tool is run on a platform other than macOS: it must exit immediately with a clear error
  rather than degrade to any less protected storage.
- A partially completed multi-variable store or import is interrupted: the tool must report
  precisely which variables were stored and which were not.

**Naming and input**

- A variable name that is not a valid environment variable name (contains spaces, starts with
  a digit, is empty) must be rejected at entry with a clear message.
- A namespace name outside the allowed form (see FR-007a) must be rejected at entry with a
  message stating the allowed form, rather than silently mangled or truncated.
- Two namespace names differing only by case refer to the same namespace. The casing given
  when the namespace was first created is the one shown in every listing and report; a later
  command that names it with different casing operates on the same namespace and does not
  change the displayed casing.
- Two variable names differing only by case are distinct variables, because environment
  variable names are case-sensitive. `Api_Token` and `API_TOKEN` may coexist in one namespace
  and are both delivered to the child process.
- A variable name that duplicates one already listed in the same command invocation.
- A value supplied on standard input that is empty, or consists only of a newline: treated as
  the empty-value case above and must not be stored without confirmation.
- A value supplied on standard input that contains more than one line: stored unchanged apart
  from the single trailing newline, since a multi-line value such as a private key is valid.

**Running commands**

- The command to run is omitted entirely, or the separator between tool options and the target
  command is missing: the tool must explain the correct form rather than guessing.
- A namespace variable has the same name as a variable already present in the developer's
  environment: the namespace value takes precedence for the child process (see Assumptions).
- The launched command is long-running and the tool must not hold secret values in memory
  longer than needed to hand them to the child.
- The launched command itself prints its environment: this is outside the tool's control and
  is the developer's responsibility, but the tool's own output must never do so.

**Import**

- A `.env` file with duplicate keys: the tool must apply a defined, documented rule and report
  it, rather than silently taking one.
- A `.env` file with `export KEY=value` prefixes, trailing comments, or multi-line values.
- A `.env` file that is empty, unreadable due to permissions, or not a file at all.
- A `.env` file large enough that prompting for confirmation per entry would be unreasonable.

**Manifest and namespace inference**

- The namespace is omitted and no manifest exists in the current directory: fail clearly,
  naming both ways to resolve it, rather than guessing or falling back to a default.
- A manifest exists but declares a namespace that holds no stored values yet: the developer
  should be pointed at the initialize command rather than shown a bare lookup failure.
- A manifest declares one namespace and the developer explicitly names a different one: the
  explicit name wins, and the tool reports which it used so the mismatch is visible.
- A manifest is present in a parent directory but not the current one: the tool must define
  and document whether it searches upward, and behave consistently either way.
- A manifest declares a variable name that is not a valid environment variable name.
- A manifest is syntactically valid but declares an empty variable list.

**Clipboard**

- The clipboard is unavailable or the copy fails: report it clearly and exit non-zero, rather
  than leaving the developer believing a value was copied when it was not.
- The developer copies other content before the auto-clear interval elapses: their newer
  content must survive — the tool clears only if its own value is still present.
- The tool is terminated before it can clear the clipboard: the value remains until the
  developer copies something else. This residual exposure must be documented, not hidden.
- A clipboard manager or sync service captures clipboard history: outside the tool's control,
  and a documented limitation of this command.

## Requirements *(mandatory)*

### Functional Requirements

**Storing secrets**

- **FR-001**: System MUST allow a developer to create a named namespace and store one or more
  named variables within it in a single invocation.
- **FR-002**: System MUST prompt for each value interactively, one prompt per variable,
  identifying the namespace and variable name being requested.
- **FR-003**: System MUST NOT echo secret input to the terminal during entry, and MUST NOT
  reveal the length of the value being typed.
- **FR-004**: System MUST NOT accept a secret value as a command-line argument in any command.
- **FR-004a**: System MUST accept a value from standard input, as the only non-prompt entry
  path, when standard input is not a terminal or when the developer explicitly requests it.
  This path MUST be limited to exactly one variable per invocation and MUST be refused, before
  any input is read, if more than one variable is named. Exactly one trailing newline, if
  present, MUST be removed; the remaining content MUST be stored unchanged.
- **FR-005**: System MUST store all secret values in the macOS Keychain.
- **FR-006**: System MUST refuse to overwrite an existing stored value unless the developer
  explicitly confirms the overwrite interactively, or explicitly requests overwriting via an
  option when running non-interactively.
- **FR-007**: System MUST validate variable names as valid environment variable names and
  reject invalid names with a clear message before prompting for any value. Variable names
  are case-sensitive: names differing only by case are distinct variables.
- **FR-007a**: System MUST validate namespace names before any other action. A namespace name
  MUST be 1 to 64 characters, consist only of ASCII letters, digits, hyphens, underscores, and
  periods, and begin with a letter or digit. A name outside this form MUST be rejected with a
  message stating the allowed form.
- **FR-007b**: System MUST treat namespace names as case-insensitive for every lookup,
  comparison, and match, and MUST preserve the casing given when the namespace was first
  created for display in every listing and report. A namespace MUST NOT be silently split or
  duplicated because it was later named with different casing.
- **FR-008**: System MUST report, on completion, which variables were stored and which were
  skipped, by name only.

**Importing**

- **FR-009**: System MUST import variables from an existing `.env`-style file into a named
  namespace.
- **FR-010**: System MUST parse common `KEY=value` syntax, including comment lines, blank
  lines, optional `export ` prefixes, and values wrapped in single or double quotes.
- **FR-011**: System MUST NOT display any imported value at any point during or after import.
- **FR-012**: System MUST warn about malformed entries, identifying them by line number and by
  variable name where one is safely derivable, and MUST NOT display the content of a malformed
  line — because a malformed line may itself be, or contain, a secret.
- **FR-013**: System MUST continue processing remaining entries after encountering a malformed
  entry, and MUST report a summary of stored, skipped, and malformed counts.
- **FR-014**: System MUST NOT delete, move, or modify the source file.
- **FR-015**: System MUST apply the overwrite protection of FR-006 to imported variables.

**Listing**

- **FR-016**: System MUST list the variable names stored in a given namespace without
  displaying any value.
- **FR-017**: System MUST produce a stable, predictable ordering for listed names.
- **FR-018**: System MUST offer a machine-readable output form for both variable listing and
  namespace listing, containing names only.
- **FR-019**: System MUST provide a way to list the namespaces that exist, showing each name
  in its originally given casing, in the stable ordering of FR-017, without any variable names
  or values. When no namespace exists the listing MUST be empty and MUST exit successfully;
  an empty store is a valid state, not an error.

**Revealing a single value (optional capability)**

- **FR-019a**: The tool MAY provide an explicit command to copy a single secret value to the
  macOS clipboard for workflows that cannot consume environment variables. Clipboard use MUST
  never be the default secret-access mechanism. The tool MUST avoid printing the secret and
  SHOULD clear the clipboard after a configurable short timeout when it can do so without
  overwriting newer clipboard contents. If the command is provided, FR-019b through FR-019h
  apply to it.
- **FR-019b**: The clipboard MUST be written only by that explicit command. No other command,
  option, or failure path MAY place a value on the clipboard.
- **FR-019c**: The command MUST copy exactly one named variable per invocation. There MUST be
  no bulk copy, no wildcard, and no form that copies an entire namespace.
- **FR-019d**: The command MUST NOT print the value to the terminal, write it to a file, or
  place it in any process's command-line arguments. Confirmation output MUST state only that
  the named variable was copied and when it will be cleared.
- **FR-019e**: The command MUST clear the copied value from the clipboard automatically after
  a short timeout, MUST clear only if the clipboard still holds that value so a developer's
  later copy is never destroyed, and MUST accept a bounded override of the timeout with a
  documented secure default. If automatic clearing cannot be scheduled, the command MUST clear
  the clipboard immediately and fail with a non-zero status rather than leave the value in
  place with no clearing.
- **FR-019f**: The command MUST warn, in its confirmation output, that reliable clearing
  cannot be guaranteed: clipboard history tools, clipboard managers, and clipboard sync
  services may retain the value after it is cleared.
- **FR-019g**: Help text and documentation MUST state that the clipboard is readable by other
  applications running as the same user, how long the value remains there, and that
  clipboard managers can defeat automatic clearing.
- **FR-019h**: Documentation MUST present clipboard copy as an occasional path for
  destinations that cannot read environment variables. It MUST NOT appear in the primary
  `.env`-replacement guidance, the install-to-first-secret walkthrough, or any example of
  daily use.

**Running commands**

- **FR-020**: System MUST run a developer-specified command with the namespace's variables
  present in that command's environment.
- **FR-020a**: System MUST accept the namespace explicitly, and MUST allow it to be omitted
  when a manifest in the current directory declares one. An explicitly named namespace always
  takes precedence over a manifest-declared one.
- **FR-020b**: System MUST report which namespace it selected, on standard error, whenever the
  namespace was inferred rather than named — so the choice is never silent.
- **FR-020c**: System MUST fail with a clear error, without launching anything, when the
  namespace is omitted and no manifest declares one.
- **FR-020d**: System MUST NOT infer the namespace for destructive operations. Deleting a
  variable or a namespace MUST always name it explicitly.
- **FR-021**: System MUST make secrets available only to the launched process and its
  descendants, and MUST NOT modify the environment of the invoking shell.
- **FR-022**: System MUST NOT place any secret value in the command-line arguments of the
  launched process or of any other process it starts.
- **FR-023**: System MUST propagate the launched command's exit status as its own exit status.
- **FR-024**: System MUST forward terminal signals to the launched process and MUST NOT leave
  orphaned child processes on exit.
- **FR-025**: System MUST fail without launching the command if the namespace does not exist
  (that is, holds no variables) or cannot be read.
- **FR-026**: System MUST connect the launched command's input and output streams to the
  terminal so that interactive programs behave normally.

**Deleting**

- **FR-027**: System MUST allow deletion of a single named variable from a namespace.
- **FR-028**: System MUST allow deletion of an entire namespace and all variables within it.
- **FR-029**: System MUST require interactive confirmation before deleting a namespace, and
  MUST require an explicit force option to do so non-interactively.
- **FR-030**: System MUST report clearly and exit non-zero when asked to delete something that
  does not exist, and MUST change nothing in that case.

**Manifest**

- **FR-031**: System MUST support a project manifest file in TOML format (`.keychain-cli.toml`)
  that declares a namespace and the list of variable names the project requires.
- **FR-032**: System MUST NOT write secret values into the manifest, and MUST provide no option
  or code path that would do so.
- **FR-033**: System MUST initialize a namespace from a manifest by prompting only for the
  variables that are not already stored.
- **FR-034**: System MUST report a clear error and store nothing when the manifest is missing,
  malformed, or lacks required fields.
- **FR-035**: System MUST provide a way to report which manifest-required variables are
  currently missing from the namespace, by name, without storing anything.

**Cross-cutting security**

- **FR-036**: System MUST NOT write any secret value to a log, temporary file, cache, or any
  file the system itself creates.
- **FR-037**: System MUST NOT include any secret value, or any partial secret value, in any
  error message, warning, diagnostic, or stack trace.
- **FR-038**: System MUST NOT reveal information that narrows a secret's value, including its
  length, prefix, suffix, or character composition.
- **FR-039**: System MUST NOT require the developer to type a secret value on a command line
  in any documented workflow.
- **FR-040**: System MUST fail closed — aborting with a non-zero status — whenever it cannot
  verify that a security precondition holds.

**Errors and platform**

- **FR-041**: System MUST use documented, stable exit codes that let a caller distinguish
  success, general failure, and specific failure conditions without parsing message text.
- **FR-042**: System MUST send normal output to standard output and diagnostics and errors to
  standard error.
- **FR-043**: System MUST state, in every error message, what failed and what the developer can
  do next.
- **FR-044**: System MUST exit with a clear error when run on any platform other than macOS.
- **FR-045**: System MUST provide built-in help sufficient to use any command without
  consulting external documentation.

### Key Entities

- **Namespace**: A named grouping of secrets belonging to one project or context (for example
  `client-a`). A namespace exists exactly when at least one variable is stored in it: storing
  the first variable creates it, and deleting the last variable removes it. There is no
  separate create or empty state. Names are matched case-insensitively and displayed in the
  casing first given. Namespaces are independent; no nesting or inheritance.
- **Variable**: A named secret within a namespace. Has a name that is a valid environment
  variable name, and a value that is never displayed. The name is treated as non-sensitive
  metadata; the value is always sensitive.
- **Manifest**: A committed, plaintext TOML project file (`.keychain-cli.toml`) declaring a
  namespace name and the list of variable names the project requires. Contains no values.
  Represents the project's *requirements*, while the Keychain holds the developer's
  *fulfillment* of them. Also supplies the default namespace when one is not named explicitly.
- **Keychain Entry**: The stored representation of a variable's value in the macOS Keychain.
  Sole system of record for secret values; the tool keeps no other copy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with an existing `.env` file can move it into the Keychain and run
  their normal development command successfully in under 5 minutes, without reading source
  code or documentation beyond built-in help.
- **SC-002**: Across every command and every failure path, the number of secret values that
  appear in terminal output, shell history, error messages, files created by the tool, or the
  arguments of any process is **zero**, demonstrated by automated tests.
- **SC-003**: After running any command through the tool, the invoking shell contains zero
  variables from the namespace, verified by comparing the environment before and after.
- **SC-004**: An existing development command produces identical behavior whether its variables
  come from a `.env` file or from the tool, with no change to the application itself.
- **SC-005**: A developer joining a project with a committed manifest reaches a working setup
  in under 2 minutes, being prompted only for values they do not already have.
- **SC-006**: Every security-relevant behavior named in the Cross-cutting security requirements
  has at least one automated test asserting the negative case, with no gaps at release.
- **SC-007**: The added delay between invoking a command through the tool and that command
  beginning to run is under 1 second on a typical developer machine.
- **SC-008**: Every failure path exits non-zero with a documented exit code and a message
  naming both the cause and the next action, verified for all enumerated error conditions.
- **SC-009**: Zero secret values are written to any project file, verified by inspecting the
  working tree after a full exercise of every command.
- **SC-010**: A value copied to the clipboard is no longer present there after the documented
  interval, in 100% of test runs, and a developer's subsequent clipboard content is never
  destroyed by the tool's cleanup.

## Assumptions

- **Single-developer scope.** Each developer's Keychain holds their own values. No sharing,
  syncing, or distribution of secret values between developers is in scope; the manifest
  shares *names* only.
- **Environment precedence.** When a namespace variable has the same name as one already in
  the developer's environment, the namespace value takes precedence for the child process.
  This matches expectations from `.env` loaders and is the reason the developer invoked the
  tool. The parent environment is otherwise inherited so that `PATH` and similar continue to
  work.
- **Duplicate keys on import.** When a `.env` file defines the same key twice, the last
  occurrence wins, matching common `.env` loader behavior, and the tool reports that a
  duplicate was collapsed.
- **Non-interactive value entry.** Where a value must be supplied without a terminal prompt,
  it is read from standard input rather than from an argument, one variable per invocation
  (FR-004a). This is the supported migration path for files that hold a single bare token with
  no key name. Automating secret storage in CI is not a target workflow for this release.
- **Namespace casing.** Namespace names are typed by hand, and `Client-A` and `client-a`
  almost always mean the same project, so treating them as different would create silent
  duplicates and confusing lookup failures. Variable names are not folded because environment
  variable names are case-sensitive by definition and the child process must receive exactly
  the name the developer stored.
- **Trusted local machine.** The threat model addresses secrets at rest, secrets in process
  arguments visible to other local users, and secrets leaking into files and history. It does
  not address an attacker who already has code execution as the developer's own user.
- **Keychain authorization.** The developer may be prompted by macOS to authorize access. This
  is expected behavior, is controlled by the OS rather than the tool, and is not suppressed.
- **Project constraints from the constitution.** macOS only, Python, standard-library-first,
  no external secret managers, no GUI, no shell-wide export mode, no agent sandboxing. These
  are fixed for this release and are not revisited in this specification.
- **Manifest is advisory.** A manifest declares what a project needs. It does not grant access,
  and its presence is never required for the other commands to function.
- **Manifest format is TOML.** Chosen because it is parseable by the Python standard library,
  satisfying the constitution's standard-library-first principle without an external
  dependency, while still allowing comments in a hand-edited file. This sets the project's
  minimum Python version at 3.11, where TOML parsing entered the standard library.
- **Namespace inference is convenience, not authority.** A manifest in the current directory
  supplies a default namespace when none is typed, and the selection is always reported.
  Destructive commands never infer. Whether the tool searches parent directories for a manifest
  is deferred to planning and must be documented either way.
- **The clipboard is a bounded, deliberate, optional exposure.** Copying a value to the
  clipboard places it somewhere other applications running as the same user can read, and
  clipboard managers or sync services may capture it and defeat automatic clearing. This is
  accepted as the least-bad option for a use case whose realistic alternative is a plaintext
  file, and it is mitigated by an explicit single-variable command, automatic clearing with a
  short bounded timeout, a per-use warning, and exclusion from the primary guidance. The
  capability is optional (FR-019a MAY); a release that omits it is complete. Planning records
  it in the constitution's security exception register.

## Out of Scope

Explicitly excluded from this release, to be revisited only by a later specification:

- Windows and Linux support, and any cross-platform storage abstraction.
- Cloud or hosted secret managers.
- Team synchronization or sharing of secret *values*.
- Any graphical interface.
- A shell-wide `eval`-style export mode that injects secrets into the developer's own shell.
- Revealing more than one secret at a time, or revealing to standard output or a file. The
  clipboard path of User Story 7 is the only supported way to retrieve a value.
- AI-agent sandboxing, command interception, or dangerous-command blocklists.
- Secret rotation, expiry, versioning, or audit logging.
- Import from INI-style, profile-sectioned files such as `~/.aws/credentials`. The import
  command reads flat `KEY=value` files only. Such files are migrated one profile at a time with
  the store command, using the variable names the consuming tool expects.
- Acting as a credential helper or credential process for other tools, for example the AWS
  `credential_process` setting or git credential helpers. These require emitting a secret
  value on standard output, which FR-019b forbids.
