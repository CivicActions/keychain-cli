"""CLI dispatcher: ``--`` split, usage errors, exit codes, platform guard."""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import sys

import pytest

from keychain_cli import __version__, cli
from keychain_cli.errors import UsageError
from tests.conftest import RunCli


@pytest.mark.parametrize(
    ("argv", "head", "tail"),
    [
        (
            ["run", "client-a", "--", "npm", "run", "dev"],
            ["run", "client-a"],
            ["npm", "run", "dev"],
        ),
        (["run", "--", "npm", "run", "dev"], ["run"], ["npm", "run", "dev"]),
        (["run", "client-a", "--", "env", "--", "x"], ["run", "client-a"], ["env", "--", "x"]),
        (["run", "client-a", "--"], ["run", "client-a"], []),
        (["list", "client-a"], ["list", "client-a"], None),
        ([], [], None),
    ],
)
def test_split_command_tail(argv: list[str], head: list[str], tail: list[str] | None) -> None:
    assert cli.split_command_tail(argv) == (head, tail)


@pytest.mark.parametrize(
    "argv",
    [["run", "client-a", "npm", "run", "dev"], ["run", "client-a"], ["run"]],
)
def test_run_without_separator_is_a_usage_error(run_cli: RunCli, argv: list[str]) -> None:
    code, out, err = run_cli(argv)
    assert code == 2
    assert out == ""
    assert "run [NAMESPACE] -- COMMAND" in err
    assert "unrecognized arguments" not in err


def test_run_with_separator_reaches_the_run_command(run_cli: RunCli) -> None:
    # Not implemented in this build, so the dispatcher's own exit 1 proves the parse worked.
    code, _out, err = run_cli(["run", "client-a", "--", "npm", "run", "dev"])
    assert code == 1
    assert "not implemented" in err


def test_run_with_omitted_namespace_does_not_treat_command_as_namespace(run_cli: RunCli) -> None:
    code, _out, err = run_cli(["run", "--", "npm", "run", "dev"])
    assert code == 1
    assert "not implemented" in err
    assert "npm" not in err


def test_unknown_command_is_exit_2(run_cli: RunCli) -> None:
    code, _out, err = run_cli(["frobnicate"])
    assert code == 2
    assert "invalid choice" in err


def test_no_command_is_exit_2(run_cli: RunCli) -> None:
    code, _out, _err = run_cli([])
    assert code == 2


def test_version(run_cli: RunCli) -> None:
    code, out, _err = run_cli(["--version"])
    assert code == 0
    assert out.strip() == f"keychain-cli {__version__}"


def test_help_lists_every_command(run_cli: RunCli) -> None:
    code, out, _err = run_cli(["--help"])
    assert code == 0
    for command in cli.COMMANDS:
        assert command in out


@pytest.mark.parametrize("command", [c for c in cli.COMMANDS if c != "run"])
def test_every_command_is_recognized_and_not_implemented(run_cli: RunCli, command: str) -> None:
    code, out, err = run_cli([command])
    assert code == 1
    assert out == ""
    assert f"the {command} command is not implemented" in err


def test_non_darwin_exits_6_before_any_keychain_import(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    for module in list(sys.modules):
        if module.startswith("keychain_cli.keychain.") and module != "keychain_cli.keychain":
            monkeypatch.delitem(sys.modules, module)
    monkeypatch.setattr(sys, "platform", "linux")
    code, out, err = run_cli(["list"])
    assert code == 6
    assert out == ""
    assert "macOS" in err
    assert "keychain_cli.keychain.store" not in sys.modules
    assert "keychain_cli.keychain._sec" not in sys.modules


def test_resolve_namespace_requires_explicit_name_for_now() -> None:
    assert cli.resolve_namespace("Client-A", allow_infer=True).key == "client-a"
    with pytest.raises(UsageError) as inferable:
        cli.resolve_namespace(None, allow_infer=True)
    assert "manifest" in inferable.value.next_step
    with pytest.raises(UsageError) as destructive:
        cli.resolve_namespace(None, allow_infer=False)
    assert "never infers" in destructive.value.next_step


def test_unexpected_exception_prints_no_traceback(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        msg = "internal"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "_dispatch", boom)
    code, out, err = run_cli(["list"])
    assert code == 1
    assert out == ""
    assert "Traceback" not in err
    assert "RuntimeError" in err
    assert "internal" not in err
