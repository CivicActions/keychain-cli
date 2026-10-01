"""Unit tests for `keychain-cli run` (US2, T035)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from keychain_cli.keychain import StoreError
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import InMemoryStore, RecordingExec


def test_run_executes_command_with_overlaid_environment(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "API_TOKEN", SecretValue.from_text("secret-token"))
    store.add(ns, "EXISTING_VAR", SecretValue.from_text("new-val"))

    code, stdout, stderr = run_cli(["run", "client-a", "--", "echo", "hello", "--", "flag"])

    assert code == 0
    assert stdout == ""
    assert stderr == ""
    assert len(exec_fn.calls) == 1
    prog, argv, env = exec_fn.calls[0]
    assert prog == "echo"
    assert argv == ["echo", "hello", "--", "flag"]
    assert "sh" not in argv[0] and "bash" not in argv[0] and "zsh" not in argv[0]
    assert env["API_TOKEN"] == "secret-token"
    assert env["EXISTING_VAR"] == "new-val"


def test_run_missing_namespace_exits_3_and_does_not_exec(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    code, stdout, stderr = run_cli(["run", "missing-ns", "--", "echo", "hi"])

    assert code == 3
    assert stdout == ""
    assert "missing-ns" in stderr
    assert len(exec_fn.calls) == 0


def test_run_store_error_exits_5_and_does_not_exec(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    class FailingStore(InMemoryStore):
        def get_all(self, namespace: object) -> dict[str, SecretValue]:
            raise StoreError(-25293, "Keychain authorization failed")

    failing_store = FailingStore()
    from keychain_cli import cli

    code = cli.main(
        ["run", "ns", "--", "echo", "hi"],
        store_factory=lambda: failing_store,
        exec_fn=exec_fn,
    )
    assert code == 5
    assert len(exec_fn.calls) == 0


def test_run_command_not_found_exits_8(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "VAR", SecretValue.from_text("val"))
    exec_fn.raises = FileNotFoundError(2, "No such file or directory")

    code, stdout, stderr = run_cli(["run", "client-a", "--", "nonexistent-cmd"])

    assert code == 8
    assert "cannot execute 'nonexistent-cmd'" in stderr


def test_run_command_permission_denied_exits_8(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "VAR", SecretValue.from_text("val"))
    exec_fn.raises = PermissionError(13, "Permission denied")

    code, stdout, stderr = run_cli(["run", "client-a", "--", "unexecutable-cmd"])

    assert code == 8
    assert "cannot execute 'unexecutable-cmd'" in stderr


def test_run_without_separator_exits_2(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["run", "client-a", "echo", "hello"])

    assert code == 2
    assert "`--`" in stderr


def test_run_empty_command_tail_exits_2(
    run_cli: RunCli, store: InMemoryStore, exec_fn: RecordingExec
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "VAR", SecretValue.from_text("val"))

    code, stdout, stderr = run_cli(["run", "client-a", "--"])

    assert code == 2
    assert "no command specified" in stderr
    assert len(exec_fn.calls) == 0
