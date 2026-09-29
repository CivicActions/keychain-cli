"""Entry point: platform guard, ``--`` split, argument parsing, dispatch, exit codes.

Commands are registered here but, in this build, every one reports "not implemented" with
exit 1. The storage layer beneath them is complete and tested.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from keychain_cli import __version__
from keychain_cli.errors import (
    EXIT_INTERRUPTED,
    KeychainCliError,
    UsageError,
    format_error,
)
from keychain_cli.keychain import SecretStore
from keychain_cli.names import Namespace, validate_namespace
from keychain_cli.output import err
from keychain_cli.platform_check import ensure_supported
from keychain_cli.prompt import Prompter, TtyPrompter

TEST_KEYCHAIN_ENV = "KEYCHAIN_CLI_TEST_KEYCHAIN"

ExecFn = Callable[[str, Sequence[str], Mapping[str, str]], Any]
SpawnFn = Callable[..., Any]
StoreFactory = Callable[[], SecretStore]

COMMANDS = ("set", "list", "run", "import", "delete", "init", "check", "copy")


@dataclass(frozen=True)
class Services:
    """Side-effect seams injected into commands (constitution VI)."""

    store_factory: StoreFactory
    prompts: Prompter
    exec_fn: ExecFn
    spawn_fn: SpawnFn


def split_command_tail(argv: Sequence[str]) -> tuple[list[str], list[str] | None]:
    """Split at the first literal ``--``. The tail is the command ``run`` will launch.

    Done before argparse sees anything so that ``run -- cmd`` (namespace omitted) cannot be
    misread as ``run cmd``. Returns ``(head, None)`` when there is no ``--``.
    """
    args = list(argv)
    if "--" not in args:
        return args, None
    index = args.index("--")
    return args[:index], args[index + 1 :]


def resolve_namespace(explicit: str | None, *, allow_infer: bool) -> Namespace:
    """Turn the namespace argument into a ``Namespace``.

    Manifest inference (FR-020a) is not wired yet; until it is, the namespace must be named.
    """
    if explicit is not None:
        return validate_namespace(explicit)
    if allow_infer:
        raise UsageError(
            "no namespace given",
            "Name it as the first argument, or add a .keychain-cli.toml manifest to the "
            "current directory",
        )
    raise UsageError(
        "no namespace given",
        "Name it explicitly; this command never infers a namespace from a manifest",
    )


def default_store_factory() -> SecretStore:
    """Open the Keychain store. Imported lazily so the platform check runs first."""
    from keychain_cli.keychain.store import SecurityFrameworkStore, open_keychain

    override = os.environ.get(TEST_KEYCHAIN_ENV)
    if override:
        err(f"using test keychain {override}")
        return SecurityFrameworkStore(keychain=open_keychain(Path(override)))
    return SecurityFrameworkStore()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keychain-cli",
        description=(
            "Store project secrets in the macOS Keychain and hand them to one command's "
            "environment, instead of keeping a plaintext .env file."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    subparsers.add_parser("set", help="store one or more secrets in a namespace")
    subparsers.add_parser("list", help="list namespaces, or the variable names in one")
    run = subparsers.add_parser(
        "run",
        help="run a command with a namespace's secrets in its environment",
        usage="%(prog)s [NAMESPACE] -- COMMAND [ARG ...]",
    )
    run.add_argument("namespace", nargs="?", help="namespace to load (or omit to use the manifest)")
    subparsers.add_parser("import", help="import a .env file into a namespace")
    subparsers.add_parser("delete", help="delete one variable or a whole namespace")
    subparsers.add_parser("init", help="store the variables a project manifest requires")
    subparsers.add_parser("check", help="report which manifest variables are missing")
    subparsers.add_parser("copy", help="copy one secret to the clipboard (optional capability)")
    return parser


def _not_implemented(command: str) -> KeychainCliError:
    return KeychainCliError(
        f"the {command} command is not implemented in this build",
        "This build contains the storage layer only; see CHANGELOG.md",
    )


def _dispatch(args: argparse.Namespace, _command_tail: list[str], _services: Services) -> int:
    raise _not_implemented(args.command)


def _require_separator_for_run(head: list[str], command_tail: list[str] | None) -> list[str]:
    """``run`` must have ``--``; checked before argparse so the message explains the form."""
    if head and head[0] == "run" and command_tail is None:
        raise UsageError(
            "the run command needs `--` before the command to launch",
            "Use: keychain-cli run [NAMESPACE] -- COMMAND [ARG ...]",
        )
    return command_tail or []


def main(
    argv: Sequence[str] | None = None,
    *,
    store_factory: StoreFactory | None = None,
    prompts: Prompter | None = None,
    exec_fn: ExecFn | None = None,
    spawn_fn: SpawnFn | None = None,
) -> int:
    """Run the CLI and return its exit code. Never raises to the caller."""
    services = Services(
        store_factory=store_factory or default_store_factory,
        prompts=prompts or TtyPrompter(),
        exec_fn=exec_fn or _default_exec,
        spawn_fn=spawn_fn or _default_spawn,
    )
    try:
        ensure_supported()
        head, command_tail = split_command_tail(sys.argv[1:] if argv is None else argv)
        command_tail = _require_separator_for_run(head, command_tail)
        args = build_parser().parse_args(head)
        return _dispatch(args, command_tail, services)
    except SystemExit as exit_request:  # argparse --help/--version/usage errors
        code = exit_request.code
        return code if isinstance(code, int) else 2
    except KeychainCliError as error:
        err(format_error(error))
        return error.exit_code
    except KeyboardInterrupt:
        err("keychain-cli: interrupted")
        return EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - last line of defence; never print a traceback
        err(
            f"keychain-cli: unexpected error ({type(error).__name__}). "
            "Report the command you ran, without any secret values"
        )
        return 1


def _default_exec(file: str, argv: Sequence[str], env: Mapping[str, str]) -> None:
    """Replace this process with ``argv``. Only ``run`` will call it; no shell is involved."""
    os.execvpe(file, list(argv), dict(env))  # noqa: S606 - argv list, never a shell string


def _default_spawn(*args: Any, **kwargs: Any) -> Any:
    import subprocess  # noqa: PLC0415 - lazy; only the clipboard path spawns processes

    return subprocess.Popen(*args, **kwargs)  # noqa: S603 - argv list, never a shell string
