"""Integration tests for real macOS clipboard interactions (US7, T070)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.integration.conftest import CliEnv, Sandbox, assert_sandbox_clean

if TYPE_CHECKING:
    from keychain_cli.keychain.store import SecurityFrameworkStore


def _pbpaste() -> bytes:
    try:
        return subprocess.check_output(["/usr/bin/pbpaste"])  # noqa: S603
    except Exception:  # noqa: BLE001
        pytest.skip("macOS pasteboard server is not accessible")


def _pbcopy(data: bytes) -> None:
    proc = subprocess.Popen(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)  # noqa: S603
    proc.communicate(data)


@pytest.fixture(autouse=True)
def preserve_clipboard() -> Iterator[None]:
    prior = _pbpaste()
    try:
        yield
    finally:
        _pbcopy(prior)


def test_clipboard_copy_and_clearing(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    _pbpaste()  # check pasteboard server is available

    ns = validate_namespace("clip-ns")
    placeholder = "CLIP-SECRET-VAL"
    real_store.add(ns, "TOKEN", SecretValue.from_text(placeholder))

    # 1. copy sets clipboard
    code, stdout, stderr = cli_env(["copy", "clip-ns", "TOKEN", "--clear-after", "1"])
    assert code == 0
    assert "cleared in 1 seconds" in stderr
    assert _pbpaste().decode() == placeholder

    # 2. poll pbpaste until cleared
    start = time.time()
    cleared = False
    while time.time() - start < 5.0:
        if _pbpaste() == b"":
            cleared = True
            break
        time.sleep(0.25)
    assert cleared, "clipboard was not cleared within 5 seconds"

    assert_sandbox_clean(sandbox, placeholder)


def test_clipclear_does_not_clear_newer_content() -> None:
    _pbpaste()

    # Set initial text
    initial = b"initial-secret"
    _pbcopy(initial)
    digest = hashlib.sha256(initial).hexdigest()

    # Spawn _clipclear with interval 1
    proc = subprocess.Popen(
        [sys.executable, "-m", "keychain_cli._clipclear"],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    proc.stdin.write(f"{digest}\n1\n".encode())
    proc.stdin.close()

    # User immediately copies newer text
    newer = b"newer-user-content"
    _pbcopy(newer)

    # Wait for helper to exit
    proc.wait(timeout=5.0)

    # Newer content remains untouched
    assert _pbpaste() == newer
