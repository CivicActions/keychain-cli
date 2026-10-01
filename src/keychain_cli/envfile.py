"""Parser for `.env` files per research R-008 (US3, T045)."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from keychain_cli.errors import InvalidInputError, NotFoundError
from keychain_cli.names import VARIABLE_PATTERN
from keychain_cli.output import DuplicateKey, MalformedLine
from keychain_cli.secret import SecretValue


@dataclass(frozen=True)
class EnvFileEntry:
    """One successfully parsed variable assignment."""

    line: int
    name: str
    value: SecretValue


@dataclass
class EnvFileParse:
    """The complete result of parsing a `.env` file."""

    entries: list[EnvFileEntry] = field(default_factory=list)
    malformed: list[MalformedLine] = field(default_factory=list)
    duplicates: list[DuplicateKey] = field(default_factory=list)


def _parse_double_quoted(s: str) -> str:
    """Parse and unescape a double-quoted string body. Raises ValueError if unterminated."""
    result: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            # Closing quote found! Remainder must be whitespace or comment.
            rem = s[i + 1 :].strip()
            if rem and not rem.startswith("#"):
                raise ValueError("unexpected content after closing quote")
            return "".join(result)
        if c == "\\":
            if i + 1 >= n:
                raise ValueError("unterminated escape")
            nxt = s[i + 1]
            if nxt == "n":
                result.append("\n")
            elif nxt == "t":
                result.append("\t")
            elif nxt == '"':
                result.append('"')
            elif nxt == "\\":
                result.append("\\")
            else:
                result.append("\\" + nxt)
            i += 2
            continue
        result.append(c)
        i += 1
    raise ValueError("unterminated double quote")


def _parse_single_quoted(s: str) -> str:
    """Parse a single-quoted string body. Raises ValueError if unterminated."""
    close_idx = s.find("'")
    if close_idx == -1:
        raise ValueError("unterminated single quote")
    rem = s[close_idx + 1 :].strip()
    if rem and not rem.startswith("#"):
        raise ValueError("unexpected content after closing quote")
    return s[:close_idx]


def _parse_unquoted(s: str) -> str:
    """Strip trailing ` #` comments and surrounding whitespace from unquoted value."""
    # Trailing comment must be preceded by space
    # Look for ' #'
    comment_idx = s.find(" #")
    if comment_idx != -1:
        s = s[:comment_idx]
    return s.strip()


def parse_env_file(path: Path) -> EnvFileParse:
    """Parse a `.env` file at the given path."""
    if not path.exists():
        raise NotFoundError(f"file '{path}' not found", "Check the path and retry")
    if not path.is_file():
        raise InvalidInputError(
            f"'{path}' is not a regular file",
            "Provide a path to a regular file",
        )

    try:
        raw_bytes = path.read_bytes()
    except (PermissionError, OSError) as err:
        raise InvalidInputError(
            f"cannot read '{path}': {err.strerror}",
            "Make sure the file exists and is readable",
        ) from None

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as err:
        # Determine the line where decode failed
        line_no = raw_bytes[: err.start].count(b"\n") + 1
        raise InvalidInputError(
            f"file '{path}' contains invalid UTF-8 at line {line_no}",
            "Ensure the file is encoded in valid UTF-8",
        ) from None

    lines = text.splitlines()
    entries_by_name: dict[str, EnvFileEntry] = {}
    first_lines: dict[str, int] = {}
    duplicates_list: list[DuplicateKey] = []
    malformed: list[MalformedLine] = []

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            malformed.append(MalformedLine(line=line_no, name=None))
            continue

        key_part, _, val_part = line.partition("=")
        key = key_part.strip()

        if not VARIABLE_PATTERN.match(key):
            malformed.append(MalformedLine(line=line_no, name=None))
            continue

        val_part = val_part.lstrip()
        try:
            if val_part.startswith('"'):
                parsed_val = _parse_double_quoted(val_part[1:])
            elif val_part.startswith("'"):
                parsed_val = _parse_single_quoted(val_part[1:])
            else:
                parsed_val = _parse_unquoted(val_part)
        except ValueError:
            malformed.append(MalformedLine(line=line_no, name=key))
            continue

        entry = EnvFileEntry(
            line=line_no,
            name=key,
            value=SecretValue.from_text(parsed_val),
        )

        if key in entries_by_name:
            dup = DuplicateKey(
                name=key,
                first_line=first_lines[key],
                last_line=line_no,
            )
            duplicates_list.append(dup)
        else:
            first_lines[key] = line_no

        entries_by_name[key] = entry

    return EnvFileParse(
        entries=sorted(entries_by_name.values(), key=lambda e: e.name),
        malformed=malformed,
        duplicates=duplicates_list,
    )
