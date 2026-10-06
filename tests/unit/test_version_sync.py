"""Guard that every declared version string stays in lockstep.

Release Please rewrites the version in `pyproject.toml` (via its `python` release type), in
`src/keychain_cli/__init__.py` (via an `extra-files` generic updater keyed on the
`x-release-please-version` annotation), and in `.release-please-manifest.json`. Those are
independent mechanisms, so this module fails loudly if the annotation is ever dropped, a path is
renamed, or someone edits one of them by hand.
"""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from keychain_cli import __version__

RELEASE_PLEASE_ANNOTATION = "x-release-please-version"
REPO_ROOT = Path(__file__).parents[2]


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
