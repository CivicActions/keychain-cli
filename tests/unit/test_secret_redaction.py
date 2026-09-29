"""``SecretValue`` never renders, and no error can carry a secret or its length (FR-037, FR-038)."""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

import inspect
import json

import pytest

from keychain_cli import errors
from keychain_cli.errors import KeychainCliError, KeychainError, format_error
from keychain_cli.secret import REDACTED, SecretValue
from tests.conftest import LEAK, assert_no_leak

FORBIDDEN_PARAMETER_NAMES = {"length", "size", "count", "len"}


@pytest.fixture
def secret() -> SecretValue:
    return SecretValue.from_text(LEAK)


def test_repr_and_str_are_redacted(secret: SecretValue) -> None:
    assert repr(secret) == REDACTED
    assert str(secret) == REDACTED
    assert_no_leak(repr(secret), str(secret), [secret], {"k": secret})


def test_fstring_and_format_raise(secret: SecretValue) -> None:
    with pytest.raises(TypeError):
        f"{secret}"  # noqa: B018 - the expression is the test
    with pytest.raises(TypeError):
        "{}".format(secret)  # noqa: UP032
    with pytest.raises(TypeError):
        format(secret, "")


def test_json_dumps_raises(secret: SecretValue) -> None:
    with pytest.raises(TypeError):
        json.dumps(secret)
    with pytest.raises(TypeError):
        json.dumps({"value": secret})


def test_data_is_the_only_way_to_the_bytes(secret: SecretValue) -> None:
    assert secret.data == LEAK.encode()
    assert SecretValue(b"a\nb \xc3\xbc").data == b"a\nb \xc3\xbc"


def test_only_bytes_accepted() -> None:
    with pytest.raises(TypeError):
        SecretValue("text")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SecretValue(bytearray(b"x"))  # type: ignore[arg-type]


def test_equality_by_bytes() -> None:
    assert SecretValue(b"x") == SecretValue(b"x")
    assert SecretValue(b"x") != SecretValue(b"y")
    assert SecretValue(b"x") != b"x"


def _error_classes() -> list[type[KeychainCliError]]:
    found = [
        obj
        for obj in vars(errors).values()
        if inspect.isclass(obj) and issubclass(obj, KeychainCliError)
    ]
    assert len(found) >= 9
    return found


@pytest.mark.parametrize("cls", _error_classes())
def test_error_constructors_reject_secret_values(
    cls: type[KeychainCliError], secret: SecretValue
) -> None:
    if cls is KeychainError:
        with pytest.raises(TypeError):
            KeychainError(-1, secret)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            KeychainError(-1, secret.data)  # type: ignore[arg-type]
        return
    with pytest.raises(TypeError):
        cls(secret, "next")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cls("what", secret)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cls(secret.data, "next")  # type: ignore[arg-type]


@pytest.mark.parametrize("cls", _error_classes())
def test_no_error_constructor_accepts_a_length(cls: type[KeychainCliError]) -> None:
    names = set(inspect.signature(cls.__init__).parameters) - {"self"}
    assert not names & FORBIDDEN_PARAMETER_NAMES, f"{cls.__name__} takes a length-like parameter"


@pytest.mark.parametrize("cls", _error_classes())
def test_formatted_errors_contain_no_secret(cls: type[KeychainCliError]) -> None:
    error = KeychainError(-25299, "dup") if cls is KeychainError else cls("what failed", "do this")
    text = format_error(error)
    assert text.startswith("keychain-cli: ")
    assert_no_leak(text, repr(error), str(error), error.args)


def test_keychain_error_message_carries_only_status_and_os_text() -> None:
    value = SecretValue(b"x" * 1234)
    error = KeychainError(-25299, "The specified item already exists in the keychain.")
    text = format_error(error)
    assert "1234" not in text
    assert "-25299" in text
    assert error.exit_code == 5
    del value


def test_exit_codes_match_contract() -> None:
    assert errors.UsageError.exit_code == 2
    assert errors.NotFoundError.exit_code == 3
    assert errors.RefusedError.exit_code == 4
    assert errors.KeychainError.exit_code == 5
    assert errors.UnsupportedPlatformError.exit_code == 6
    assert errors.InvalidInputError.exit_code == 7
    assert errors.CommandNotFoundError.exit_code == 8
    assert errors.ClipboardError.exit_code == 9
    assert errors.EXIT_CHECK_MISSING == 10
    assert errors.EXIT_INTERRUPTED == 130
