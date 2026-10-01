"""Implementation of `keychain-cli run` (US2, T038)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from keychain_cli.errors import CommandNotFoundError, NotFoundError, UsageError
from keychain_cli.keychain import NotFound, SecretStore
from keychain_cli.names import Namespace

ExecFn = Callable[[str, Sequence[str], Mapping[str, str]], Any]


def run_run(
    args: argparse.Namespace,
    command_tail: list[str],
    store: SecretStore,
    exec_fn: ExecFn,
    resolve_ns_fn: Callable[[str | None], Namespace],
) -> int:
    """Run `keychain-cli run`."""
    if not command_tail:
        raise UsageError(
            "no command specified after `--`",
            "Use: keychain-cli run [NAMESPACE] -- COMMAND [ARG ...]",
        )

    ns = resolve_ns_fn(args.namespace)
    try:
        values = store.get_all(ns)
    except NotFound:
        raise NotFoundError(
            f"namespace '{ns.display}' not found",
            "Run 'keychain-cli init' to configure this project, "
            "or 'keychain-cli set' to store variables",
        ) from None

    env = {**os.environ, **{name: v.data.decode("utf-8") for name, v in values.items()}}

    try:
        exec_fn(command_tail[0], command_tail, env)
    except (FileNotFoundError, PermissionError) as err:
        raise CommandNotFoundError(
            f"cannot execute '{command_tail[0]}': {err.strerror}",
            "Check that the command exists, is on PATH, and is executable",
        ) from None

    return 0
