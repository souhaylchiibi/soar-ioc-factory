"""Phase 3 — normalization: valid, invalid and canonicalization cases."""
import pytest

from app.models.ioc import IocType
from app.services.normalization import (
    NormalizationError,
    compute_fingerprint,
    normalize,
)


class TestIp:
    def test_ipv4_canonical(self) -> None:
        assert normalize("  203.0.113.9 ", IocType.IP).value == "203.0.113.9"

    def test_ipv6_compressed_canonical(self) -> None:
        assert normalize("2001:0db8:0000:0000:0000:0000:0000:0001", IocType.IP).value == "2001:db8::1"

    def test_ip_with_port_stripped(self) -> None:
        assert normalize("198.51.100.7:4444", IocType.IP).value == "198.51.100.7"

    @pytest.mark.parametrize("bad", ["999.999.999.999", "not-an-ip", "1.2.3", "0.0.0.0", "224.0.0.1", ""])
    def test_invalid_or_rejected_ip(self, bad: str) -> None:
        with pytest.raises(NormalizationError):
            normalize(bad, IocType.IP)


class TestDomain:
    def test_lowercased_and_trailing_dot_removed(self) -> None:
        assert normalize("Evil.Example.COM.", IocType.DOMAIN).value == "evil.example.com"

    @pytest.mark.parametrize("bad", ["no tld", "http://ok.example/path", "-bad-.example",
                                     "spaces here.example", "single", "under_score.example", ""])
    def test_invalid_domain(self, bad: str) -> None:
        with pytest.raises(NormalizationError):
            normalize(bad, IocType.DOMAIN)

    def test_valid_idna_style_label(self) -> None:
        assert normalize("sub.domain-1.example", IocType.DOMAIN).value == "sub.domain-1.example"


class TestUrl:
    def test_scheme_host_lowercased_fragment_dropped(self) -> None:
        got = normalize("HTTP://Evil.Example/Path?a=1#frag", IocType.URL)
        assert got.value == "http://evil.example/Path?a=1"

    def test_default_https_port_removed(self) -> None:
        assert normalize("https://evil.example:443/x", IocType.URL).value == "https://evil.example/x"

    def test_non_default_port_kept(self) -> None:
        assert normalize("http://evil.example:8080/x", IocType.URL).value == "http://evil.example:8080/x"

    @pytest.mark.parametrize("bad", ["ftp://x.example/a", "javascript:alert(1)",
                                     "http:///nohost", "http://bad domain/"])
    def test_invalid_url(self, bad: str) -> None:
        with pytest.raises(NormalizationError):
            normalize(bad, IocType.URL)


class TestHash:
    @pytest.mark.parametrize("value,expected", [
        ("44d88612fea8a8f36de82e1278abb02f", IocType.HASH_MD5),
        ("A94A8FE5CCB19BA61C4C0873D391E987982FBBD3", IocType.HASH_SHA1),
        ("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", IocType.HASH_SHA256),
    ])
    def test_hashes_lowercased(self, value: str, expected: IocType) -> None:
        got = normalize(value, None)  # inferred
        assert got.type == expected
        assert got.value == value.lower()

    @pytest.mark.parametrize("bad", [
        "zzzz8612fea8a8f36de82e1278abb02f",  # not hex
        "44d88612fea8a8f36de82e1278abb02f00",  # wrong length
        "",
    ])
    def test_invalid_hash(self, bad: str) -> None:
        with pytest.raises(NormalizationError):
            normalize(bad, IocType.HASH_MD5)

    def test_declared_type_mismatch_rejected(self) -> None:
        # 40 hex chars declared as MD5 must fail, not be "fixed".
        with pytest.raises(NormalizationError):
            normalize("a94a8fe5ccb19ba61c4c0873d391e987982fbbd3", IocType.HASH_MD5)


class TestFingerprint:
    def test_stable_and_distinct_by_type(self) -> None:
        a = compute_fingerprint(IocType.DOMAIN, "evil.example")
        b = compute_fingerprint(IocType.URL, "evil.example")
        assert a == compute_fingerprint(IocType.DOMAIN, "evil.example")
        assert a != b
        assert len(a) == 64

    def test_canonicalization_prevents_duplicates(self) -> None:
        one = normalize("EVIL.EXAMPLE.", IocType.DOMAIN)
        two = normalize("evil.example", IocType.DOMAIN)
        assert one.fingerprint == two.fingerprint

    def test_type_inference_fails_without_hint_for_bare_host(self) -> None:
        # A bare hostname is ambiguous: it must NOT be silently accepted.
        with pytest.raises(NormalizationError):
            normalize("evil.example")
