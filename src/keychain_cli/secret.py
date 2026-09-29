"""The one type allowed to hold a secret while it is in process memory.

``SecretValue`` cannot be formatted, printed, or JSON-encoded into a string that contains
the value. ``repr`` and ``str`` are redacted, and ``format`` raises so an f-string cannot
leak it by accident. Code that needs the bytes asks for ``.data`` explicitly, which is easy
to audit with a search.
"""

from __future__ import annotations

from typing import final

REDACTED = "SecretValue(<redacted>)"


@final
class SecretValue:
    """Immutable wrapper around the raw bytes of one secret."""

    __slots__ = ("_data",)

    def __init__(self, data: bytes) -> None:
        # Exact type on purpose: no bytes subclass with a custom repr may hold a secret.
        if type(data) is not bytes:  # pylint: disable=unidiomatic-typecheck
            msg = f"SecretValue takes bytes, not {type(data).__name__}"
            raise TypeError(msg)
        self._data = data

    @classmethod
    def from_text(cls, text: str) -> SecretValue:
        """Wrap a str, encoding it as UTF-8."""
        return cls(text.encode("utf-8"))

    @property
    def data(self) -> bytes:
        """The raw bytes. The only way to read the value."""
        return self._data

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretValue):
            return NotImplemented
        return self._data == other._data

    def __hash__(self) -> int:
        return hash(self._data)

    def __repr__(self) -> str:
        return REDACTED

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, format_spec: str) -> str:  # pylint: disable=invalid-format-returned
        # Raising here is the point: f"{secret}" must fail rather than leak.
        msg = "SecretValue cannot be formatted into a string"
        raise TypeError(msg)
