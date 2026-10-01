"""Implementation of `keychain-cli import` (US3, T046)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
from pathlib import Path

from keychain_cli.envfile import parse_env_file
from keychain_cli.errors import InvalidInputError
from keychain_cli.keychain import SecretStore
from keychain_cli.names import validate_namespace
from keychain_cli.output import StoreReport, err, print_report
from keychain_cli.prompt import Prompter


def run_import(args: argparse.Namespace, store: SecretStore, prompts: Prompter) -> int:
    """Run `keychain-cli import`."""
    ns = validate_namespace(args.namespace)
    file_path = Path(args.file)

    parsed = parse_env_file(file_path)

    if not parsed.entries and parsed.malformed:
        raise InvalidInputError(
            "every line was malformed",
            "Provide a file with at least one valid KEY=value entry",
        )

    for m in parsed.malformed:
        if m.name is None:
            err(f"warning: line {m.line}: malformed entry")
        else:
            err(f"warning: line {m.line} ({m.name}): malformed entry")

    report = StoreReport(
        malformed=parsed.malformed,
        duplicates=parsed.duplicates,
    )

    existing = [e for e in parsed.entries if store.exists(ns, e.name)]
    new_entries = [e for e in parsed.entries if not store.exists(ns, e.name)]

    overwrite = False
    if existing:
        if args.force:
            overwrite = True
        elif prompts.is_interactive():
            names_str = ", ".join(e.name for e in existing)
            msg = f"{len(existing)} variables already exist: {names_str}. Overwrite all?"
            overwrite = prompts.confirm(msg, default=False)
        else:
            overwrite = False

    try:
        for entry in new_entries:
            store.add(ns, entry.name, entry.value)
            report.stored.append(entry.name)

        if overwrite:
            for entry in existing:
                store.update(ns, entry.name, entry.value)
                report.overwritten.append(entry.name)
        else:
            for entry in existing:
                report.skipped.append(entry.name)
    except KeyboardInterrupt:
        print_report(report)
        raise

    print_report(report)
    return 0 if not report.skipped else 4
