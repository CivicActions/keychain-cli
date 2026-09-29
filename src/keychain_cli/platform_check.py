"""Refuse to run anywhere but a supported macOS and Python (spec FR-044; constitution III)."""

from __future__ import annotations

import platform
import sys

from keychain_cli.errors import UnsupportedPlatformError

MIN_MACOS_MAJOR = 13
MIN_PYTHON = (3, 11)


def _macos_major() -> int:
    release = platform.mac_ver()[0]
    head = release.split(".", 1)[0]
    return int(head) if head.isdigit() else 0


def ensure_supported() -> None:
    """Raise ``UnsupportedPlatformError`` unless this is macOS 13+ on Python 3.11+."""
    if sys.platform != "darwin":
        raise UnsupportedPlatformError(
            f"unsupported platform {sys.platform!r}; keychain-cli requires macOS",
            "Run it on a Mac. There is deliberately no fallback storage on other systems",
        )
    major = _macos_major()
    if major < MIN_MACOS_MAJOR:
        raise UnsupportedPlatformError(
            f"unsupported macOS version {platform.mac_ver()[0] or 'unknown'}; "
            f"keychain-cli requires macOS {MIN_MACOS_MAJOR} or later",
            "Upgrade macOS to a supported version",
        )
    if sys.version_info < MIN_PYTHON:
        found = ".".join(str(part) for part in sys.version_info[:3])
        wanted = ".".join(str(part) for part in MIN_PYTHON)
        raise UnsupportedPlatformError(
            f"unsupported Python {found}; keychain-cli requires Python {wanted} or later",
            "Reinstall with a newer interpreter, for example: uv tool install keychain-cli",
        )
