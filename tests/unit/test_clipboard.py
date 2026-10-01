"""Unit tests for clipboard operations and the CLIP-001 pinning test (US7, T067)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

import pytest

from keychain_cli.clipboard import copy_to_clipboard, schedule_clear
from keychain_cli.errors import ClipboardError
from keychain_cli.secret import SecretValue
from tests.conftest import LEAK
from tests.fakes import RecordingSpawn


def test_copy_to_clipboard_spawns_pbcopy_with_stdin() -> None:
    spawn = RecordingSpawn()
    secret = SecretValue(b"my-clipboard-secret")
    copy_to_clipboard(secret, spawn_fn=spawn)

    assert len(spawn.calls) == 1
    argv, kwargs = spawn.calls[0]
    assert argv == ["/usr/bin/pbcopy"]
    assert kwargs.get("stdin") == subprocess.PIPE
    assert spawn.stdin_writes == [b"my-clipboard-secret"]


def test_schedule_clear_spawns_helper_with_stdin() -> None:
    spawn = RecordingSpawn()
    digest = hashlib.sha256(b"my-secret").hexdigest()
    schedule_clear(digest, 45, spawn_fn=spawn)

    assert len(spawn.calls) == 1
    argv, kwargs = spawn.calls[0]
    assert argv == [sys.executable, "-m", "keychain_cli._clipclear"]
    assert kwargs.get("start_new_session") is True
    assert kwargs.get("stdout") == subprocess.DEVNULL
    assert kwargs.get("stderr") == subprocess.DEVNULL
    assert spawn.stdin_writes == [f"{digest}\n45\n".encode()]


def test_value_reaches_only_pbcopy_stdin() -> None:
    """CLIP-001 PINNING TEST: Secret value appears ONLY in pbcopy stdin, never in argv."""
    spawn = RecordingSpawn()
    secret = SecretValue.from_text(LEAK)

    copy_to_clipboard(secret, spawn_fn=spawn)
    digest = hashlib.sha256(secret.data).hexdigest()
    schedule_clear(digest, 30, spawn_fn=spawn)

    # 1. Secret bytes appear in no spawned argv
    for argv, _kwargs in spawn.calls:
        for arg in argv:
            assert LEAK not in arg
            assert secret.data not in arg.encode()

    # 2. Secret bytes appear only in pbcopy stdin, not in helper stdin
    assert len(spawn.stdin_writes) == 2
    assert spawn.stdin_writes[0] == secret.data
    assert LEAK.encode() not in spawn.stdin_writes[1]
    assert digest.encode() in spawn.stdin_writes[1]


def test_pbcopy_failure_raises_clipboard_error() -> None:
    spawn = RecordingSpawn()
    spawn.returncode = 1
    secret = SecretValue.from_text("val")

    with pytest.raises(ClipboardError) as exc:
        copy_to_clipboard(secret, spawn_fn=spawn)
    assert exc.value.exit_code == 9
    assert "clipboard write failed" in exc.value.message


def test_helper_spawn_failure_clears_clipboard_and_raises() -> None:
    class FailingSpawn(RecordingSpawn):
        def __call__(self, argv: Sequence[str], **kwargs: Any) -> RecordingSpawn._Process:
            if "_clipclear" in " ".join(argv):
                raise OSError("Simulated spawn failure")
            return super().__call__(argv, **kwargs)

    spawn = FailingSpawn()
    secret = SecretValue.from_text("val")
    copy_to_clipboard(secret, spawn_fn=spawn)

    digest = hashlib.sha256(secret.data).hexdigest()
    with pytest.raises(ClipboardError) as exc:
        schedule_clear(digest, 45, spawn_fn=spawn)

    assert exc.value.exit_code == 9
    assert "not left on the clipboard" in exc.value.next_step

    # Check clear_now was called (empty stdin to pbcopy)
    assert len(spawn.calls) == 2
    assert spawn.calls[1][0] == ["/usr/bin/pbcopy"]
    assert spawn.stdin_writes[-1] == b""
