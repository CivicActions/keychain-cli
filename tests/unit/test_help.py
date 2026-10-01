"""Help text audit and parser inspection for FR-004 compliance (T077)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse

import pytest

from keychain_cli.cli import COMMANDS, build_parser
from tests.conftest import RunCli


def test_toplevel_help_lists_all_commands(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["--help"])
    assert code == 0
    assert stderr == ""
    for cmd in COMMANDS:
        assert cmd in stdout


@pytest.mark.parametrize("cmd", COMMANDS)
def test_subcommand_help_includes_examples_and_exit_codes(run_cli: RunCli, cmd: str) -> None:
    code, stdout, stderr = run_cli([cmd, "--help"])
    assert code == 0
    assert stderr == ""
    assert "Example" in stdout
    assert "Exit code" in stdout

    if cmd == "copy":
        assert "prefer `run`" in stdout
        assert "clipboard is readable by every application" in stdout


def test_fr004_parser_no_secrets_in_args() -> None:
    """FR-004: Parser MUST NOT accept secrets in arguments or options."""
    parser = build_parser()

    # Find subparsers action
    subparser_action = None
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            subparser_action = action
            break
    assert subparser_action is not None

    forbidden_keywords = {"value", "secret", "password", "token"}

    for name, sub in subparser_action.choices.items():
        for action in sub._actions:  # noqa: SLF001
            # Check options
            for opt in action.option_strings:
                opt_lower = opt.lower()
                for kw in forbidden_keywords:
                    assert kw not in opt_lower, f"option {opt} in command {name} contains {kw}"

            # Check positionals (actions with no option_strings)
            if not action.option_strings and action.dest != "help":
                dest_lower = action.dest.lower()
                # Allowed positionals: namespace, variables, variable, file, command tail
                allowed_dests = {"namespace", "variables", "variable", "file", "command"}
                assert dest_lower in allowed_dests or "command" in dest_lower, (
                    f"unexpected positional {action.dest} in command {name}"
                )
