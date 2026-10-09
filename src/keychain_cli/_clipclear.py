"""Detached clipboard clearing helper (US7, T071).

Runs detached in its own session, sleeps for the specified seconds, and clears
the clipboard only if its contents still match the expected SHA-256 digest.
"""

from __future__ import annotations

import hashlib
import subprocess  # nosec B404 - CLIP-001: argv list, never a shell string
import sys
import time


def main() -> int:
    """Read digest and interval from stdin, sleep, and clear if unmodified."""
    try:
        raw_digest = sys.stdin.readline().strip()
        raw_seconds = sys.stdin.readline().strip()
        if not raw_digest or not raw_seconds:
            return 0
        seconds = float(raw_seconds)
    except (ValueError, OSError):
        return 0

    time.sleep(seconds)

    try:
        current = subprocess.check_output(["/usr/bin/pbpaste"])  # noqa: S603 # nosec B603 - CLIP-001
        if hashlib.sha256(current).hexdigest() == raw_digest:
            proc = subprocess.Popen(  # noqa: S603 # nosec B603 - CLIP-001
                ["/usr/bin/pbcopy"], stdin=subprocess.PIPE
            )
            proc.communicate(b"")
    except Exception:  # noqa: BLE001 # nosec B110 - CLIP-001: best-effort clear, failure is silent
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
