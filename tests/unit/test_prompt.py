"""Prompt seam: stdin value rules (FR-004a) and confirmations.

No-echo behaviour (FR-003) comes from ``getpass`` and is verified manually in quickstart
scenario 1, not here; this file drives ``TtyPrompter`` with injected readers only.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import io

import pytest

from keychain_cli.errors import InvalidInputError
from keychain_cli.names import Namespace
from keychain_cli.prompt import TtyPrompter, strip_one_newline
from tests.conftest import LEAK, assert_no_leak


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"tok\n", b"tok"),
        (b"tok\r\n", b"tok"),
        (b"tok", b"tok"),
        (b"tok\n\n", b"tok\n"),
        (b"line1\nline2\n", b"line1\nline2"),
        (
            b"-----BEGIN KEY-----\nabc\n-----END KEY-----\n",
            b"-----BEGIN KEY-----\nabc\n-----END KEY-----",
        ),
        (b" spaced \n", b" spaced "),
    ],
)
def test_strip_one_newline(raw: bytes, expected: bytes) -> None:
    assert strip_one_newline(raw) == expected


def test_stdin_value_round_trips_bytes() -> None:
    prompter = TtyPrompter(stdin=io.BytesIO(LEAK.encode() + b"\n"))
    assert prompter.read_secret_from_stdin().data == LEAK.encode()


@pytest.mark.parametrize("raw", [b"", b"\n", b"\r\n"])
def test_empty_stdin_is_rejected_without_revealing_anything(raw: bytes) -> None:
    prompter = TtyPrompter(stdin=io.BytesIO(raw))
    with pytest.raises(InvalidInputError) as excinfo:
        prompter.read_secret_from_stdin()
    assert excinfo.value.exit_code == 7
    assert "standard input" in excinfo.value.message


@pytest.mark.parametrize(
    ("line", "default", "expected"),
    [
        ("", False, False),
        ("", True, True),
        ("y", False, True),
        ("Y", False, True),
        ("yes", False, True),
        ("n", True, False),
        ("no", True, False),
        ("maybe", True, False),
    ],
)
def test_confirm(
    line: str, default: bool, expected: bool, capsys: pytest.CaptureFixture[str]
) -> None:  # noqa: FBT001
    prompter = TtyPrompter(tty_readline=lambda: line + "\n")
    assert prompter.confirm("Overwrite?", default=default) is expected
    assert "Overwrite?" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("Client-A", True),
        ("client-a", True),
        ("CLIENT-A", False),
        ("client-b", False),
        ("", False),
    ],
)
def test_confirm_exact_accepts_display_or_key(typed: str, expected: bool) -> None:  # noqa: FBT001
    prompter = TtyPrompter(tty_readline=lambda: typed + "\n")
    ns = Namespace(key="client-a", display="Client-A")
    assert prompter.confirm_exact("Type the namespace name to confirm:", ns) is expected


def test_read_secret_uses_injected_getpass_and_never_echoes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: list[str] = []

    def fake_getpass(prompt: str) -> str:
        seen.append(prompt)
        return LEAK

    prompter = TtyPrompter(getpass_fn=fake_getpass)
    value = prompter.read_secret("Value for ns/VAR:")
    assert value.data == LEAK.encode()
    assert seen == ["Value for ns/VAR:"]
    captured = capsys.readouterr()
    assert_no_leak(captured.out, captured.err)
