"""Implementation of `keychain-cli init` (US6, T062)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from keychain_cli.commands.set_ import store_single_value
from keychain_cli.errors import InvalidInputError
from keychain_cli.keychain import SecretStore
from keychain_cli.manifest import load_manifest
from keychain_cli.names import Namespace
from keychain_cli.output import StoreReport, err, print_report
from keychain_cli.prompt import Prompter


def run_init(
    args: argparse.Namespace,
    store: SecretStore,
    prompts: Prompter,
    resolve_ns_fn: Callable[[str | None], Namespace],
) -> int:
    """Run `keychain-cli init`."""
    manifest = load_manifest(Path.cwd())
    ns: Namespace = resolve_ns_fn(args.namespace)

    missing = [v for v in manifest.variables if not store.exists(ns, v)]

    if not missing:
        err(f"namespace {ns.display} is complete")
        return 0

    if not prompts.is_interactive():
        raise InvalidInputError(
            f"cannot prompt for missing variables non-interactively: {', '.join(missing)}",
            "Run interactively to be prompted, or store values with `keychain-cli set`",
        )

    report = StoreReport()
    try:
        for var in missing:
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
                force=False,
                interactive=True,
            )
    except KeyboardInterrupt:
        print_report(report)
        raise

    print_report(report)
    return 0 if not report.skipped else 4
