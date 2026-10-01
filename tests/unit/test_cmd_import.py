"""Unit tests for `keychain-cli import` (US3, T042)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from keychain_cli.errors import EXIT_INTERRUPTED
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import FakePrompts, InMemoryStore


def test_import_stores_all_valid_entries(
    run_cli: RunCli, store: InMemoryStore, tmp_path: Path
) -> None:
    env_file = tmp_path / "valid.env"
    env_file.write_text("VAR1=val1\nVAR2=val2\n")

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file)])
    assert code == 0
    assert stdout == ""
    assert "stored: VAR1, VAR2" in stderr
    ns = validate_namespace("test-ns")
    assert store.get(ns, "VAR1").data == b"val1"
    assert store.get(ns, "VAR2").data == b"val2"


def test_import_warnings_and_duplicates_and_preserves_file(
    run_cli: RunCli, store: InMemoryStore, tmp_path: Path
) -> None:
    content = 'ALPHA=one\nBETA=first\nbad line here\nUNTERM="unterminated\nBETA=second\n'
    env_file = tmp_path / "mix.env"
    env_file.write_text(content)
    orig_bytes = env_file.read_bytes()
    orig_mtime = env_file.stat().st_mtime

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file)])
    assert code == 0
    assert "warning: line 3: malformed entry" in stderr
    assert "warning: line 4 (UNTERM): malformed entry" in stderr
    assert "duplicate key BETA (lines 2, 5): last value used" in stderr
    assert "stored: ALPHA, BETA" in stderr
    assert "malformed: 2 line(s): line 3, line 4 (UNTERM)" in stderr

    # Source file unchanged
    assert env_file.read_bytes() == orig_bytes
    assert env_file.stat().st_mtime == orig_mtime


def test_import_existing_confirmed_once_updates_all(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts, tmp_path: Path
) -> None:
    ns = validate_namespace("test-ns")
    store.add(ns, "A", SecretValue.from_text("old_a"))
    store.add(ns, "B", SecretValue.from_text("old_b"))

    env_file = tmp_path / "exist.env"
    env_file.write_text("A=new_a\nB=new_b\nC=new_c\n")

    prompts.answers = [True]  # Confirm overwrite all

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file)])
    assert code == 0
    assert any("2 variables already exist: A, B. Overwrite all?" in p for p in prompts.shown)
    assert "stored: C" in stderr
    assert "overwritten: A, B" in stderr
    assert store.get(ns, "A").data == b"new_a"
    assert store.get(ns, "B").data == b"new_b"
    assert store.get(ns, "C").data == b"new_c"


def test_import_existing_declined_skips_all_and_exits_4(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts, tmp_path: Path
) -> None:
    ns = validate_namespace("test-ns")
    store.add(ns, "A", SecretValue.from_text("old_a"))

    env_file = tmp_path / "exist.env"
    env_file.write_text("A=new_a\nB=new_b\n")

    prompts.answers = [False]  # Decline overwrite

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file)])
    assert code == 4
    assert "skipped: A" in stderr
    assert "stored: B" in stderr
    assert store.get(ns, "A").data == b"old_a"
    assert store.get(ns, "B").data == b"new_b"


def test_import_force_overwrites_without_asking(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts, tmp_path: Path
) -> None:
    ns = validate_namespace("test-ns")
    store.add(ns, "A", SecretValue.from_text("old_a"))

    env_file = tmp_path / "exist.env"
    env_file.write_text("A=new_a\n")

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file), "--force"])
    assert code == 0
    assert prompts.shown == []
    assert "overwritten: A" in stderr
    assert store.get(ns, "A").data == b"new_a"


def test_import_non_interactive_without_force_skips_and_exits_4(
    run_cli: RunCli, store: InMemoryStore, tmp_path: Path
) -> None:
    ns = validate_namespace("test-ns")
    store.add(ns, "A", SecretValue.from_text("old_a"))

    env_file = tmp_path / "exist.env"
    env_file.write_text("A=new_a\n")

    code, stdout, stderr = run_cli(["import", "test-ns", str(env_file)], tty=False)
    assert code == 4
    assert "skipped: A" in stderr
    assert store.get(ns, "A").data == b"old_a"


def test_import_missing_file_exits_3(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["import", "test-ns", "no-such-file.env"])
    assert code == 3
    assert "not found" in stderr


def test_import_directory_exits_7(run_cli: RunCli, tmp_path: Path) -> None:
    code, stdout, stderr = run_cli(["import", "test-ns", str(tmp_path)])
    assert code == 7
    assert "not a regular file" in stderr


def test_import_unreadable_file_exits_7(run_cli: RunCli, tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable.env"
    unreadable.write_text("A=1\n")
    unreadable.chmod(0o000)

    try:
        code, stdout, stderr = run_cli(["import", "test-ns", str(unreadable)])
        assert code == 7
        assert "cannot read" in stderr
    finally:
        unreadable.chmod(0o644)


def test_import_all_lines_malformed_exits_7(run_cli: RunCli, tmp_path: Path) -> None:
    bad_file = tmp_path / "all_bad.env"
    bad_file.write_text("bad1\nbad2\n")

    code, stdout, stderr = run_cli(["import", "test-ns", str(bad_file)])
    assert code == 7
    assert "every line was malformed" in stderr


def test_import_keyboard_interrupt_prints_partial_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from keychain_cli import cli

    env_file = tmp_path / "interrupt.env"
    env_file.write_text("VAR1=val1\nVAR2=val2\n")

    class InterruptStore(InMemoryStore):
        def add(self, namespace: Any, name: str, value: SecretValue) -> None:
            if name == "VAR2":
                raise KeyboardInterrupt
            super().add(namespace, name, value)

    inst = InterruptStore()
    code = cli.main(
        ["import", "test-ns", str(env_file)],
        store_factory=lambda: inst,
    )
    captured = capsys.readouterr()
    assert code == EXIT_INTERRUPTED
    assert "stored: VAR1" in captured.err
    ns = validate_namespace("test-ns")
    assert inst.get(ns, "VAR1").data == b"val1"
