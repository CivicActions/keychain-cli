"""Unit tests for manifest loading and validation (US6, T057)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from keychain_cli.errors import InvalidInputError, NotFoundError
from keychain_cli.manifest import MANIFEST_NAME, load_manifest


def test_valid_manifest_loads(tmp_path: Path) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text('namespace = "my-project"\nvariables = ["VAR1", "VAR2"]\n')

    m = load_manifest(tmp_path)
    assert m.namespace.key == "my-project"
    assert m.namespace.display == "my-project"
    assert m.variables == ["VAR1", "VAR2"]


def test_missing_manifest_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError) as exc:
        load_manifest(tmp_path)
    assert "not found" in exc.value.message


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ('variables = ["A"]\n', "missing required key 'namespace'"),
        ('namespace = "ns"\n', "missing required key 'variables'"),
        ('namespace = "ns"\nvariables = []\n', "variables list cannot be empty"),
        ('namespace = 123\nvariables = ["A"]\n', "'namespace' must be a string"),
        ('namespace = "ns"\nvariables = "A"\n', "'variables' must be an array of strings"),
        ('namespace = "ns"\nvariables = [123]\n', "each variable must be a string"),
        ('namespace = "bad!name"\nvariables = ["A"]\n', "invalid namespace name"),
        ('namespace = "ns"\nvariables = ["123BAD"]\n', "invalid variable name"),
        ('namespace = "ns"\nvariables = ["A", "A"]\n', "duplicate variable 'A'"),
        ('namespace = "ns"\nvariables = ["A"]\nextra = 1\n', "unknown key 'extra'"),
        ("[table]\nkey = 1\n", "tables or nested sections are not allowed"),
        ('namespace = "unclosed\n', "TOML parse error"),
    ],
)
def test_malformed_manifest_raises_invalid_input(tmp_path: Path, content: str, match: str) -> None:
    manifest_path = tmp_path / MANIFEST_NAME
    manifest_path.write_text(content)

    with pytest.raises(InvalidInputError) as exc:
        load_manifest(tmp_path)
    assert match in exc.value.message


def test_manifest_loader_exposes_no_write_functions() -> None:
    from keychain_cli import manifest

    funcs = [
        obj
        for name, obj in vars(manifest).items()
        if inspect.isfunction(obj) and not name.startswith("_")
    ]
    for func in funcs:
        sig = inspect.signature(func)
        assert "value" not in sig.parameters
        assert "secret" not in sig.parameters
