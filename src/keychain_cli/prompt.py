"""Interactive input: hidden secret prompts, confirmations, and the stdin value path.

Everything that touches the terminal lives here so commands can be tested with a fake
(constitution VI). Secret entry never echoes (FR-003). The stdin path takes exactly one
value per invocation and strips exactly one trailing newline (FR-004a).
"""

from __future__ import annotations

import getpass
import sys
from collections.abc import Callable
from typing import BinaryIO, Protocol

from keychain_cli.errors import InvalidInputError
from keychain_cli.names import Namespace
from keychain_cli.secret import SecretValue


class Prompter(Protocol):
    """The seam commands use for all terminal interaction."""

    def is_interactive(self) -> bool:
        """True when a person is at a terminal and can answer prompts."""
        ...

    def read_secret(self, prompt: str) -> SecretValue:
        """Read a secret with echo suppressed."""
        ...

    def confirm(self, question: str, *, default: bool = False) -> bool:
        """Ask a yes/no question; an empty answer returns ``default``."""
        ...

    def confirm_exact(self, question: str, expected: Namespace) -> bool:
        """Ask the developer to retype a namespace name."""
        ...

    def read_secret_from_stdin(self) -> SecretValue:
        """Read one value from standard input."""
        ...


def strip_one_newline(data: bytes) -> bytes:
    """Remove exactly one trailing newline (``\\n`` or ``\\r\\n``) if present."""
    if data.endswith(b"\r\n"):
        return data[:-2]
    if data.endswith(b"\n"):
        return data[:-1]
    return data


class TtyPrompter:
    """Production prompter. Talks to ``/dev/tty`` and ``getpass``."""

    def __init__(
        self,
        *,
        stdin: BinaryIO | None = None,
        tty_readline: Callable[[], str] | None = None,
        getpass_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._stdin = stdin
        self._tty_readline = tty_readline or _read_line_from_tty
        self._getpass = getpass_fn or _getpass_to_stderr

    def is_interactive(self) -> bool:
        return sys.stdin.isatty()

    def read_secret(self, prompt: str) -> SecretValue:
        return SecretValue.from_text(self._getpass(prompt))

    def confirm(self, question: str, *, default: bool = False) -> bool:
        sys.stderr.write(f"{question} [{'Y/n' if default else 'y/N'}] ")
        sys.stderr.flush()
        answer = self._tty_readline().strip().lower()
        if not answer:
            return default
        return answer in {"y", "yes"}

    def confirm_exact(self, question: str, expected: Namespace) -> bool:
        sys.stderr.write(f"{question} ")
        sys.stderr.flush()
        answer = self._tty_readline().strip()
        return answer in {expected.display, expected.key}

    def read_secret_from_stdin(self) -> SecretValue:
        stream = self._stdin or sys.stdin.buffer
        data = strip_one_newline(stream.read())
        if not data:
            raise InvalidInputError(
                "no value was supplied on standard input",
                "Pipe exactly one value, or run interactively to be prompted",
            )
        return SecretValue(data)


def _read_line_from_tty() -> str:
    with open("/dev/tty", encoding="utf-8") as tty:  # noqa: PTH123 - device, not a path
        return tty.readline()


def _getpass_to_stderr(prompt: str) -> str:
    return getpass.getpass(prompt, stream=sys.stderr)
