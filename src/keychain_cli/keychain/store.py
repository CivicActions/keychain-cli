"""``SecretStore`` on the macOS Keychain via the Security framework.

Item layout (data-model.md, "KeychainItem"):

    kSecClass        generic password
    kSecAttrService  "keychain-cli:<namespace key>"   exact-match grouping key
    kSecAttrAccount  variable name                     case-sensitive
    kSecAttrCreator  0x6B63636C ('kccl')               ownership stamp, enumeration key
    kSecAttrGeneric  namespace display name (UTF-8)    first-given casing
    kSecAttrLabel    "keychain-cli: <Display>/<VAR>"   for Keychain Access only
    kSecValueData    the secret                        requested only by get/get_all

Every query carries the creator stamp, so items the tool did not create are invisible to
it. List operations ask for attributes only and never for data.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

from keychain_cli.keychain import AlreadyExists, NotFound, StoreError, _cf, _sec
from keychain_cli.keychain._sec import Keys
from keychain_cli.names import Namespace
from keychain_cli.secret import SecretValue

KeychainHandle = int

_Pairs = list[tuple[int, int]]


class SecurityFrameworkStore:
    """Production store. Pass ``keychain`` to target a specific keychain file (tests)."""

    def __init__(self, keychain: KeychainHandle | None = None) -> None:
        self._keychain = keychain

    # ---- listing (attributes only) -------------------------------------------------

    def list_namespaces(self) -> list[Namespace]:
        rows = self._match_attributes(namespace=None, name=None)
        seen: dict[str, Namespace] = {}
        for service, _account, display in rows:
            key = service[len(_sec.SERVICE_PREFIX) :]
            seen.setdefault(key, Namespace(key=key, display=display or key))
        return [seen[key] for key in sorted(seen)]

    def list_variables(self, namespace: Namespace) -> list[str]:
        rows = self._match_attributes(namespace=namespace, name=None)
        if not rows:
            raise NotFound(namespace.display)
        return sorted(account for _service, account, _display in rows)

    def exists(self, namespace: Namespace, name: str) -> bool:
        return bool(self._match_attributes(namespace=namespace, name=name))

    # ---- reading values ----------------------------------------------------------

    def get(self, namespace: Namespace, name: str) -> SecretValue:
        with _cf.CFObjects() as cf:
            query = self._query(cf, namespace=namespace, name=name)
            query.append((Keys.RETURN_DATA, _cf.BOOLEAN_TRUE))
            status, result = _sec.item_copy_matching(cf.dictionary(query))
        if status == _sec.ERR_NOT_FOUND:
            raise NotFound(name)
        _raise_unless_ok(status)
        try:
            if not _cf.is_data(result):
                raise StoreError(status, "unexpected result type from SecItemCopyMatching")
            return SecretValue(_cf.to_bytes(result))
        finally:
            _cf.release(result)

    def get_all(self, namespace: Namespace) -> dict[str, SecretValue]:
        # One attribute query for the names, then one data query per variable. The file-based
        # keychain rejects kSecReturnData combined with kSecMatchLimitAll (errSecParam, -50).
        names = self.list_variables(namespace)
        return {name: self.get(namespace, name) for name in names}

    # ---- writing -----------------------------------------------------------------

    def add(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        display = self._existing_display(namespace) or namespace.display
        with _cf.CFObjects() as cf:
            attributes: _Pairs = [
                (Keys.CLASS, Keys.CLASS_GENERIC_PASSWORD),
                (Keys.ATTR_SERVICE, cf.string(_service(namespace))),
                (Keys.ATTR_ACCOUNT, cf.string(name)),
                (Keys.ATTR_CREATOR, cf.number32(_sec.CREATOR_STAMP)),
                (Keys.ATTR_GENERIC, cf.data(display.encode("utf-8"))),
                (Keys.ATTR_LABEL, cf.string(f"keychain-cli: {display}/{name}")),
                (Keys.VALUE_DATA, cf.data(value.data)),
            ]
            if self._keychain is not None:
                attributes.append((Keys.USE_KEYCHAIN, self._keychain))
            status = _sec.item_add(cf.dictionary(attributes))
        if status == _sec.ERR_DUPLICATE:
            raise AlreadyExists(name)
        _raise_unless_ok(status)

    def update(self, namespace: Namespace, name: str, value: SecretValue) -> None:
        with _cf.CFObjects() as cf:
            query = self._query(cf, namespace=namespace, name=name)
            changes: _Pairs = [(Keys.VALUE_DATA, cf.data(value.data))]
            status = _sec.item_update(cf.dictionary(query), cf.dictionary(changes))
        if status == _sec.ERR_NOT_FOUND:
            raise NotFound(name)
        _raise_unless_ok(status)

    # ---- deleting ----------------------------------------------------------------

    def delete_variable(self, namespace: Namespace, name: str) -> None:
        with _cf.CFObjects() as cf:
            query = self._query(cf, namespace=namespace, name=name)
            status = _sec.item_delete(cf.dictionary(query))
        if status == _sec.ERR_NOT_FOUND:
            raise NotFound(name)
        _raise_unless_ok(status)

    def delete_namespace(self, namespace: Namespace) -> int:
        count = len(self.list_variables(namespace))
        with _cf.CFObjects() as cf:
            query = self._query(cf, namespace=namespace, name=None)
            query.append((Keys.MATCH_LIMIT, Keys.MATCH_LIMIT_ALL))
            status = _sec.item_delete(cf.dictionary(query))
        if status == _sec.ERR_NOT_FOUND:
            raise NotFound(namespace.display)
        _raise_unless_ok(status)
        return count

    # ---- internals ---------------------------------------------------------------

    def _query(self, cf: _cf.CFObjects, *, namespace: Namespace | None, name: str | None) -> _Pairs:
        """The base query every read and delete uses: class, stamp, optional scope."""
        pairs: _Pairs = [
            (Keys.CLASS, Keys.CLASS_GENERIC_PASSWORD),
            (Keys.ATTR_CREATOR, cf.number32(_sec.CREATOR_STAMP)),
        ]
        if namespace is not None:
            pairs.append((Keys.ATTR_SERVICE, cf.string(_service(namespace))))
        if name is not None:
            pairs.append((Keys.ATTR_ACCOUNT, cf.string(name)))
        if self._keychain is not None:
            pairs.append((Keys.MATCH_SEARCH_LIST, cf.array([self._keychain])))
        return pairs

    def _match_attributes(
        self, *, namespace: Namespace | None, name: str | None
    ) -> list[tuple[str, str, str]]:
        """Attribute-only query. Returns ``(service, account, display)`` rows, never data."""
        with _cf.CFObjects() as cf:
            query = self._query(cf, namespace=namespace, name=name)
            query.append((Keys.MATCH_LIMIT, Keys.MATCH_LIMIT_ALL))
            query.append((Keys.RETURN_ATTRIBUTES, _cf.BOOLEAN_TRUE))
            status, result = _sec.item_copy_matching(cf.dictionary(query))
        if status == _sec.ERR_NOT_FOUND:
            return []
        _raise_unless_ok(status)
        try:
            rows: list[tuple[str, str, str]] = []
            for item in _iter_dicts(result):
                service = _cf.dict_get(item, Keys.ATTR_SERVICE)
                account = _cf.dict_get(item, Keys.ATTR_ACCOUNT)
                generic = _cf.dict_get(item, Keys.ATTR_GENERIC)
                if not (service and account):
                    continue
                display = _cf.to_bytes(generic).decode("utf-8", errors="replace") if generic else ""
                rows.append((_cf.to_str(service), _cf.to_str(account), display))
            return rows
        finally:
            _cf.release(result)

    def _existing_display(self, namespace: Namespace) -> str | None:
        rows = self._match_attributes(namespace=namespace, name=None)
        for _service, _account, display in rows:
            if display:
                return display
        return None


def _service(namespace: Namespace) -> str:
    return _sec.SERVICE_PREFIX + namespace.key


def _iter_dicts(result: int) -> Sequence[int]:
    if not result:
        return []
    if _cf.is_array(result):
        return [item for item in _cf.array_items(result) if _cf.is_dictionary(item)]
    if _cf.is_dictionary(result):
        return [result]
    return []


def _raise_unless_ok(status: int) -> None:
    if status != 0:
        raise StoreError(status, _sec.status_message(status))


# ---- keychain files (integration tests and the test-keychain override) -------------


class TemporaryKeychain:
    """Create a throwaway keychain file and delete it on exit.

    Used only by the integration test suite so tests never touch the login keychain. The
    unlock password is random and discarded; nothing about it is a secret worth keeping.
    """

    def __init__(self, directory: Path) -> None:
        self.path = directory / "keychain-cli-test.keychain-db"
        self.handle: KeychainHandle = 0

    def __enter__(self) -> Self:
        status, handle = _sec.keychain_create(str(self.path), os.urandom(24).hex().encode())
        _raise_unless_ok(status)
        self.handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.handle:
            _sec.keychain_delete(self.handle)
            self.handle = 0
        self.path.unlink(missing_ok=True)


def open_keychain(path: Path) -> KeychainHandle:
    """Open an existing keychain file. Used for ``KEYCHAIN_CLI_TEST_KEYCHAIN``."""
    status, handle = _sec.keychain_open(str(path))
    _raise_unless_ok(status)
    return handle
