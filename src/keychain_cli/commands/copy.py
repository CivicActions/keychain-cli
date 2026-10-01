"""Implementation of `keychain-cli copy` (US7, T073)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable
from typing import Any

from keychain_cli.clipboard import (
    MAX_CLEAR_AFTER,
    MIN_CLEAR_AFTER,
    copy_to_clipboard,
    schedule_clear,
)
from keychain_cli.errors import NotFoundError, UsageError
from keychain_cli.keychain import NotFound, SecretStore
from keychain_cli.names import validate_namespace, validate_variable
from keychain_cli.output import err

SpawnFn = Callable[..., Any]


def run_copy(args: argparse.Namespace, store: SecretStore, spawn_fn: SpawnFn) -> int:
    """Run `keychain-cli copy`."""
    clear_after = args.clear_after
    if clear_after < MIN_CLEAR_AFTER or clear_after > MAX_CLEAR_AFTER:
        raise UsageError(
            f"--clear-after must be between {MIN_CLEAR_AFTER} and {MAX_CLEAR_AFTER} seconds, "
            f"not {clear_after}",
            f"Specify an integer between {MIN_CLEAR_AFTER} and {MAX_CLEAR_AFTER}",
        )

    ns = validate_namespace(args.namespace)
    var = validate_variable(args.variable)

    try:
        secret = store.get(ns, var)
    except NotFound:
        raise NotFoundError(
            f"variable '{var}' not found in namespace '{ns.display}'",
            f"Run `keychain-cli list {ns.display}` to see existing variables",
        ) from None

    copy_to_clipboard(secret, spawn_fn=spawn_fn)
    digest = hashlib.sha256(secret.data).hexdigest()
    schedule_clear(digest, clear_after, spawn_fn=spawn_fn)

    err(f"copied {ns.display}/{var} to clipboard; it will be cleared in {clear_after} seconds.")
    err("warning: clipboard managers, history tools, and clipboard sync may keep a copy.")

    return 0
