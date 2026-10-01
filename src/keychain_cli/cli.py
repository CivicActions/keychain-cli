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
    InvalidInputError,
    KeychainCliError,
    NotFoundError,
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
    """Turn the namespace argument into a ``Namespace``, with manifest inference."""
    from keychain_cli.manifest import MANIFEST_NAME, load_manifest

    if explicit is not None:
        ns = validate_namespace(explicit)
        # Check if manifest exists in cwd and declares a different namespace
        try:
            manifest = load_manifest(Path.cwd())
            if manifest.namespace.key != ns.key:
                err(
                    f"using namespace {ns.display} (manifest declares {manifest.namespace.display})"
                )
        except (NotFoundError, InvalidInputError):
            pass
        return ns

    if allow_infer:
        try:
            manifest = load_manifest(Path.cwd())
            err(f"using namespace {manifest.namespace.display} from {MANIFEST_NAME}")
            return manifest.namespace
        except NotFoundError:
            raise UsageError(
                "no namespace given",
                "Name it as the first argument, or add a .keychain-cli.toml manifest to the "
                "current directory",
            ) from None

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

    set_parser = subparsers.add_parser(
        "set",
        help="store one or more secrets in a namespace",
        description=(
            "Store secrets in a namespace via interactive prompts or standard input.\n\n"
            "Example:\n"
            "  keychain-cli set client-a API_TOKEN DB_PASSWORD\n\n"
            "Standard input rule:\n"
            "  With --stdin or when standard input is not a TTY, exactly one variable name\n"
            "  must be given, and the secret value is read from standard input.\n\n"
            "Exit codes:\n"
            "  0: All requested variables stored or overwritten\n"
            "  4: At least one variable skipped or overwrite refused\n"
            "  5: Keychain operation failed\n"
            "  7: Invalid variable name, duplicate variable, or invalid stdin input\n"
            "  130: Interrupted by user"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    set_parser.add_argument("namespace", help="target namespace")
    set_parser.add_argument("variables", nargs="+", help="variable name(s) to store")
    set_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing variables without confirmation",
    )
    set_parser.add_argument(
        "--stdin",
        action="store_true",
        help="read value from standard input (exactly one variable)",
    )
    list_parser = subparsers.add_parser(
        "list",
        help="list namespaces, or the variable names in one",
        description=(
            "List namespaces, or the variable names in a namespace.\n\n"
            "If no namespace is given and a .keychain-cli.toml manifest exists in the\n"
            "current directory, that namespace's variables are listed.\n\n"
            "Examples:\n"
            "  keychain-cli list\n"
            "  keychain-cli list client-a\n"
            "  keychain-cli list --all\n\n"
            "Exit codes:\n"
            "  0: Success\n"
            "  2: Invalid arguments\n"
            "  3: Namespace not found"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_parser.add_argument("namespace", nargs="?", help="namespace to list variables for")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="list all namespaces, ignoring any current-directory manifest",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="emit names as a compact JSON array on stdout",
    )
    run = subparsers.add_parser(
        "run",
        help="run a command with a namespace's secrets in its environment",
        usage="%(prog)s [NAMESPACE] -- COMMAND [ARG ...]",
        description=(
            "Run a command with secrets from a namespace injected into its environment.\n\n"
            "If no namespace is given, the namespace is inferred from .keychain-cli.toml\n"
            "in the current directory.\n\n"
            "Example:\n"
            "  keychain-cli run client-a -- /usr/bin/env\n\n"
            "The `--` separator is required to separate keychain-cli arguments from the command.\n"
            "After launch, the exit status is the command's own exit status.\n\n"
            "Exit codes (before launch):\n"
            "  2: Missing `--` or invalid usage\n"
            "  3: Namespace not found\n"
            "  5: Keychain operation failed\n"
            "  8: Command not found or not executable"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run.add_argument("namespace", nargs="?", help="namespace to load (or omit to use the manifest)")
    import_parser = subparsers.add_parser(
        "import",
        help="import a .env file into a namespace",
        description=(
            "Import variables from a .env-style file into a namespace.\n\n"
            "Example:\n"
            "  keychain-cli import client-a project.env\n\n"
            "Parsing rules:\n"
            "  - Blank lines and lines starting with '#' are ignored\n"
            "  - Optional leading 'export '\n"
            "  - KEY=value syntax with single, double, or unquoted values\n"
            "  - Trailing unquoted comments starting with ' #' are stripped\n"
            "  - The source file is never modified\n\n"
            "Exit codes:\n"
            "  0: Every parsed entry stored or overwritten\n"
            "  3: File not found\n"
            "  4: Overwrite declined or skipped\n"
            "  5: Keychain operation failed\n"
            "  7: File unreadable, not regular, or every line malformed\n"
            "  130: Interrupted by user"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    import_parser.add_argument("namespace", help="target namespace")
    import_parser.add_argument("file", help="path to .env file to import")
    import_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing variables without confirmation",
    )
    delete_parser = subparsers.add_parser(
        "delete",
        help="delete one variable or a whole namespace",
        description=(
            "Delete a single variable or an entire namespace.\n\n"
            "Examples:\n"
            "  keychain-cli delete client-a API_TOKEN\n"
            "  keychain-cli delete client-a\n\n"
            "Deleting an entire namespace requires interactive confirmation by typing\n"
            "the namespace name, or passing --force.\n"
            "The namespace is never inferred from a manifest for delete.\n\n"
            "Exit codes:\n"
            "  0: Deleted successfully\n"
            "  2: Missing namespace or invalid arguments\n"
            "  3: Variable or namespace not found\n"
            "  4: Deletion declined or non-interactive without --force\n"
            "  5: Keychain operation failed"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    delete_parser.add_argument("namespace", help="target namespace (never inferred)")
    delete_parser.add_argument("variable", nargs="?", help="optional variable name to delete")
    delete_parser.add_argument(
        "--force",
        action="store_true",
        help="delete whole namespace without confirmation",
    )
    init_parser = subparsers.add_parser(
        "init",
        help="store the variables a project manifest requires",
        description=(
            "Prompt for and store any variables declared in .keychain-cli.toml that\n"
            "are not already present in the Keychain.\n\n"
            "Examples:\n"
            "  keychain-cli init\n"
            "  keychain-cli init client-a\n\n"
            "Exit codes:\n"
            "  0: Complete; all declared variables are stored\n"
            "  3: Manifest file not found\n"
            "  5: Keychain operation failed\n"
            "  7: Manifest malformed, or missing variables when run non-interactively\n"
            "  130: Interrupted by user"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_parser.add_argument("namespace", nargs="?", help="optional namespace override")

    check_parser = subparsers.add_parser(
        "check",
        help="report which manifest variables are missing",
        description=(
            "Report which variables declared in .keychain-cli.toml are missing.\n\n"
            "Examples:\n"
            "  keychain-cli check\n"
            "  keychain-cli check --json\n\n"
            "Exit codes:\n"
            "  0: All required variables are present\n"
            "  3: Manifest file not found\n"
            "  7: Manifest malformed\n"
            "  10: One or more required variables are missing"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check_parser.add_argument("namespace", nargs="?", help="optional namespace override")
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="emit missing variable names as a compact JSON array on stdout",
    )
    copy_parser = subparsers.add_parser(
        "copy",
        help="copy one secret to the clipboard (optional capability)",
        description=(
            "Copy a single secret to the system clipboard for pasting into applications\n"
            "that cannot read environment variables.\n\n"
            "Example:\n"
            "  keychain-cli copy client-a API_TOKEN\n\n"
            "Security notice:\n"
            "  Not the normal way to use a secret; prefer `run`.\n"
            "  The clipboard is readable by every application running as you, and clipboard\n"
            "  managers or history tools can defeat automatic clearing.\n\n"
            "Exit codes:\n"
            "  0: Copied and clearing scheduled\n"
            "  2: Clearing interval out of range or invalid arguments\n"
            "  3: Variable or namespace not found\n"
            "  5: Keychain operation failed\n"
            "  9: Clipboard write failed or clearing helper could not be started"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    copy_parser.add_argument("namespace", help="target namespace (never inferred)")
    copy_parser.add_argument("variable", help="exact name of variable to copy")
    copy_parser.add_argument(
        "--clear-after",
        type=int,
        default=45,
        help="seconds before clearing the clipboard (1-300, default 45)",
    )
    return parser


def _not_implemented(command: str) -> KeychainCliError:
    return KeychainCliError(
        f"the {command} command is not implemented in this build",
        "This build contains the storage layer only; see CHANGELOG.md",
    )


def _dispatch(args: argparse.Namespace, _command_tail: list[str], services: Services) -> int:
    store = services.store_factory()
    if args.command == "set":
        from keychain_cli.commands.set_ import run_set

        return run_set(args, store, services.prompts)
    if args.command == "run":
        from keychain_cli.commands.run import run_run

        return run_run(
            args,
            _command_tail,
            store,
            services.exec_fn,
            resolve_ns_fn=lambda ns: resolve_namespace(ns, allow_infer=True),
        )
    if args.command == "import":
        from keychain_cli.commands.import_ import run_import

        return run_import(args, store, services.prompts)
    if args.command == "list":
        from keychain_cli.commands.list_ import run_list

        return run_list(
            args,
            store,
            resolve_ns_fn=lambda ns: resolve_namespace(ns, allow_infer=True),
        )
    if args.command == "delete":
        from keychain_cli.commands.delete import run_delete

        return run_delete(args, store, services.prompts)
    if args.command == "init":
        from keychain_cli.commands.init import run_init

        return run_init(
            args,
            store,
            services.prompts,
            resolve_ns_fn=lambda ns: resolve_namespace(ns, allow_infer=True),
        )
    if args.command == "check":
        from keychain_cli.commands.check import run_check

        return run_check(
            args,
            store,
            resolve_ns_fn=lambda ns: resolve_namespace(ns, allow_infer=True),
        )
    if args.command == "copy":
        from keychain_cli.commands.copy import run_copy

        return run_copy(args, store, services.spawn_fn)
    raise _not_implemented(args.command)


def _require_separator_for_run(head: list[str], command_tail: list[str] | None) -> list[str]:
    """``run`` must have ``--``; checked before argparse so the message explains the form."""
    if head and head[0] == "run" and command_tail is None:
        if "-h" in head or "--help" in head:
            return []
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
