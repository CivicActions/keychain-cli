"""The Keychain access layer behind one narrow seam.

Commands depend on ``SecretStore`` and never on the Security framework directly, so every
command can be unit-tested against an in-memory fake (constitution VI). The only production
implementation is ``keychain_cli.keychain.store.SecurityFrameworkStore``; import it lazily
so that a non-macOS run fails at the platform check before any framework loads.

This module deliberately imports no ``ctypes`` code.
"""

from __future__ import annotations

from typing import Protocol

from keychain_cli.errors import KeychainError as StoreError
from keychain_cli.names import Namespace
from keychain_cli.secret import SecretValue

__all__ = [
    "AlreadyExists",
    "Namespace",
    "NotFound",
    "SecretStore",
    "StoreError",
]


class AlreadyExists(Exception):
    """The variable already holds a value. Commands decide whether to overwrite."""


class NotFound(Exception):
    """The namespace or variable does not exist."""


class SecretStore(Protocol):
    """Everything the tool ever asks of the Keychain.

    List operations request attributes only and never secret data. Errors from the
    underlying store are raised as ``StoreError`` carrying the OS status and OS message,
    never a value.
    """

    def list_namespaces(self) -> list[Namespace]:
        """All namespaces that hold at least one variable, sorted by ``key``."""
        ...

    def list_variables(self, namespace: Namespace) -> list[str]:
        """Sorted variable names. Raises ``NotFound`` if the namespace holds none."""
        ...

    def exists(self, namespace: Namespace, name: str) -> bool:
        """Whether the variable holds a value. Reads no secret data."""
        ...

    def get(self, namespace: Namespace, name: str) -> SecretValue:
        """One value. Raises ``NotFound``."""
        ...

    def get_all(self, namespace: Namespace) -> dict[str, SecretValue]:
        """Every variable in the namespace. Raises ``NotFound`` if there are none."""
        ...

    def add(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        """Store a new variable. Raises ``AlreadyExists``; never overwrites."""
        ...

    def update(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        """Replace an existing value. Raises ``NotFound``."""
        ...

    def delete_variable(self, namespace: Namespace, name: str) -> None:
        """Remove one variable. Raises ``NotFound``."""
        ...

    def delete_namespace(self, namespace: Namespace) -> int:
        """Remove every variable in the namespace. Returns the count; raises ``NotFound`` if 0."""
        ...
