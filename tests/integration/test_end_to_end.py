"""End-to-end integration tests running keychain-cli subprocess against temporary keychain.

Note that stdio inheritance (FR-026) is inherent to exec and verified manually in
quickstart scenario 3.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.conftest import LEAK, assert_no_leak
from tests.integration.conftest import CliEnv, Sandbox, assert_sandbox_clean

if TYPE_CHECKING:
    from keychain_cli.keychain.store import SecurityFrameworkStore


def test_set_and_stdin(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    code, stdout, stderr = cli_env(
        ["set", "e2e-ns", "MY_TOKEN", "--stdin"], stdin=LEAK.encode() + b"\n"
    )
    assert code == 0
    assert_no_leak(stdout, stderr)

    ns = validate_namespace("e2e-ns")
    val = real_store.get(ns, "MY_TOKEN")
    assert val.data == LEAK.encode()

    assert_sandbox_clean(sandbox, LEAK)


def test_run_command_environment_and_lifecycle(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    ns = validate_namespace("e2e-run")
    real_store.add(ns, "SECRET_KEY", SecretValue.from_text("secret_val_123"))

    orig_env = dict(os.environ)

    # 1. /usr/bin/env output contains variables
    code, stdout, stderr = cli_env(["run", "e2e-run", "--", "/usr/bin/env"])
    assert code == 0
    assert "SECRET_KEY=secret_val_123" in stdout
    # Parent environment unchanged
    assert os.environ == orig_env
    assert_sandbox_clean(sandbox, "secret_val_123")

    # 2. sh -c 'exit 42' returns 42
    code, stdout, stderr = cli_env(["run", "e2e-run", "--", "/bin/sh", "-c", "exit 42"])
    assert code == 42
    assert_sandbox_clean(sandbox, "secret_val_123")

    # 3. non-existent command returns 8
    code, stdout, stderr = cli_env(["run", "e2e-run", "--", "no-such-cmd-xyz"])
    assert code == 8
    assert_sandbox_clean(sandbox, "secret_val_123")

    # 4. sleep interrupted via SIGINT
    proc = subprocess.Popen(
        [sys.executable, "-m", "keychain_cli", "run", "e2e-run", "--", "/bin/sleep", "30"],
        cwd=sandbox.work,
        env=sandbox.env,
    )
    time.sleep(0.3)
    os.kill(proc.pid, signal.SIGINT)

    start = time.time()
    killed = False
    while time.time() - start < 5.0:
        try:
            os.kill(proc.pid, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            killed = True
            break
    proc.wait()
    assert killed or proc.poll() is not None
    assert_sandbox_clean(sandbox, "secret_val_123")


def test_import_and_run(cli_env: CliEnv, real_store: object, sandbox: Sandbox) -> None:
    env_content = (
        "# comment\n"
        "export ALPHA=one\n"
        'BETA="two words"\n'
        "GAMMA='single # not a comment'\n"
        "DELTA=three # trailing comment\n"
        "this line is malformed\n"
        "BETA=override\n"
    )
    env_path = sandbox.work / "demo.env"
    env_path.write_text(env_content)
    sandbox.register(env_path)

    code, stdout, stderr = cli_env(["import", "qs-demo", "demo.env"])
    assert code == 0
    assert "warning: line 6: malformed entry" in stderr
    assert "duplicate key BETA (lines 3, 7): last value used" in stderr
    assert "stored: ALPHA, BETA, DELTA, GAMMA" in stderr

    cmd = [
        "run",
        "qs-demo",
        "--",
        "/bin/sh",
        "-c",
        'printf "%s|%s|%s|%s\\n" "$ALPHA" "$BETA" "$GAMMA" "$DELTA"',
    ]
    code, stdout, stderr = cli_env(cmd)
    assert code == 0
    assert stdout.strip() == "one|override|single # not a comment|three"

    assert_sandbox_clean(sandbox, "not_a_leak")


def test_list_namespaces_and_variables(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    ns1 = validate_namespace("Client-A")
    ns2 = validate_namespace("other")
    real_store.add(ns1, "VAR_B", SecretValue.from_text("secret_b"))
    real_store.add(ns1, "VAR_A", SecretValue.from_text("secret_a"))
    real_store.add(ns2, "OTHER_VAR", SecretValue.from_text("secret_other"))

    code, stdout, stderr = cli_env(["list", "--all"])
    assert code == 0
    assert stdout == "Client-A\nother\n"
    assert_no_leak(stdout, stderr)

    code, stdout, stderr = cli_env(["list", "client-a"])
    assert code == 0
    assert stdout == "VAR_A\nVAR_B\n"
    assert_no_leak(stdout, stderr)

    assert_sandbox_clean(sandbox, "secret_a")


def test_delete_lifecycle(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    ns = validate_namespace("del-ns")
    real_store.add(ns, "V1", SecretValue.from_text("val1"))
    real_store.add(ns, "V2", SecretValue.from_text("val2"))
    real_store.add(ns, "V3", SecretValue.from_text("val3"))

    # Delete single variable
    code, stdout, stderr = cli_env(["delete", "del-ns", "V1"])
    assert code == 0
    assert_no_leak(stdout, stderr)

    code, stdout, stderr = cli_env(["list", "del-ns"])
    assert code == 0
    assert stdout == "V2\nV3\n"

    # Delete entire namespace with --force
    code, stdout, stderr = cli_env(["delete", "del-ns", "--force"])
    assert code == 0
    assert_no_leak(stdout, stderr)

    code, stdout, stderr = cli_env(["list", "--all"])
    assert code == 0
    assert "del-ns" not in stdout

    assert_sandbox_clean(sandbox, "val1")


def test_manifest_workflow_init_and_check(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    manifest_content = 'namespace = "qs-manifest"\nvariables = ["VAR_A", "VAR_B"]\n'
    manifest_path = sandbox.work / ".keychain-cli.toml"
    manifest_path.write_text(manifest_content)
    sandbox.register(manifest_path)

    # 1. check missing variables -> exits 10
    code, stdout, stderr = cli_env(["check"])
    assert code == 10
    assert stdout == "VAR_A\nVAR_B\n"

    # 2. Add VAR_A directly to store
    ns = validate_namespace("qs-manifest")
    real_store.add(ns, "VAR_A", SecretValue.from_text("existing_a"))

    # 3. check again -> only VAR_B missing, exits 10
    code, stdout, stderr = cli_env(["check"])
    assert code == 10
    assert stdout.strip() == "VAR_B"

    # 4. init non-interactively with missing exits 7
    code, stdout, stderr = cli_env(["init"])
    assert code == 7

    # 5. Add VAR_B to complete namespace
    real_store.add(ns, "VAR_B", SecretValue.from_text("existing_b"))

    # 6. check complete -> exits 0
    code, stdout, stderr = cli_env(["check"])
    assert code == 0
    assert stdout == ""

    # 7. init complete -> prints complete, exits 0
    code, stdout, stderr = cli_env(["init"])
    assert code == 0
    assert "namespace qs-manifest is complete" in stderr

    assert_sandbox_clean(sandbox, "existing_a")
