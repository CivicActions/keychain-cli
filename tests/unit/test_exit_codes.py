"""Exit code verification against contracts and documentation (T078)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import re
from pathlib import Path

import pytest

from keychain_cli.errors import (
    EXIT_CHECK_MISSING,
    EXIT_INTERRUPTED,
    ClipboardError,
    CommandNotFoundError,
    InvalidInputError,
    KeychainCliError,
    KeychainError,
    NotFoundError,
    RefusedError,
    UnsupportedPlatformError,
    UsageError,
)


@pytest.mark.parametrize(
    ("err_cls", "expected_code"),
    [
        (KeychainCliError, 1),
        (UsageError, 2),
        (NotFoundError, 3),
        (RefusedError, 4),
        (KeychainError, 5),
        (UnsupportedPlatformError, 6),
        (InvalidInputError, 7),
        (CommandNotFoundError, 8),
        (ClipboardError, 9),
    ],
)
def test_exception_exit_codes(err_cls: type[KeychainCliError], expected_code: int) -> None:
    assert err_cls.exit_code == expected_code


def test_special_exit_codes() -> None:
    assert EXIT_CHECK_MISSING == 10
    assert EXIT_INTERRUPTED == 130


def test_readme_exit_codes_table_matches_code() -> None:
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")

    # Match lines like | 0 | Success |
    matches = re.findall(r"^\|\s*(\d+)\s*\|\s*([^|]+)\s*\|", readme, re.MULTILINE)
    assert matches

    readme_codes = {int(code_str): desc.strip() for code_str, desc in matches if code_str.isdigit()}

    expected_codes = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 130}
    assert expected_codes.issubset(readme_codes.keys())
