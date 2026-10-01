"""Manifest loader and validator for `.keychain-cli.toml` (US6, T061)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from keychain_cli.errors import InvalidInputError, NotFoundError
from keychain_cli.names import Namespace, validate_namespace, validate_variable

MANIFEST_NAME = ".keychain-cli.toml"
ALLOWED_KEYS = {"namespace", "variables"}


@dataclass(frozen=True)
class Manifest:
    """The contents of a `.keychain-cli.toml` file."""

    namespace: Namespace
    variables: list[str]


def load_manifest(directory: Path) -> Manifest:
    """Load and validate `.keychain-cli.toml` from the specified directory."""
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.exists():
        raise NotFoundError(
            f"manifest '{MANIFEST_NAME}' not found in {directory}",
            f"Create a {MANIFEST_NAME} file in the project directory, "
            "or name the namespace explicitly",
        )

    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except (PermissionError, OSError) as err:
        raise InvalidInputError(
            f"cannot read '{MANIFEST_NAME}': {err.strerror}",
            f"Make sure {MANIFEST_NAME} is readable",
        ) from None

    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as err:
        raise InvalidInputError(
            f"TOML parse error in '{MANIFEST_NAME}': {err}",
            f"Fix the syntax error in {MANIFEST_NAME}",
        ) from None

    for key, val in data.items():
        if isinstance(val, dict):
            raise InvalidInputError(
                f"tables or nested sections are not allowed in '{MANIFEST_NAME}'",
                "Define 'namespace' and 'variables' at the top level only",
            )
        if key not in ALLOWED_KEYS:
            raise InvalidInputError(
                f"unknown key '{key}' in '{MANIFEST_NAME}'",
                f"Allowed keys are {', '.join(sorted(ALLOWED_KEYS))}",
            )

    if "namespace" not in data:
        raise InvalidInputError(
            f"missing required key 'namespace' in '{MANIFEST_NAME}'",
            "Specify a namespace string in the manifest",
        )
    if not isinstance(data["namespace"], str):
        raise InvalidInputError(
            f"'namespace' must be a string in '{MANIFEST_NAME}'",
            "Specify the namespace as a quoted string",
        )
    namespace = validate_namespace(data["namespace"])

    if "variables" not in data:
        raise InvalidInputError(
            f"missing required key 'variables' in '{MANIFEST_NAME}'",
            "Specify an array of variable names in the manifest",
        )
    if not isinstance(data["variables"], list):
        raise InvalidInputError(
            f"'variables' must be an array of strings in '{MANIFEST_NAME}'",
            "Specify variables as a list of strings",
        )
    if not data["variables"]:
        raise InvalidInputError(
            f"variables list cannot be empty in '{MANIFEST_NAME}'",
            "List at least one variable name that the project requires",
        )

    variables: list[str] = []
    seen: set[str] = set()
    for var in data["variables"]:
        if not isinstance(var, str):
            raise InvalidInputError(
                f"each variable must be a string in '{MANIFEST_NAME}'",
                "Ensure every variable in the list is a quoted string",
            )
        validate_variable(var)
        if var in seen:
            raise InvalidInputError(
                f"duplicate variable '{var}' in '{MANIFEST_NAME}'",
                "Remove the duplicate variable name from the list",
            )
        seen.add(var)
        variables.append(var)

    return Manifest(namespace=namespace, variables=variables)
