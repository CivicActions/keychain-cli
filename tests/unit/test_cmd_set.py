"""Unit tests for `keychain-cli set` (US1, T030)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import pytest

from keychain_cli.errors import EXIT_INTERRUPTED
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import FakePrompts, InMemoryStore


def test_set_three_variables_prompted_once_each(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    prompts.secrets = [
        SecretValue.from_text("val1"),
        SecretValue.from_text("val2"),
        SecretValue.from_text("val3"),
    ]
    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1", "VAR2", "VAR3"])

    assert code == 0
    assert stdout == ""
    assert "stored: VAR1, VAR2, VAR3" in stderr
    assert prompts.shown == [
        "Value for my-ns/VAR1:",
        "Value for my-ns/VAR2:",
        "Value for my-ns/VAR3:",
    ]
    ns = validate_namespace("my-ns")
    assert store.get(ns, "VAR1").data == b"val1"
    assert store.get(ns, "VAR2").data == b"val2"
    assert store.get(ns, "VAR3").data == b"val3"


def test_set_names_validated_before_any_prompt(run_cli: RunCli, prompts: FakePrompts) -> None:
    code, stdout, stderr = run_cli(["set", "my-ns", "VALID_ONE", "invalid-name"])

    assert code == 7
    assert stdout == ""
    assert "invalid variable name 'invalid-name'" in stderr
    assert prompts.shown == []


def test_set_duplicate_variable_in_invocation_rejected(
    run_cli: RunCli, prompts: FakePrompts
) -> None:
    code, stdout, stderr = run_cli(["set", "my-ns", "DUP", "DUP"])

    assert code == 7
    assert stdout == ""
    assert "duplicate variable" in stderr
    assert prompts.shown == []


def test_set_existing_interactive_declined_skips_and_exits_4(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("orig"))

    prompts.secrets = [SecretValue.from_text("new")]
    prompts.answers = [False]  # Decline overwrite

    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1"])

    assert code == 4
    assert stdout == ""
    assert "VAR1 already exists in my-ns. Overwrite?" in prompts.shown
    assert "skipped: VAR1" in stderr
    assert store.get(ns, "VAR1").data == b"orig"


def test_set_existing_interactive_confirmed_updates_and_exits_0(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("orig"))

    prompts.secrets = [SecretValue.from_text("new")]
    prompts.answers = [True]  # Confirm overwrite

    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1"])

    assert code == 0
    assert stdout == ""
    assert "VAR1 already exists in my-ns. Overwrite?" in prompts.shown
    assert "overwritten: VAR1" in stderr
    assert store.get(ns, "VAR1").data == b"new"


def test_set_force_updates_without_asking(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("orig"))

    prompts.secrets = [SecretValue.from_text("new")]

    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1", "--force"])

    assert code == 0
    assert stdout == ""
    assert not any("Overwrite?" in p for p in prompts.shown)
    assert "overwritten: VAR1" in stderr
    assert store.get(ns, "VAR1").data == b"new"


def test_set_existing_non_interactive_without_force_skips_and_exits_4(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("orig"))
    prompts.stdin_value = SecretValue.from_text("new")

    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1"], tty=False)

    assert code == 4
    assert stdout == ""
    assert "skipped: VAR1" in stderr
    assert store.get(ns, "VAR1").data == b"orig"


def test_set_empty_value_interactive_declined_skips(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    prompts.secrets = [SecretValue(b"")]
    prompts.answers = [False]  # Decline storing empty value

    code, stdout, stderr = run_cli(["set", "my-ns", "EMPTY_VAR"])

    assert code == 4
    assert "Store an empty value for EMPTY_VAR?" in prompts.shown
    assert "skipped: EMPTY_VAR" in stderr
    ns = validate_namespace("my-ns")
    assert not store.exists(ns, "EMPTY_VAR")


def test_set_empty_value_interactive_confirmed_stores(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    prompts.secrets = [SecretValue(b"")]
    prompts.answers = [True]  # Confirm storing empty value

    code, stdout, stderr = run_cli(["set", "my-ns", "EMPTY_VAR"])

    assert code == 0
    assert "Store an empty value for EMPTY_VAR?" in prompts.shown
    assert "stored: EMPTY_VAR" in stderr
    ns = validate_namespace("my-ns")
    assert store.get(ns, "EMPTY_VAR").data == b""


def test_set_stdin_mode_with_one_var_stores(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    prompts.stdin_value = SecretValue(b"stdin-secret")

    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1", "--stdin"])

    assert code == 0
    assert "stored: VAR1" in stderr
    assert prompts.stdin_reads == 1
    ns = validate_namespace("my-ns")
    assert store.get(ns, "VAR1").data == b"stdin-secret"


def test_set_stdin_mode_with_two_vars_exits_7_before_reading(
    run_cli: RunCli, prompts: FakePrompts
) -> None:
    code, stdout, stderr = run_cli(["set", "my-ns", "VAR1", "VAR2", "--stdin"])

    assert code == 7
    assert "standard input mode takes exactly one variable" in stderr
    assert prompts.stdin_reads == 0


def test_set_keyboard_interrupt_prints_partial_report(
    store: InMemoryStore, capsys: pytest.CaptureFixture[str]
) -> None:
    from keychain_cli import cli

    class InterruptPrompts(FakePrompts):
        def read_secret(self, prompt: str) -> SecretValue:
            if self.shown:
                raise KeyboardInterrupt
            return super().read_secret(prompt)

    prompts = InterruptPrompts()
    prompts.secrets = [SecretValue.from_text("first")]

    code = cli.main(
        ["set", "my-ns", "VAR1", "VAR2"],
        store_factory=lambda: store,
        prompts=prompts,
    )
    captured = capsys.readouterr()
    assert code == EXIT_INTERRUPTED
    assert "stored: VAR1" in captured.err
    ns = validate_namespace("my-ns")
    assert store.get(ns, "VAR1").data == b"first"
    assert not store.exists(ns, "VAR2")
