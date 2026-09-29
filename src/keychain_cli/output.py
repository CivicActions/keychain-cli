"""Output helpers and the report types that are safe to print.

Results go to stdout, diagnostics to stderr (FR-042). Every type in this module holds names,
counts, and line numbers only; none can carry a secret value.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field


def out(line: str) -> None:
    """Write one result line to stdout."""
    sys.stdout.write(line + "\n")


def err(line: str) -> None:
    """Write one diagnostic line to stderr."""
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def emit_names(names: Sequence[str], json_mode: bool) -> None:  # noqa: FBT001 - CLI flag
    """Print names one per line, or as a compact JSON array when ``json_mode`` is set."""
    if json_mode:
        out(json.dumps(list(names), separators=(",", ":")))
        return
    for name in names:
        out(name)


@dataclass(frozen=True)
class MalformedLine:
    """A ``.env`` line that could not be parsed. Never carries the line's content."""

    line: int
    name: str | None = None


@dataclass(frozen=True)
class DuplicateKey:
    """A key defined more than once in a ``.env`` file; the last definition wins."""

    name: str
    first_line: int
    last_line: int


@dataclass
class StoreReport:
    """What a ``set``, ``import``, or ``init`` did, by variable name only."""

    stored: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    malformed: list[MalformedLine] = field(default_factory=list)
    duplicates: list[DuplicateKey] = field(default_factory=list)


def print_report(report: StoreReport) -> None:
    """Render a ``StoreReport`` to stderr, omitting empty categories."""
    for label, names in (
        ("stored", report.stored),
        ("overwritten", report.overwritten),
        ("skipped", report.skipped),
    ):
        if names:
            err(f"{label}: {', '.join(names)}")
    if report.malformed:
        err(
            f"malformed: {len(report.malformed)} line(s): "
            + ", ".join(_describe(m) for m in report.malformed)
        )
    for dup in report.duplicates:
        err(f"duplicate key {dup.name} (lines {dup.first_line}, {dup.last_line}): last value used")


def _describe(malformed: MalformedLine) -> str:
    if malformed.name is None:
        return f"line {malformed.line}"
    return f"line {malformed.line} ({malformed.name})"
