"""Leak tests asserting placeholder secrets never surface in outputs or exceptions."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from pathlib import Path
from typing import Any

from keychain_cli.keychain import StoreError
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import LEAK, RunCli, assert_no_leak
from tests.fakes import FakePrompts, InMemoryStore, RecordingExec


def test_set_no_leak_on_success(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    prompts.secrets = [SecretValue.from_text(LEAK)]
    code, stdout, stderr = run_cli(["set", "leak-ns", "LEAK_VAR"])
    assert code == 0
    assert_no_leak(stdout, stderr)


def test_set_no_leak_on_declined_overwrite(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    ns = validate_namespace("leak-ns")
    store.add(ns, "LEAK_VAR", SecretValue.from_text(LEAK))

    prompts.secrets = [SecretValue.from_text(LEAK + "-new")]
    prompts.answers = [False]

    code, stdout, stderr = run_cli(["set", "leak-ns", "LEAK_VAR"])
    assert code == 4
    assert_no_leak(stdout, stderr)


def test_set_no_leak_on_store_error(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts
) -> None:
    class FailingStore(InMemoryStore):
        def add(self, namespace: Any, name: str, value: SecretValue) -> None:
            raise StoreError(-25299, "Simulated Keychain failure")

    failing_store = FailingStore()
    prompts.secrets = [SecretValue.from_text(LEAK)]

    from keychain_cli import cli

    code = cli.main(
        ["set", "leak-ns", "LEAK_VAR"],
        store_factory=lambda: failing_store,
        prompts=prompts,
    )
    assert code == 5


def test_run_no_leak_on_failure_and_only_in_env(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    ns = validate_namespace("leak-ns")
    store.add(ns, "LEAK_VAR", SecretValue.from_text(LEAK))

    # Missing namespace
    code, stdout, stderr = run_cli(["run", "other-ns", "--", "echo", "hi"])
    assert code == 3
    assert_no_leak(stdout, stderr)

    # Command not found
    exec_fn.raises = FileNotFoundError(2, "No such file")
    code, stdout, stderr = run_cli(["run", "leak-ns", "--", "nonexistent"])
    assert code == 8
    assert_no_leak(stdout, stderr)

    # Successful exec: value in env, never in argv
    exec_fn.raises = None
    code, stdout, stderr = run_cli(["run", "leak-ns", "--", "cmd", "arg1"])
    assert code == 0
    assert_no_leak(stdout, stderr)
    assert len(exec_fn.calls) == 2
    prog, argv, env = exec_fn.calls[-1]
    assert_no_leak(prog, argv)
    assert env["LEAK_VAR"] == LEAK


def test_import_no_leak(
    run_cli: RunCli, store: InMemoryStore, prompts: FakePrompts, tmp_path: Path
) -> None:
    env_file = tmp_path / "leak.env"
    env_file.write_text(f"VALID={LEAK}\n{LEAK}\n")

    # Success
    code, stdout, stderr = run_cli(["import", "leak-ns", str(env_file)])
    assert code == 0
    assert_no_leak(stdout, stderr)

    # Decline overwrite
    prompts.answers = [False]
    code, stdout, stderr = run_cli(["import", "leak-ns", str(env_file)])
    assert code == 4
    assert_no_leak(stdout, stderr)

    # Store error
    class FailingStore(InMemoryStore):
        def update(self, namespace: Any, name: str, value: SecretValue) -> None:
            raise StoreError(-25299, "Simulated store error")

    failing_store = FailingStore()
    ns = validate_namespace("leak-ns")
    failing_store.add(ns, "VALID", SecretValue.from_text("old"))

    from keychain_cli import cli

    prompts.answers = [True]
    code = cli.main(
        ["import", "leak-ns", str(env_file)],
        store_factory=lambda: failing_store,
        prompts=prompts,
    )
    assert code == 5
