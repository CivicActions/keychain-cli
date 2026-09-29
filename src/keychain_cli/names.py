"""Namespace and variable name rules (spec FR-007, FR-007a, FR-007b).

Namespaces are matched case-insensitively: ``key`` is the lowercase form used for every
lookup, ``display`` is the casing the developer typed. Variable names are environment
variable names and stay case-sensitive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from keychain_cli.errors import InvalidInputError

NAMESPACE_FORM = (
    "1 to 64 characters: ASCII letters, digits, '-', '_', or '.', starting with a letter or digit"
)
VARIABLE_FORM = (
    "a valid environment variable name: letters, digits, or '_', not starting with a digit"
)

_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Namespace:
    """A validated namespace name.

    ``key`` is used for every lookup and comparison; ``display`` is shown to the developer.
    """

    key: str
    display: str


def validate_namespace(display: str) -> Namespace:
    """Validate a namespace name and derive its lowercase key."""
    if not _NAMESPACE_RE.match(display):
        raise InvalidInputError(
            f"invalid namespace name {display!r}",
            f"Use {NAMESPACE_FORM}",
        )
    return Namespace(key=display.lower(), display=display)


def validate_variable(name: str) -> str:
    """Validate an environment variable name. Returns it unchanged."""
    if not _VARIABLE_RE.match(name):
        raise InvalidInputError(
            f"invalid variable name {name!r}",
            f"Use {VARIABLE_FORM}",
        )
    return name
