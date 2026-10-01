"""Unit tests for `keychain-cli list` (US4, T049)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import json

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import InMemoryStore


def test_list_variables_sorted_and_no_values(run_cli: RunCli, store: InMemoryStore) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "Api_Token", SecretValue.from_text("secret2"))
    store.add(ns, "API_TOKEN", SecretValue.from_text("secret1"))
    store.add(ns, "DB_PASS", SecretValue.from_text("secret3"))

    code, stdout, stderr = run_cli(["list", "client-a"])
    assert code == 0
    assert stderr == ""
    assert stdout == "API_TOKEN\nApi_Token\nDB_PASS\n"
    assert "secret" not in stdout


def test_list_variables_json(run_cli: RunCli, store: InMemoryStore) -> None:
    ns = validate_namespace("client-a")
    store.add(ns, "VAR2", SecretValue.from_text("v2"))
    store.add(ns, "VAR1", SecretValue.from_text("v1"))

    code, stdout, stderr = run_cli(["list", "client-a", "--json"])
    assert code == 0
    assert stderr == ""
    assert stdout.strip() == '["VAR1","VAR2"]'
    assert json.loads(stdout) == ["VAR1", "VAR2"]


def test_list_missing_namespace_exits_3(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["list", "missing-ns"])
    assert code == 3
    assert stdout == ""
    assert "namespace 'missing-ns' not found" in stderr


def test_list_bare_lists_namespaces_sorted_by_key(run_cli: RunCli, store: InMemoryStore) -> None:
    store.add(validate_namespace("other"), "VAR", SecretValue.from_text("v"))
    store.add(validate_namespace("Client-A"), "VAR", SecretValue.from_text("v"))

    code, stdout, stderr = run_cli(["list"])
    assert code == 0
    assert stderr == ""
    assert stdout == "Client-A\nother\n"


def test_list_bare_empty_store_exits_0(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["list"])
    assert code == 0
    assert stdout == ""
    assert stderr == ""


def test_list_all_flag_lists_namespaces(run_cli: RunCli, store: InMemoryStore) -> None:
    store.add(validate_namespace("Client-A"), "VAR", SecretValue.from_text("v"))

    code, stdout, stderr = run_cli(["list", "--all"])
    assert code == 0
    assert stdout == "Client-A\n"


def test_list_all_with_namespace_positional_exits_2(run_cli: RunCli) -> None:
    code, stdout, stderr = run_cli(["list", "client-a", "--all"])
    assert code == 2
    assert "--all does not accept a namespace" in stderr


def test_list_namespaces_json(run_cli: RunCli, store: InMemoryStore) -> None:
    store.add(validate_namespace("Client-A"), "VAR", SecretValue.from_text("v"))
    store.add(validate_namespace("other"), "VAR", SecretValue.from_text("v"))

    code, stdout, stderr = run_cli(["list", "--json"])
    assert code == 0
    assert stdout.strip() == '["Client-A","other"]'
