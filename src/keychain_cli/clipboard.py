"""Clipboard operations and clearing management (US7, T072).

Deliberate exposure channel governed by SECURITY-EXCEPTIONS.md entry CLIP-001.
"""

from __future__ import annotations

import subprocess  # nosec B404 - CLIP-001: argv list, never a shell string
import sys
from collections.abc import Callable
from typing import Any

from keychain_cli.errors import ClipboardError
from keychain_cli.secret import SecretValue

DEFAULT_CLEAR_AFTER = 45
MIN_CLEAR_AFTER = 1
MAX_CLEAR_AFTER = 300

SpawnFn = Callable[..., Any]


def clear_now(spawn_fn: SpawnFn = subprocess.Popen) -> None:
    """Clear the clipboard immediately by piping empty input to pbcopy."""
    try:
        proc = spawn_fn(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(b"")
    except Exception:  # noqa: BLE001 # nosec B110 - CLIP-001: best-effort clear, failure is silent
        pass


def copy_to_clipboard(value: SecretValue, spawn_fn: SpawnFn = subprocess.Popen) -> None:
    """Copy the secret value to the macOS clipboard via pbcopy."""
    try:
        proc = spawn_fn(["/usr/bin/pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(value.data)
        if proc.returncode != 0:
            raise ClipboardError(
                "clipboard write failed",
                "Ensure pbcopy is accessible and working in your session",
            )
    except ClipboardError:
        raise
    except Exception as err:
        raise ClipboardError(
            f"clipboard write failed: {err}",
            "Ensure pbcopy is accessible and working in your session",
        ) from None


def schedule_clear(digest: str, seconds: int, spawn_fn: SpawnFn = subprocess.Popen) -> None:
    """Spawn the detached clearing helper to clear the clipboard after `seconds`."""
    try:
        proc = spawn_fn(
            [sys.executable, "-m", "keychain_cli._clipclear"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        proc.stdin.write(f"{digest}\n{seconds}\n".encode())
        proc.stdin.close()
    except Exception as err:
        clear_now(spawn_fn)
        raise ClipboardError(
            f"failed to schedule clipboard clearing: {err}",
            "value was not left on the clipboard; retry or paste from another source",
        ) from None
