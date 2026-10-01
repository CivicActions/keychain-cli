"""Unit tests for `keychain-cli copy` (US7, T068)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import pytest

from keychain_cli.keychain import StoreError
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import InMemoryStore, RecordingSpawn


def test_copy_success_prints_two_line_confirmation(
    run_cli: RunCli, store: InMemoryStore, spawn_fn: RecordingSpawn
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "API_TOKEN", SecretValue.from_text("token-val"))

    code, stdout, stderr = run_cli(["copy", "client-a", "API_TOKEN"])
    assert code == 0
    assert stdout == ""
    assert "copied client-a/API_TOKEN to clipboard; it will be cleared in 45 seconds." in stderr
    assert (
        "warning: clipboard managers, history tools, and clipboard sync may keep a copy." in stderr
    )
    assert len(spawn_fn.calls) == 2


def test_copy_custom_clear_after_passed_to_helper(
    run_cli: RunCli, store: InMemoryStore, spawn_fn: RecordingSpawn
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "API_TOKEN", SecretValue.from_text("token-val"))

    code, stdout, stderr = run_cli(["copy", "client-a", "API_TOKEN", "--clear-after", "5"])
    assert code == 0
    assert "cleared in 5 seconds" in stderr
    assert b"\n5\n" in spawn_fn.stdin_writes[1]


def test_copy_max_clear_after_accepted(
    run_cli: RunCli, store: InMemoryStore, spawn_fn: RecordingSpawn
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "API_TOKEN", SecretValue.from_text("token-val"))

    code, stdout, stderr = run_cli(["copy", "client-a", "API_TOKEN", "--clear-after", "300"])
    assert code == 0
    assert "cleared in 300 seconds" in stderr


@pytest.mark.parametrize("invalid_val", ["0", "-1", "301", "abc"])
def test_copy_invalid_clear_after_exits_2(
    run_cli: RunCli, store: InMemoryStore, spawn_fn: RecordingSpawn, invalid_val: str
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "API_TOKEN", SecretValue.from_text("token-val"))

    code, stdout, stderr = run_cli(["copy", "client-a", "API_TOKEN", "--clear-after", invalid_val])
    assert code == 2
    assert len(spawn_fn.calls) == 0


def test_copy_missing_variable_exits_3_no_spawn(
    run_cli: RunCli, store: InMemoryStore, spawn_fn: RecordingSpawn
) -> None:
    code, stdout, stderr = run_cli(["copy", "client-a", "MISSING_VAR"])
    assert code == 3
    assert len(spawn_fn.calls) == 0


def test_copy_store_error_exits_5_no_spawn(spawn_fn: RecordingSpawn) -> None:
    class FailingStore(InMemoryStore):
        def get(self, namespace: object, name: str) -> SecretValue:
            raise StoreError(-25293, "Keychain locked")

    from keychain_cli import cli

    code = cli.main(
        ["copy", "client-a", "VAR"],
        store_factory=lambda: FailingStore(),
        spawn_fn=spawn_fn,
    )
    assert code == 5
    assert len(spawn_fn.calls) == 0


def test_copy_invalid_args_count_exits_2(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["copy", "client-a"])
    assert code == 2

    code, stdout, stderr = run_cli(["copy", "client-a", "V1", "V2"])
    assert code == 2
