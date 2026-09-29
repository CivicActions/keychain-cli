"""The real Security framework backend against a throwaway keychain (T028).

Covers the KeychainItem layout, the creator-stamp isolation, display-name inheritance, and
every status-code mapping the store relies on.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name,import-outside-toplevel

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from keychain_cli.keychain import AlreadyExists, NotFound
from keychain_cli.names import Namespace, validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import LEAK

if TYPE_CHECKING:
    from keychain_cli.keychain.store import SecurityFrameworkStore

CLIENT_A = validate_namespace("Client-A")
OTHER = validate_namespace("other")


@pytest.mark.parametrize(
    "raw",
    [
        b"placeholder-ascii",
        b"line1\nline2\n",
        "spaces 'quotes' \"double\" ünïcödé 🔑".encode(),
        b"\x00binary\xff",
        b"k" * 16 * 1024,
        LEAK.encode(),
    ],
)
def test_add_get_round_trip(real_store: SecurityFrameworkStore, raw: bytes) -> None:
    real_store.add(CLIENT_A, "VALUE", SecretValue(raw))
    assert real_store.get(CLIENT_A, "VALUE").data == raw


def test_add_twice_raises_already_exists_and_keeps_first_value(
    real_store: SecurityFrameworkStore,
) -> None:
    real_store.add(CLIENT_A, "API_TOKEN", SecretValue(b"first"))
    with pytest.raises(AlreadyExists):
        real_store.add(CLIENT_A, "API_TOKEN", SecretValue(b"second"))
    assert real_store.get(CLIENT_A, "API_TOKEN").data == b"first"


def test_missing_items_raise_not_found(real_store: SecurityFrameworkStore) -> None:
    with pytest.raises(NotFound):
        real_store.get(CLIENT_A, "NOPE")
    with pytest.raises(NotFound):
        real_store.get_all(CLIENT_A)
    with pytest.raises(NotFound):
        real_store.list_variables(CLIENT_A)
    with pytest.raises(NotFound):
        real_store.update(CLIENT_A, "NOPE", SecretValue(b"x"))
    with pytest.raises(NotFound):
        real_store.delete_variable(CLIENT_A, "NOPE")
    with pytest.raises(NotFound):
        real_store.delete_namespace(CLIENT_A)
    assert real_store.exists(CLIENT_A, "NOPE") is False
    assert real_store.list_namespaces() == []


def test_list_variables_is_sorted_and_case_sensitive(real_store: SecurityFrameworkStore) -> None:
    for name in ("b_lower", "API_TOKEN", "Api_Token", "DB_PASSWORD"):
        real_store.add(CLIENT_A, name, SecretValue(b"v"))
    assert real_store.list_variables(CLIENT_A) == [
        "API_TOKEN",
        "Api_Token",
        "DB_PASSWORD",
        "b_lower",
    ]
    assert real_store.exists(CLIENT_A, "API_TOKEN") is True
    assert real_store.exists(CLIENT_A, "api_token") is False


def test_list_namespaces_groups_by_lowercase_key_and_shows_first_casing(
    real_store: SecurityFrameworkStore,
) -> None:
    real_store.add(CLIENT_A, "A", SecretValue(b"1"))
    real_store.add(validate_namespace("client-a"), "B", SecretValue(b"2"))
    real_store.add(validate_namespace("CLIENT-A"), "C", SecretValue(b"3"))
    real_store.add(OTHER, "X", SecretValue(b"4"))
    assert real_store.list_namespaces() == [
        Namespace(key="client-a", display="Client-A"),
        Namespace(key="other", display="other"),
    ]
    assert real_store.list_variables(validate_namespace("cLiEnT-a")) == ["A", "B", "C"]


def test_display_name_is_inherited_by_later_additions(real_store: SecurityFrameworkStore) -> None:
    real_store.add(validate_namespace("client-a"), "FIRST", SecretValue(b"1"))
    real_store.add(validate_namespace("Client-A"), "SECOND", SecretValue(b"2"))
    assert real_store.list_namespaces() == [Namespace(key="client-a", display="client-a")]


def test_get_all_returns_every_value(real_store: SecurityFrameworkStore) -> None:
    real_store.add(CLIENT_A, "A", SecretValue(b"1"))
    real_store.add(CLIENT_A, "B", SecretValue(b"2\n"))
    real_store.add(OTHER, "C", SecretValue(b"3"))
    values = real_store.get_all(CLIENT_A)
    assert {k: v.data for k, v in values.items()} == {"A": b"1", "B": b"2\n"}


def test_update_replaces_value(real_store: SecurityFrameworkStore) -> None:
    real_store.add(CLIENT_A, "A", SecretValue(b"old"))
    real_store.update(CLIENT_A, "A", SecretValue(b"new"))
    assert real_store.get(CLIENT_A, "A").data == b"new"
    assert real_store.list_variables(CLIENT_A) == ["A"]


def test_delete_variable_leaves_others(real_store: SecurityFrameworkStore) -> None:
    for name in ("A", "B", "C"):
        real_store.add(CLIENT_A, name, SecretValue(b"v"))
    real_store.delete_variable(CLIENT_A, "B")
    assert real_store.list_variables(CLIENT_A) == ["A", "C"]


def test_delete_last_variable_removes_namespace(real_store: SecurityFrameworkStore) -> None:
    real_store.add(CLIENT_A, "ONLY", SecretValue(b"v"))
    real_store.delete_variable(CLIENT_A, "ONLY")
    assert real_store.list_namespaces() == []


def test_delete_namespace_returns_count_and_spares_others(
    real_store: SecurityFrameworkStore,
) -> None:
    for name in ("A", "B", "C"):
        real_store.add(CLIENT_A, name, SecretValue(b"v"))
    real_store.add(OTHER, "X", SecretValue(b"v"))
    assert real_store.delete_namespace(CLIENT_A) == 3
    assert real_store.list_namespaces() == [OTHER]
    with pytest.raises(NotFound):
        real_store.list_variables(CLIENT_A)


def test_items_without_the_creator_stamp_are_invisible(
    real_store: SecurityFrameworkStore, temp_keychain: int
) -> None:
    from keychain_cli.keychain import _cf, _sec
    from keychain_cli.keychain._sec import Keys

    # An item with the tool's service prefix but no stamp, added directly via the framework.
    with _cf.CFObjects() as cf:
        status = _sec.item_add(
            cf.dictionary(
                [
                    (Keys.CLASS, Keys.CLASS_GENERIC_PASSWORD),
                    (Keys.ATTR_SERVICE, cf.string(_sec.SERVICE_PREFIX + "client-a")),
                    (Keys.ATTR_ACCOUNT, cf.string("FOREIGN")),
                    (Keys.VALUE_DATA, cf.data(b"not-ours")),
                    (Keys.USE_KEYCHAIN, temp_keychain),
                ]
            )
        )
    assert status == 0

    assert real_store.list_namespaces() == []
    assert real_store.exists(CLIENT_A, "FOREIGN") is False
    with pytest.raises(NotFound):
        real_store.get(CLIENT_A, "FOREIGN")
    with pytest.raises(NotFound):
        real_store.delete_variable(CLIENT_A, "FOREIGN")

    # Adding our own item with the same (service, account) is a Keychain-level duplicate.
    with pytest.raises(AlreadyExists):
        real_store.add(CLIENT_A, "FOREIGN", SecretValue(b"ours"))


def test_store_error_carries_status_and_os_text_only() -> None:
    from keychain_cli.keychain import StoreError, _sec

    error = StoreError(
        _sec.ERR_INTERACTION_NOT_ALLOWED, _sec.status_message(_sec.ERR_INTERACTION_NOT_ALLOWED)
    )
    assert error.exit_code == 5
    assert error.os_status == -25308
    assert "-25308" in error.message
    assert LEAK not in repr(error)


def test_temporary_keychain_is_removed_on_exit(tmp_path: object) -> None:
    from pathlib import Path

    from keychain_cli.keychain.store import TemporaryKeychain

    assert isinstance(tmp_path, Path)
    with TemporaryKeychain(tmp_path) as keychain:
        assert keychain.path.exists()
        assert keychain.handle
    assert not keychain.path.exists()
    assert keychain.handle == 0
