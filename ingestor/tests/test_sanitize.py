from __future__ import annotations

import pytest

from src.sanitize import sanitize, truncate


class TestTruncate:
    def test_none_passes_through(self) -> None:
        assert truncate(None, 10) is None

    def test_empty_unchanged(self) -> None:
        assert truncate("", 10) == ""

    def test_under_cap_unchanged(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_at_cap_unchanged(self) -> None:
        assert truncate("x" * 10, 10) == "x" * 10

    def test_over_cap_truncated(self) -> None:
        assert truncate("x" * 11, 10) == "x" * 10

    def test_zero_cap(self) -> None:
        assert truncate("hello", 0) == ""

    def test_no_escape_rewriting(self) -> None:
        # Unlike sanitize, truncate must NOT escape control chars - it's a
        # DB-shape guard, not a log-injection guard.
        assert truncate("a\nb", 10) == "a\nb"

    def test_multibyte_chars_counted_as_chars(self) -> None:
        # Postgres VARCHAR(N) and Python len() both count code points.
        s = "ä" * 5  # 5 chars, 10 bytes in utf-8
        assert truncate(s, 5) == s
        assert truncate(s, 3) == "ä" * 3

    def test_nul_byte_stripped(self) -> None:
        # Postgres TEXT/VARCHAR rejects U+0000 with DataError.
        assert truncate("a\x00b", 10) == "ab"

    def test_nul_only_string_returns_empty(self) -> None:
        assert truncate("\x00\x00", 10) == ""


class TestSanitize:
    def test_none_yields_empty(self) -> None:
        assert sanitize(None) == ""

    def test_control_chars_escaped(self) -> None:
        assert sanitize("a\nb") == "a\\x0ab"

    def test_truncation_marker(self) -> None:
        result = sanitize("x" * 10, max_len=5)
        assert result == "xxxxx..."

    @pytest.mark.parametrize("ch", ["\x00", "\x1f", "\x7f"])
    def test_c0_and_del_escaped(self, ch: str) -> None:
        assert f"\\x{ord(ch):02x}" in sanitize(ch)
