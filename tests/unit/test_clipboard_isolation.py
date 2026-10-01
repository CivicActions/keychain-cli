"""Isolation tests ensuring clipboard access is strictly confined to `copy` (US7, T069)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import ast
from pathlib import Path

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import FakePrompts, InMemoryStore, RecordingExec, RecordingSpawn


def test_static_clipboard_isolation() -> None:
    src_dir = Path(__file__).parents[2] / "src" / "keychain_cli"

    for py_file in src_dir.rglob("*.py"):
        rel = py_file.relative_to(src_dir).as_posix()
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

        # Check imports of clipboard
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "clipboard" not in alias.name or rel in {
                        "commands/copy.py",
                        "clipboard.py",
                    }, f"unauthorized import of clipboard in {rel}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and "clipboard" in node.module:
                    assert rel in {
                        "commands/copy.py",
                        "clipboard.py",
                    }, f"unauthorized import of clipboard in {rel}"

        # Check literal string 'pbcopy'
        content = py_file.read_text(encoding="utf-8")
        if "pbcopy" in content:
            assert rel in {
                "clipboard.py",
                "_clipclear.py",
            }, f"literal 'pbcopy' appears outside clipboard modules in {rel}"


def test_other_commands_never_spawn_pbcopy(
    run_cli: RunCli,
    store: InMemoryStore,
    spawn_fn: RecordingSpawn,
    prompts: FakePrompts,
    exec_fn: RecordingExec,
) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "VAR", SecretValue.from_text("secret-val"))

    # set
    prompts.secrets = [SecretValue.from_text("val2")]
    run_cli(["set", "client-a", "VAR2"])
    assert not any("pbcopy" in " ".join(call[0]) for call in spawn_fn.calls)

    # list
    run_cli(["list", "client-a"])
    assert not any("pbcopy" in " ".join(call[0]) for call in spawn_fn.calls)

    # run
    run_cli(["run", "client-a", "--", "echo", "test"])
    assert not any("pbcopy" in " ".join(call[0]) for call in spawn_fn.calls)

    # delete
    run_cli(["delete", "client-a", "VAR"])
    assert not any("pbcopy" in " ".join(call[0]) for call in spawn_fn.calls)
