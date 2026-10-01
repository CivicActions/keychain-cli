"""Performance and lazy-import tests (T079, SC-007)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import os
import statistics
import sys
import time
from typing import TYPE_CHECKING

from keychain_cli.names import validate_namespace
from keychain_cli.secret import SecretValue
from tests.integration.conftest import CliEnv, Sandbox

if TYPE_CHECKING:
    from keychain_cli.keychain.store import SecurityFrameworkStore


def test_run_latency_and_lazy_imports(
    cli_env: CliEnv, real_store: SecurityFrameworkStore, sandbox: Sandbox
) -> None:
    ns = validate_namespace("perf-ns")
    real_store.add(ns, "SECRET", SecretValue.from_text("perf_val"))

    # 1. Measure latency over 5 runs
    times: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        code, stdout, stderr = cli_env(["run", "perf-ns", "--", "/usr/bin/true"])
        elapsed = time.perf_counter() - start
        assert code == 0
        times.append(elapsed)

    median_time = statistics.median(times)
    threshold = 3.0 if "CI" in os.environ else 1.0
    assert median_time < threshold, (
        f"Median execution time {median_time:.3f}s exceeds threshold {threshold}s"
    )

    # 2. Check lazy imports in a Python script invoked through the CLI
    check_script = (
        "import sys\n"
        "forbidden = ['keychain_cli.envfile', 'keychain_cli.manifest', 'keychain_cli.clipboard']\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "if loaded:\n"
        "    print(f'LEAKED_MODULES:{loaded}', file=sys.stderr)\n"
        "    sys.exit(1)\n"
    )
    script_path = sandbox.work / "check_imports.py"
    script_path.write_text(check_script)
    sandbox.register(script_path)

    code, stdout, stderr = cli_env(["run", "perf-ns", "--", sys.executable, str(script_path)])
    assert code == 0, f"Lazy import violation: {stderr}"
