"""Unit tests for `keychain-cli init` and `check` (US6, T058)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import json
from pathlib import Path

import pytest

from keychain_cli.errors import EXIT_CHECK_MISSING, EXIT_INTERRUPTED
from keychain_cli.manifest import MANIFEST_NAME
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import FakePrompts, InMemoryStore


def test_init_prompts_only_for_missing_variables_in_order(
    run_cli: RunCli,
    store: InMemoryStore,
    prompts: FakePrompts,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "init-ns"\nvariables = ["A", "B", "C"]\n')
    ns = validate_namespace("init-ns")
    store.add(ns, "B", SecretValue.from_text("existing_b"))

    prompts.secrets = [SecretValue.from_text("new_a"), SecretValue.from_text("new_c")]

    code, stdout, stderr = run_cli(["init"])
    assert code == 0
    assert "stored: A, C" in stderr
    assert prompts.shown == ["Value for init-ns/A:", "Value for init-ns/C:"]
    assert store.get(ns, "A").data == b"new_a"
    assert store.get(ns, "B").data == b"existing_b"
    assert store.get(ns, "C").data == b"new_c"


def test_init_all_present_reports_complete(
    run_cli: RunCli,
    store: InMemoryStore,
    prompts: FakePrompts,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "init-ns"\nvariables = ["A"]\n')
    ns = validate_namespace("init-ns")
    store.add(ns, "A", SecretValue.from_text("existing_a"))

    code, stdout, stderr = run_cli(["init"])
    assert code == 0
    assert "namespace init-ns is complete" in stderr
    assert prompts.shown == []


def test_init_non_interactive_with_missing_exits_7(
    run_cli: RunCli, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "init-ns"\nvariables = ["A", "B"]\n')

    code, stdout, stderr = run_cli(["init"], tty=False)
    assert code == 7
    assert "cannot prompt for missing variables non-interactively: A, B" in stderr


def test_init_malformed_manifest_exits_7(
    run_cli: RunCli, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text("invalid toml ===\n")

    code, stdout, stderr = run_cli(["init"])
    assert code == 7
    assert "TOML parse error" in stderr


def test_init_keyboard_interrupt_prints_partial_report(
    store: InMemoryStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "init-ns"\nvariables = ["A", "B"]\n')

    class InterruptPrompts(FakePrompts):
        def read_secret(self, prompt: str) -> SecretValue:
            if self.shown:
                raise KeyboardInterrupt
            return super().read_secret(prompt)

    prompts = InterruptPrompts()
    prompts.secrets = [SecretValue.from_text("val_a")]

    from keychain_cli import cli

    code = cli.main(
        ["init"],
        store_factory=lambda: store,
        prompts=prompts,
    )
    captured = capsys.readouterr()
    assert code == EXIT_INTERRUPTED
    assert "stored: A" in captured.err
    ns = validate_namespace("init-ns")
    assert store.get(ns, "A").data == b"val_a"
    assert not store.exists(ns, "B")


def test_check_reports_missing_variables_and_exits_10(
    run_cli: RunCli, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "check-ns"\nvariables = ["A", "B", "C"]\n')
    ns = validate_namespace("check-ns")
    store.add(ns, "B", SecretValue.from_text("b"))

    code, stdout, stderr = run_cli(["check"])
    assert code == EXIT_CHECK_MISSING
    assert stdout == "A\nC\n"

    # With --json
    code, stdout, stderr = run_cli(["check", "--json"])
    assert code == EXIT_CHECK_MISSING
    assert json.loads(stdout) == ["A", "C"]


def test_check_all_present_exits_0(
    run_cli: RunCli, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "check-ns"\nvariables = ["A"]\n')
    ns = validate_namespace("check-ns")
    store.add(ns, "A", SecretValue.from_text("a"))

    code, stdout, stderr = run_cli(["check"])
    assert code == 0
    assert stdout == ""

    code, stdout, stderr = run_cli(["check", "--json"])
    assert code == 0
    assert json.loads(stdout) == []


def test_init_and_check_missing_manifest_exits_3(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run_cli(["init"])
    assert code == 3
    assert "not found" in stderr

    code, stdout, stderr = run_cli(["check"])
    assert code == 3
    assert "not found" in stderr
