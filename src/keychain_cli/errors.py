"""User-facing errors and the exit-code table.

Every exception here carries only strings. Constructors reject anything that is not ``str``
so a secret value, or its length, can never ride on an exception into an error message
(constitution Principle II; spec FR-037, FR-038). Exit codes are the contract in
``specs/001-keychain-secret-manager/contracts/cli.md``.
"""

from __future__ import annotations

# Non-error results that still use a distinct exit status.
EXIT_CHECK_MISSING = 10
EXIT_INTERRUPTED = 130


def _require_text(value: object, what: str) -> str:
    # Exact type on purpose: a str subclass could override __str__ to reveal a value.
    if type(value) is not str:  # pylint: disable=unidiomatic-typecheck
        msg = f"{what} must be a plain str, not {type(value).__name__}"
        raise TypeError(msg)
    return value


class KeychainCliError(Exception):
    """Base class. Exit code 1 means an unexpected internal error."""

    exit_code = 1

    def __init__(self, message: str, next_step: str) -> None:
        self.message = _require_text(message, "message")
        self.next_step = _require_text(next_step, "next_step")
        super().__init__(self.message)


class UsageError(KeychainCliError):
    """Bad arguments, missing ``--``, or an out-of-range option."""

    exit_code = 2


class NotFoundError(KeychainCliError):
    """Namespace, variable, file, or manifest does not exist."""

    exit_code = 3


class RefusedError(KeychainCliError):
    """The developer declined, or consent could not be asked for non-interactively."""

    exit_code = 4


class KeychainError(KeychainCliError):
    """The Keychain refused or failed. Carries the OS status and OS message only."""

    exit_code = 5

    def __init__(self, os_status: int, os_message: str) -> None:
        if type(os_status) is not int:  # pylint: disable=unidiomatic-typecheck
            msg = "os_status must be an int"
            raise TypeError(msg)
        self.os_status = os_status
        self.os_message = _require_text(os_message, "os_message")
        super().__init__(
            f"Keychain operation failed: {self.os_message} (status {self.os_status})",
            "Make sure your login keychain is unlocked and you approved any macOS prompt, "
            "then retry",
        )


class UnsupportedPlatformError(KeychainCliError):
    """Not macOS, or too old a macOS or Python."""

    exit_code = 6


class InvalidInputError(KeychainCliError):
    """Bad name, malformed manifest, empty or ambiguous stdin value, unreadable file."""

    exit_code = 7


class CommandNotFoundError(KeychainCliError):
    """``run``: the target command does not exist or is not executable."""

    exit_code = 8


class ClipboardError(KeychainCliError):
    """``copy``: clipboard write failed or clearing could not be scheduled."""

    exit_code = 9


def format_error(error: KeychainCliError) -> str:
    """Render one error line: what failed, then what to do next."""
    return f"keychain-cli: {error.message}. {error.next_step}"
