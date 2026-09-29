"""Test doubles for the side-effect seams. No real Keychain, terminal, or process."""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from keychain_cli.keychain import AlreadyExists, NotFound
from keychain_cli.names import Namespace
from keychain_cli.secret import SecretValue


class InMemoryStore:
    """``SecretStore`` over a dict, with the same semantics as the real store.

    Keyed by ``(namespace.key, name)``; the stored display name is inherited by later
    additions to the same namespace, exactly as the Keychain backend does.
    """

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], tuple[str, SecretValue]] = {}

    def _display(self, namespace: Namespace) -> str:
        for (key, _name), (display, _value) in self.items.items():
            if key == namespace.key:
                return display
        return namespace.display

    def list_namespaces(self) -> list[Namespace]:
        seen: dict[str, Namespace] = {}
        for (key, _name), (display, _value) in self.items.items():
            seen.setdefault(key, Namespace(key=key, display=display))
        return [seen[key] for key in sorted(seen)]

    def list_variables(self, namespace: Namespace) -> list[str]:
        names = sorted(name for (key, name) in self.items if key == namespace.key)
        if not names:
            raise NotFound(namespace.display)
        return names

    def exists(self, namespace: Namespace, name: str) -> bool:
        return (namespace.key, name) in self.items

    def get(self, namespace: Namespace, name: str) -> SecretValue:
        try:
            return self.items[(namespace.key, name)][1]
        except KeyError:
            raise NotFound(name) from None

    def get_all(self, namespace: Namespace) -> dict[str, SecretValue]:
        values = {
            name: value for (key, name), (_d, value) in self.items.items() if key == namespace.key
        }
        if not values:
            raise NotFound(namespace.display)
        return values

    def add(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        if (namespace.key, name) in self.items:
            raise AlreadyExists(name)
        self.items[(namespace.key, name)] = (self._display(namespace), value)

    def update(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        if (namespace.key, name) not in self.items:
            raise NotFound(name)
        display, _old = self.items[(namespace.key, name)]
        self.items[(namespace.key, name)] = (display, value)

    def delete_variable(self, namespace: Namespace, name: str) -> None:
        if (namespace.key, name) not in self.items:
            raise NotFound(name)
        del self.items[(namespace.key, name)]

    def delete_namespace(self, namespace: Namespace) -> int:
        keys = [k for k in self.items if k[0] == namespace.key]
        if not keys:
            raise NotFound(namespace.display)
        for k in keys:
            del self.items[k]
        return len(keys)


@dataclass
class FakePrompts:
    """Scripted terminal. Records every prompt shown; never touches a real tty."""

    interactive: bool = True
    secrets: list[SecretValue] = field(default_factory=list)
    answers: list[bool] = field(default_factory=list)
    stdin_value: SecretValue | None = None
    shown: list[str] = field(default_factory=list)
    stdin_reads: int = 0

    def is_interactive(self) -> bool:
        return self.interactive

    def read_secret(self, prompt: str) -> SecretValue:
        self.shown.append(prompt)
        return self.secrets.pop(0)

    def confirm(self, question: str, *, default: bool = False) -> bool:
        self.shown.append(question)
        return self.answers.pop(0) if self.answers else default

    def confirm_exact(self, question: str, expected: Namespace) -> bool:
        self.shown.append(f"{question} [{expected.display}]")
        return self.answers.pop(0) if self.answers else False

    def read_secret_from_stdin(self) -> SecretValue:
        self.stdin_reads += 1
        if self.stdin_value is None:
            msg = "test did not provide a stdin value"
            raise AssertionError(msg)
        return self.stdin_value


@dataclass
class RecordingExec:
    """Stands in for ``os.execvpe``; records the call instead of replacing the process."""

    calls: list[tuple[str, list[str], dict[str, str]]] = field(default_factory=list)
    raises: BaseException | None = None

    def __call__(self, file: str, argv: Sequence[str], env: Mapping[str, str]) -> None:
        self.calls.append((file, list(argv), dict(env)))
        if self.raises is not None:
            raise self.raises


@dataclass
class RecordingSpawn:
    """Stands in for ``subprocess.Popen``; records argv and everything written to stdin."""

    calls: list[tuple[list[str], dict[str, Any]]] = field(default_factory=list)
    stdin_writes: list[bytes] = field(default_factory=list)
    returncode: int = 0

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> RecordingSpawn._Process:
        self.calls.append((list(argv), dict(kwargs)))
        return RecordingSpawn._Process(self)

    class _Process:
        def __init__(self, owner: RecordingSpawn) -> None:
            self._owner = owner
            self.returncode = owner.returncode
            self.stdin = self

        def write(self, data: bytes) -> int:
            self._owner.stdin_writes.append(data)
            return len(data)

        def close(self) -> None:
            return None

        def communicate(self, data: bytes | None = None) -> tuple[bytes, bytes]:
            if data is not None:
                self._owner.stdin_writes.append(data)
            return b"", b""

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return self.returncode
