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
        # Storage guard (strips nul/control), not log-injection guard (doesn't escape).
        assert truncate("a\tb", 10) == "a\tb"

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

    def test_tab_survives(self) -> None:
        # Tab is the only control char attackers may legitimately type.
        assert truncate("a\tb", 10) == "a\tb"

    def test_crlf_stripped(self) -> None:
        # CR/LF are log-forgery vectors with no place in a stored field.
        assert truncate("a\r\nb", 10) == "ab"

    def test_other_c0_and_del_stripped(self) -> None:
        assert truncate("a\x01\x1f\x7fb", 10) == "ab"

    def test_strip_before_cap_counts_stored_chars(self) -> None:
        # Length cap counts stored chars, not input (stripped chars don't count).
        assert truncate("a\x00\x00\x00b", 2) == "ab"

    def test_ansi_color_sequence_fully_stripped(self) -> None:
        # Stripping only the ESC byte would leave "[31m" as literal text,
        # whose trailing "m" sits directly in front of the IP with no
        # separator - defeating redact_ips's alnum-adjacency guard downstream.
        assert truncate("\x1b[31mssh 192.168.1.1\x1b[0m", 500) == "ssh 192.168.1.1"

    def test_ansi_cursor_and_dec_private_mode_sequences_stripped(self) -> None:
        assert truncate("a\x1b[2K\x1b[?25lb", 10) == "ab"

    def test_incomplete_csi_sequence_still_loses_its_introducer(self) -> None:
        # No final byte, so the CSI alternative doesn't match - but the
        # generic simple-escape alternative still consumes ESC + '[',
        # leaving only the harmless, non-IP digits behind.
        assert truncate("a\x1b[31", 10) == "a31"

    def test_osc_window_title_sequence_fully_stripped(self) -> None:
        # BEL-terminated OSC (window title) leaves no residue that could
        # sit in front of an IP and defeat redact_ips's adjacency guard.
        assert truncate("\x1b]0;pwn\x07192.168.1.1", 500) == "192.168.1.1"

    def test_osc_string_terminator_form_fully_stripped(self) -> None:
        # ST-terminated OSC (ESC \\ instead of BEL).
        assert truncate("\x1b]0;pwn\x1b\\192.168.1.1", 500) == "192.168.1.1"

    def test_dcs_sequence_fully_stripped(self) -> None:
        assert truncate("\x1bPsome-dcs-body\x1b\\192.168.1.1", 500) == "192.168.1.1"

    def test_simple_two_byte_escape_stripped(self) -> None:
        # ESC 'M' (reverse index) has no '[' - the generic simple-escape
        # alternative, not the CSI one.
        assert truncate("\x1bM192.168.1.1", 500) == "192.168.1.1"


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
