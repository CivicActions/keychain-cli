"""Unit tests for `keychain-cli delete` (US5, T053)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import FakePrompts, InMemoryStore


def test_delete_single_variable_removes_only_it_no_confirmation(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))
    store.add(ns, "VAR2", SecretValue.from_text("v2"))

    code, stdout, stderr = run_cli(["delete", "my-ns", "VAR1"])
    assert code == 0
    assert stdout == ""
    assert prompts.shown == []
    assert not store.exists(ns, "VAR1")
    assert store.exists(ns, "VAR2")


def test_delete_namespace_interactive_confirmed(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("My-Ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))
    store.add(ns, "VAR2", SecretValue.from_text("v2"))

    prompts.answers = [True]  # confirm exact match

    code, stdout, stderr = run_cli(["delete", "My-Ns"])
    assert code == 0
    assert any("Delete namespace My-Ns and its 2 variables?" in p for p in prompts.shown)
    assert not store.exists(ns, "VAR1")
    assert not store.exists(ns, "VAR2")
    assert store.list_namespaces() == []


def test_delete_namespace_interactive_wrong_confirmation_exits_4(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("My-Ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))

    prompts.answers = [False]  # declined / wrong name

    code, stdout, stderr = run_cli(["delete", "My-Ns"])
    assert code == 4
    assert "canceled" in stderr
    assert store.exists(ns, "VAR1")


def test_delete_namespace_non_interactive_without_force_exits_4(
    run_cli: RunCli, store: InMemoryStore
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))

    code, stdout, stderr = run_cli(["delete", "my-ns"], tty=False)
    assert code == 4
    assert "--force" in stderr
    assert store.exists(ns, "VAR1")


def test_delete_namespace_force_deletes_without_asking(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))

    code, stdout, stderr = run_cli(["delete", "my-ns", "--force"], tty=False)
    assert code == 0
    assert prompts.shown == []
    assert not store.exists(ns, "VAR1")


def test_delete_missing_variable_exits_3(run_cli: RunCli, store: InMemoryStore) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "VAR1", SecretValue.from_text("v1"))

    code, stdout, stderr = run_cli(["delete", "my-ns", "MISSING"])
    assert code == 3
    assert "not found" in stderr


def test_delete_missing_namespace_exits_3(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["delete", "missing-ns"])
    assert code == 3
    assert "not found" in stderr


def test_delete_last_variable_removes_namespace_from_list(
    run_cli: RunCli, store: InMemoryStore
) -> None:
    ns = validate_namespace("my-ns")
    store.add(ns, "ONLY_VAR", SecretValue.from_text("v1"))

    code, stdout, stderr = run_cli(["delete", "my-ns", "ONLY_VAR"])
    assert code == 0
    assert store.list_namespaces() == []


def test_delete_requires_namespace_positional_exits_2(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["delete"])
    assert code == 2
