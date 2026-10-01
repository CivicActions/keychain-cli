"""Implementation of `keychain-cli delete` (US5, T055)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse

from keychain_cli.errors import NotFoundError, RefusedError
from keychain_cli.keychain import NotFound, SecretStore
from keychain_cli.names import validate_namespace, validate_variable
from keychain_cli.prompt import Prompter


def run_delete(args: argparse.Namespace, store: SecretStore, prompts: Prompter) -> int:
    """Run `keychain-cli delete`."""
    ns = validate_namespace(args.namespace)

    if args.variable:
        var = validate_variable(args.variable)
        try:
            store.delete_variable(ns, var)
        except NotFound:
            raise NotFoundError(
                f"variable '{var}' not found in namespace '{ns.display}'",
                f"Run `keychain-cli list {ns.display}` to see existing variables",
            ) from None
        return 0

    try:
        variables = store.list_variables(ns)
    except NotFound:
        raise NotFoundError(
            f"namespace '{ns.display}' not found",
            "Run `keychain-cli list` to see existing namespaces",
        ) from None

    count = len(variables)
    if not args.force:
        if not prompts.is_interactive():
            raise RefusedError(
                f"refusing to delete namespace '{ns.display}' non-interactively without --force",
                "Pass --force to confirm deletion in automated scripts",
            )
        msg = (
            f"Delete namespace {ns.display} and its {count} variables? "
            "Type the namespace name to confirm:"
        )
        if not prompts.confirm_exact(msg, ns):
            raise RefusedError(
                f"deletion of namespace '{ns.display}' canceled",
                "Type the exact namespace name to confirm deletion",
            )

    store.delete_namespace(ns)
    return 0
