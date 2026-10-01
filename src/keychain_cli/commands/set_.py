"""Implementation of `keychain-cli set` (US1, T033)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse

from keychain_cli.errors import InvalidInputError
from keychain_cli.keychain import AlreadyExists, SecretStore
from keychain_cli.names import Namespace, validate_namespace, validate_variable
from keychain_cli.output import StoreReport, print_report
from keychain_cli.prompt import Prompter
from keychain_cli.secret import SecretValue


def store_single_value(
    ns: Namespace,
    var: str,
    value: SecretValue,
    store: SecretStore,
    prompts: Prompter,
    report: StoreReport,
    *,
    force: bool,
    interactive: bool,
) -> None:
    """Store or update a single variable, updating the report."""
    try:
        store.add(ns, var, value)
        report.stored.append(var)
    except AlreadyExists:
        if (
            force
            or interactive
            and prompts.confirm(f"{var} already exists in {ns.display}. Overwrite?", default=False)
        ):
            store.update(ns, var, value)
            report.overwritten.append(var)
        else:
            report.skipped.append(var)


def run_set(args: argparse.Namespace, store: SecretStore, prompts: Prompter) -> int:
    """Run `keychain-cli set`."""
    ns = validate_namespace(args.namespace)

    variables: list[str] = list(args.variables)
    seen: set[str] = set()
    for var in variables:
        validate_variable(var)
        if var in seen:
            raise InvalidInputError(
                f"duplicate variable '{var}' in invocation",
                "Name each variable once per invocation",
            )
        seen.add(var)

    report = StoreReport()
    is_interactive = prompts.is_interactive()
    use_stdin = bool(args.stdin or not is_interactive)

    if use_stdin:
        if len(variables) != 1:
            raise InvalidInputError(
                "standard input mode takes exactly one variable",
                "Name exactly one variable when piping input or using --stdin",
            )
        var = variables[0]
        value = prompts.read_secret_from_stdin()
        store_single_value(
            ns,
            var,
            value,
            store,
            prompts,
            report,
            force=bool(args.force),
            interactive=is_interactive,
        )
        print_report(report)
        return 0 if not report.skipped else 4

    # Interactive mode
    try:
        for var in variables:
            value = prompts.read_secret(f"Value for {ns.display}/{var}:")
            if not value.data and not prompts.confirm(
                f"Store an empty value for {var}?", default=False
            ):
                report.skipped.append(var)
                continue
            store_single_value(
                ns,
                var,
                value,
                store,
                prompts,
                report,
                force=bool(args.force),
                interactive=True,
            )
    except KeyboardInterrupt:
        print_report(report)
        raise

    print_report(report)
    return 0 if not report.skipped else 4
