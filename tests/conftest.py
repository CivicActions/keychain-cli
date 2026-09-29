"""Shared fixtures. Unit tests never touch the Keychain, a terminal, or a real process."""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from keychain_cli import cli
from tests.fakes import FakePrompts, InMemoryStore, RecordingExec, RecordingSpawn

# Distinctive placeholder used as a secret in tests. Never a real credential. Allowlisted
# in .gitleaks.toml so the scanner does not flag it.
LEAK = "LEAKCHECK-7f3a-placeholder"

RunCli = Callable[..., tuple[int, str, str]]


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def prompts() -> FakePrompts:
    return FakePrompts()


@pytest.fixture
def exec_fn() -> RecordingExec:
    return RecordingExec()


@pytest.fixture
def spawn_fn() -> RecordingSpawn:
    return RecordingSpawn()


@pytest.fixture
def run_cli(
    store: InMemoryStore,
    prompts: FakePrompts,
    exec_fn: RecordingExec,
    spawn_fn: RecordingSpawn,
    capsys: pytest.CaptureFixture[str],
) -> RunCli:
    """Run ``cli.main`` with every seam injected. Returns ``(exit_code, stdout, stderr)``."""

    def _run(argv: Sequence[str], *, tty: bool = True) -> tuple[int, str, str]:
        prompts.interactive = tty
        code = cli.main(
            list(argv),
            store_factory=lambda: store,
            prompts=prompts,
            exec_fn=exec_fn,
            spawn_fn=spawn_fn,
        )
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def assert_no_leak(*texts: object) -> None:
    """Assert the placeholder secret appears in none of the given texts."""
    for text in texts:
        assert LEAK not in str(text), "secret placeholder leaked into output"
