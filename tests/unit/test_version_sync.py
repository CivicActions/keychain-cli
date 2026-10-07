"""Guard that every declared version string stays in lockstep.

Release Please rewrites the version in `pyproject.toml` (via its `python` release type), in
`src/keychain_cli/__init__.py` (via an `extra-files` generic updater keyed on the
`x-release-please-version` annotation), in `uv.lock` (via an `extra-files` TOML updater keyed on a
JSONPath), and in `.release-please-manifest.json`. Those are independent mechanisms, so this module
fails loudly if an annotation is ever dropped, a path is renamed, or someone edits one of them by
hand.

The `uv.lock` check earns its place: `uv.lock` records the project's *own* version in its
`[[package]]` table, so a bump that misses it leaves the lockfile stale and `uv lock --check` fails
in CI on the release pull request itself.
"""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from keychain_cli import __version__

RELEASE_PLEASE_ANNOTATION = "x-release-please-version"
REPO_ROOT = Path(__file__).parents[2]
PACKAGE_NAME = "keychain-cli"


def test_pyproject_version_matches_dunder_version() -> None:
    pyproject = REPO_ROOT / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert declared == __version__, (
        f"pyproject.toml declares {declared} but keychain_cli.__version__ is {__version__}; "
        "Release Please owns both, so a mismatch means an updater did not fire"
    )


def test_release_please_manifest_matches_dunder_version() -> None:
    manifest = REPO_ROOT / ".release-please-manifest.json"
    recorded = json.loads(manifest.read_text(encoding="utf-8"))["."]

    assert recorded == __version__, (
        f".release-please-manifest.json records {recorded} but "
        f"keychain_cli.__version__ is {__version__}"
    )


def test_uv_lock_records_the_current_version() -> None:
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    entries = [entry for entry in lock["package"] if entry["name"] == PACKAGE_NAME]

    assert len(entries) == 1, f"expected exactly one {PACKAGE_NAME} entry in uv.lock, got {entries}"

    locked = entries[0]["version"]
    assert locked == __version__, (
        f"uv.lock pins {PACKAGE_NAME} {locked} but keychain_cli.__version__ is {__version__}; "
        "the `uv.lock` extra-files updater in release-please-config.json did not fire, and "
        "`uv lock --check` will fail in CI"
    )


def test_dunder_version_carries_release_please_annotation() -> None:
    init_py = REPO_ROOT / "src" / "keychain_cli" / "__init__.py"
    source = init_py.read_text(encoding="utf-8")

    annotated = [
        line
        for line in source.splitlines()
        if line.startswith("__version__") and RELEASE_PLEASE_ANNOTATION in line
    ]

    assert annotated, (
        f"the __version__ assignment must carry a `# {RELEASE_PLEASE_ANNOTATION}` comment, "
        "which is what the Release Please generic updater keys on"
    )


def test_uv_lock_updater_jsonpath_filters_on_the_tagged_value() -> None:
    """Pin the one non-obvious character in the `uv.lock` JSONPath.

    Release Please's TOML updater parses with a *format-preserving* parser that wraps every scalar
    as `{"start": ..., "end": ..., "value": ...}`. So the filter has to compare `@.name.value`, not
    the natural-looking `@.name` — which silently matches nothing and makes the updater a no-op.
    This test exists so the `.value` is not "corrected" away by someone reading it as a typo.
    """
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    extra_files = config["packages"]["."]["extra-files"]

    lock_updaters = [
        entry for entry in extra_files if isinstance(entry, dict) and entry.get("path") == "uv.lock"
    ]

    assert len(lock_updaters) == 1, "release-please-config.json must update uv.lock exactly once"

    updater = lock_updaters[0]
    assert updater["type"] == "toml"
    assert updater["jsonpath"] == f"$.package[?(@.name.value=='{PACKAGE_NAME}')].version"
