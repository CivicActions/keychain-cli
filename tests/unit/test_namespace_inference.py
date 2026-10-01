"""Unit tests for namespace inference from `.keychain-cli.toml` (US6, T059)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from pathlib import Path

import pytest

from keychain_cli.manifest import MANIFEST_NAME
from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import RunCli
from tests.fakes import InMemoryStore, RecordingExec


def test_inference_in_cwd_for_run_list_init_check(
    run_cli: RunCli,
    store: InMemoryStore,
    exec_fn: RecordingExec,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "inferred-ns"\nvariables = ["A"]\n')

    ns = validate_namespace("inferred-ns")
    store.add(ns, "A", SecretValue.from_text("secret_val"))

    # 1. run
    code, stdout, stderr = run_cli(["run", "--", "echo", "hi"])
    assert code == 0
    assert "using namespace inferred-ns from .keychain-cli.toml" in stderr

    # 2. list
    code, stdout, stderr = run_cli(["list"])
    assert code == 0
    assert "using namespace inferred-ns from .keychain-cli.toml" in stderr
    assert stdout == "A\n"

    # 3. check
    code, stdout, stderr = run_cli(["check"])
    assert code == 0
    assert "using namespace inferred-ns from .keychain-cli.toml" in stderr

    # 4. init
    code, stdout, stderr = run_cli(["init"])
    assert code == 0
    assert "using namespace inferred-ns from .keychain-cli.toml" in stderr


def test_explicit_namespace_wins_with_mismatch_notice(
    run_cli: RunCli,
    store: InMemoryStore,
    exec_fn: RecordingExec,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "manifest-ns"\nvariables = ["A"]\n')

    ns = validate_namespace("explicit-ns")
    store.add(ns, "A", SecretValue.from_text("val"))

    code, stdout, stderr = run_cli(["run", "explicit-ns", "--", "echo", "hi"])
    assert code == 0
    assert "using namespace explicit-ns (manifest declares manifest-ns)" in stderr


def test_no_manifest_and_no_namespace_exits_2(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = run_cli(["run", "--", "echo", "hi"])
    assert code == 2
    assert "no namespace given" in stderr
    assert ".keychain-cli.toml" in stderr


def test_manifest_present_but_namespace_empty_run_points_to_init(
    run_cli: RunCli, store: InMemoryStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "empty-ns"\nvariables = ["A"]\n')

    code, stdout, stderr = run_cli(["run", "--", "echo", "hi"])
    assert code == 3
    assert "empty-ns" in stderr
    assert "init" in stderr


def test_manifest_in_parent_directory_not_found(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / MANIFEST_NAME).write_text('namespace = "parent-ns"\nvariables = ["A"]\n')
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    monkeypatch.chdir(sub_dir)

    code, stdout, stderr = run_cli(["run", "--", "echo", "hi"])
    assert code == 2
    assert "no namespace given" in stderr


def test_set_import_delete_ignore_manifest(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / MANIFEST_NAME).write_text('namespace = "ignored-ns"\nvariables = ["A"]\n')

    # set without namespace -> exit 2
    code, stdout, stderr = run_cli(["set"])
    assert code == 2

    # import without namespace -> exit 2
    code, stdout, stderr = run_cli(["import"])
    assert code == 2

    # delete without namespace -> exit 2
    code, stdout, stderr = run_cli(["delete"])
    assert code == 2
