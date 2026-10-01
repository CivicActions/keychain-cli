"""Implementation of `keychain-cli check` (US6, T062)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from keychain_cli.errors import EXIT_CHECK_MISSING
from keychain_cli.keychain import SecretStore
from keychain_cli.manifest import load_manifest
from keychain_cli.names import Namespace
from keychain_cli.output import emit_names


def run_check(
    args: argparse.Namespace,
    store: SecretStore,
    resolve_ns_fn: Callable[[str | None], Namespace],
) -> int:
    """Run `keychain-cli check`."""
    manifest = load_manifest(Path.cwd())
    ns: Namespace = resolve_ns_fn(args.namespace)

    missing = [v for v in manifest.variables if not store.exists(ns, v)]

    if missing:
        emit_names(missing, args.json)
        return EXIT_CHECK_MISSING

    if args.json:
        emit_names([], True)
    return 0
