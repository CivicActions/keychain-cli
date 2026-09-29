"""Namespace and variable name rules (FR-007, FR-007a, FR-007b)."""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import pytest

from keychain_cli.errors import InvalidInputError
from keychain_cli.names import (
    NAMESPACE_FORM,
    VARIABLE_FORM,
    Namespace,
    validate_namespace,
    validate_variable,
)


@pytest.mark.parametrize(
    "display",
    ["client-a", "Client-A", "a", "0", "x" * 64, "proj.v2", "under_score", "A1-b2.c3_d4"],
)
def test_valid_namespaces(display: str) -> None:
    ns = validate_namespace(display)
    assert ns == Namespace(key=display.lower(), display=display)


@pytest.mark.parametrize(
    "display",
    [
        "",
        "x" * 65,
        "-leading",
        "_leading",
        ".leading",
        "has space",
        "bang!",
        "ünïcode",
        "a/b",
        "a:b",
    ],
)
def test_invalid_namespaces_name_the_allowed_form(display: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        validate_namespace(display)
    assert excinfo.value.exit_code == 7
    assert NAMESPACE_FORM in excinfo.value.next_step


def test_key_is_lowercase_and_display_is_preserved() -> None:
    ns = validate_namespace("Client-A")
    assert ns.key == "client-a"
    assert ns.display == "Client-A"
    assert validate_namespace("CLIENT-A").key == ns.key


def test_namespace_is_frozen() -> None:
    ns = validate_namespace("x")
    with pytest.raises(AttributeError):
        ns.key = "y"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["API_TOKEN", "_private", "a", "Api_Token", "X1", "__"])
def test_valid_variables(name: str) -> None:
    assert validate_variable(name) == name


@pytest.mark.parametrize("name", ["", "1ABC", "has-hyphen", "has space", "dot.name", "ünï", "a=b"])
def test_invalid_variables_name_the_allowed_form(name: str) -> None:
    with pytest.raises(InvalidInputError) as excinfo:
        validate_variable(name)
    assert excinfo.value.exit_code == 7
    assert VARIABLE_FORM in excinfo.value.next_step


def test_variable_names_are_case_sensitive() -> None:
    assert validate_variable("API_TOKEN") != validate_variable("Api_Token")
