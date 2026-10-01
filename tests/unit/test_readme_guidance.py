"""Tests for documentation placement and guidance isolation for `copy` (US7, T075)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

from pathlib import Path


def test_copy_not_in_primary_guidance() -> None:
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")

    # Split README by headings
    sections = {}
    current_heading = ""
    current_lines: list[str] = []
    for line in readme.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading:
        sections[current_heading] = "\n".join(current_lines)

    first_secret = sections.get("First secret in 60 seconds", "")
    assert "keychain-cli copy" not in first_secret

    commands = sections.get("Commands", "")
    assert "keychain-cli copy" not in commands

    # Check docs/
    docs_dir = root / "docs"
    if docs_dir.exists():
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text(encoding="utf-8")
            # daily use examples should not feature copy
            assert "keychain-cli copy" not in content or doc_file.name == "threat-model.md"
