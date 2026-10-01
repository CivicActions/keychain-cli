"""Unit tests for `.env` file parsing (US3, T041)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from pathlib import Path

from keychain_cli.envfile import parse_env_file
from keychain_cli.output import DuplicateKey, MalformedLine


def test_envfile_comments_blanks_and_export(tmp_path: Path) -> None:
    content = "# Top comment\n\n   # Indented comment\nALPHA=1\nexport BETA=2\nexport   GAMMA=3\n"
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    assert len(res.entries) == 3
    assert [e.name for e in res.entries] == ["ALPHA", "BETA", "GAMMA"]
    assert [e.value.data for e in res.entries] == [b"1", b"2", b"3"]
    assert res.malformed == []
    assert res.duplicates == []


def test_envfile_single_and_double_quotes_and_escapes(tmp_path: Path) -> None:
    content = (
        'DOUBLE="hello\\nworld\\t\\"quote\\\\\\n"\n'
        "SINGLE='hello\\nworld\\t\"quote\"'\n"
        "SINGLE_HASH='not # a comment'\n"
    )
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    assert len(res.entries) == 3
    assert res.entries[0].name == "DOUBLE"
    assert res.entries[0].value.data == b'hello\nworld\t"quote\\\n'
    assert res.entries[1].name == "SINGLE"
    assert res.entries[1].value.data == b'hello\\nworld\\t"quote"'
    assert res.entries[2].name == "SINGLE_HASH"
    assert res.entries[2].value.data == b"not # a comment"


def test_envfile_unquoted_trailing_comment_and_spaces(tmp_path: Path) -> None:
    content = (
        "PLAIN=value # trailing comment\nEQUALS=foo=bar=baz # comment\nWITH_SPACES = spaced_val \n"
    )
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    entry_dict = {e.name: e.value.data for e in res.entries}
    assert len(entry_dict) == 3
    assert entry_dict["PLAIN"] == b"value"
    assert entry_dict["EQUALS"] == b"foo=bar=baz"
    assert entry_dict["WITH_SPACES"] == b"spaced_val"


def test_envfile_unterminated_quotes_are_malformed(tmp_path: Path) -> None:
    content = "UNTERM_DOUBLE=\"unterminated double\nUNTERM_SINGLE='unterminated single\n"
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    assert len(res.entries) == 0
    assert len(res.malformed) == 2
    assert res.malformed[0] == MalformedLine(line=1, name="UNTERM_DOUBLE")
    assert res.malformed[1] == MalformedLine(line=2, name="UNTERM_SINGLE")


def test_envfile_invalid_key_and_lines_without_equals(tmp_path: Path) -> None:
    content = "just a line with no equals\n123BAD=val\nBAD-KEY=val\n"
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    assert len(res.entries) == 0
    assert len(res.malformed) == 3
    assert res.malformed[0] == MalformedLine(line=1, name=None)
    assert res.malformed[1] == MalformedLine(line=2, name=None)
    assert res.malformed[2] == MalformedLine(line=3, name=None)


def test_envfile_duplicate_keys_last_wins_and_recorded(tmp_path: Path) -> None:
    content = "KEY=first\nOTHER=x\nKEY=second\n"
    env_file = tmp_path / "test.env"
    env_file.write_text(content)

    res = parse_env_file(env_file)
    entry_dict = {e.name: e.value.data for e in res.entries}
    assert entry_dict == {"KEY": b"second", "OTHER": b"x"}
    assert res.duplicates == [DuplicateKey(name="KEY", first_line=1, last_line=3)]


def test_envfile_crlf_and_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.env"
    empty_file.write_bytes(b"")
    res_empty = parse_env_file(empty_file)
    assert res_empty.entries == []
    assert res_empty.malformed == []
    assert res_empty.duplicates == []

    crlf_file = tmp_path / "crlf.env"
    crlf_file.write_bytes(b"A=1\r\nB=2\r\n")
    res_crlf = parse_env_file(crlf_file)
    assert [e.name for e in res_crlf.entries] == ["A", "B"]
    assert [e.value.data for e in res_crlf.entries] == [b"1", b"2"]


def test_malformed_line_never_carries_content() -> None:
    # Check that MalformedLine class has only line and name attributes
    import dataclasses

    fields = {f.name for f in dataclasses.fields(MalformedLine)}
    assert fields == {"line", "name"}
