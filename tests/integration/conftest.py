"""Integration fixtures. macOS only. Every test uses a throwaway keychain file.

The developer's login keychain is never read, written, or listed by this suite.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from keychain_cli.keychain.store import SecurityFrameworkStore

if sys.platform != "darwin":
    collect_ignore_glob = ["test_*.py"]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def temp_keychain(tmp_path: Path) -> Iterator[int]:
    from keychain_cli.keychain.store import TemporaryKeychain

    with TemporaryKeychain(tmp_path) as keychain:
        yield keychain.handle


@pytest.fixture
def temp_keychain_path(tmp_path: Path, temp_keychain: int) -> Path:
    del temp_keychain
    return tmp_path / "keychain-cli-test.keychain-db"


@pytest.fixture
def real_store(temp_keychain: int) -> SecurityFrameworkStore:
    from keychain_cli.keychain.store import SecurityFrameworkStore

    return SecurityFrameworkStore(keychain=temp_keychain)


@dataclass
class Sandbox:
    """Isolated HOME, TMPDIR, and working directory for end-to-end runs."""

    root: Path
    home: Path
    tmp: Path
    work: Path
    env: dict[str, str]
    written_by_test: set[Path] = field(default_factory=set)

    def register(self, path: Path) -> Path:
        """Mark a file the test itself created so the leak sweep ignores it."""
        self.written_by_test.add(path.resolve())
        return path


@pytest.fixture
def sandbox(tmp_path: Path, temp_keychain_path: Path) -> Sandbox:
    home, tmp, work = tmp_path / "home", tmp_path / "tmp", tmp_path / "work"
    for directory in (home, tmp, work):
        directory.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "en_US.UTF-8",
        "KEYCHAIN_CLI_TEST_KEYCHAIN": str(temp_keychain_path),
    }
    return Sandbox(root=tmp_path, home=home, tmp=tmp, work=work, env=env)


CliEnv = Callable[..., tuple[int, str, str]]


@pytest.fixture
def cli_env(sandbox: Sandbox) -> CliEnv:
    """Run the CLI as a real subprocess inside the sandbox."""

    def _run(argv: Sequence[str], stdin: bytes | None = None) -> tuple[int, str, str]:
        completed = subprocess.run(  # noqa: S603 - argv list, no shell
            [sys.executable, "-m", "keychain_cli", *argv],
            input=stdin,
            capture_output=True,
            cwd=sandbox.work,
            env=sandbox.env,
            check=False,
            timeout=60,
        )
        return completed.returncode, completed.stdout.decode(), completed.stderr.decode()

    return _run


def assert_sandbox_clean(sandbox: Sandbox, leak: str) -> None:
    """No file was created by the tool, and the placeholder is in no file (FR-036, SC-009)."""
    for directory in (sandbox.home, sandbox.tmp, sandbox.work):
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            assert path.resolve() in sandbox.written_by_test, f"tool created a file: {path}"
            assert leak.encode() not in path.read_bytes(), f"secret written to {path}"
