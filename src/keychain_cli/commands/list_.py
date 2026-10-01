"""Implementation of `keychain-cli list` (US4, T051)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
from collections.abc import Callable

from keychain_cli.errors import NotFoundError, UsageError
from keychain_cli.keychain import NotFound, SecretStore
from keychain_cli.names import Namespace, validate_namespace
from keychain_cli.output import emit_names


def run_list(
    args: argparse.Namespace,
    store: SecretStore,
    resolve_ns_fn: Callable[[str | None], Namespace] | None = None,
) -> int:
    """Run `keychain-cli list`."""
    if getattr(args, "all", False):
        if args.namespace:
            raise UsageError(
                "--all does not accept a namespace argument",
                "Use `keychain-cli list --all` to list namespaces, or "
                "`keychain-cli list [NAMESPACE]` to list variables",
            )
        namespaces = store.list_namespaces()
        emit_names([ns.display for ns in namespaces], args.json)
        return 0

    target_ns: Namespace | None = None
    if args.namespace:
        target_ns = validate_namespace(args.namespace)
    elif resolve_ns_fn is not None:
        try:
            target_ns = resolve_ns_fn(None)
        except UsageError:
            target_ns = None

    if target_ns is not None:
        try:
            variables = store.list_variables(target_ns)
        except NotFound:
            raise NotFoundError(
                f"namespace '{target_ns.display}' not found",
                "Check the namespace name or run `keychain-cli list` to see existing namespaces",
            ) from None
        emit_names(variables, args.json)
        return 0

    namespaces = store.list_namespaces()
    emit_names([ns.display for ns in namespaces], args.json)
    return 0
