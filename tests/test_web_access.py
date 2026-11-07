"""
Tests for public web access support: optional password gate and
public-URL detection used for the subject link / QR code.
"""

import base64

import pytest
from starlette.requests import Request

from api.main import _basic_auth_ok, _public_base_url


def _basic(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def _request(headers: dict[str, str], scheme: str = "http") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "scheme": scheme,
        "path": "/api/server-info",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "server": ("127.0.0.1", 8000),
    }
    return Request(scope)


class TestBasicAuth:
    def test_correct_credentials(self):
        assert _basic_auth_ok(_basic("robotaste", "pw"), "robotaste", "pw")

    def test_password_with_colon(self):
        assert _basic_auth_ok(_basic("robotaste", "a:b"), "robotaste", "a:b")

    @pytest.mark.parametrize("header", [
        None,
        "",
        "Bearer abc",
        "Basic not-base64!!",
        "Basic " + base64.b64encode(b"no-colon").decode(),
        _basic("robotaste", "wrong"),
        _basic("someone", "pw"),
    ])
    def test_rejected(self, header):
        assert not _basic_auth_ok(header, "robotaste", "pw")


class TestPublicBaseUrl:
    @pytest.fixture(autouse=True)
    def _no_env(self, monkeypatch):
        monkeypatch.delenv("ROBOTASTE_PUBLIC_URL", raising=False)

    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("ROBOTASTE_PUBLIC_URL", "https://robotaste.example.ac.il/")
        assert _public_base_url(_request({"host": "localhost:8000"})) == "https://robotaste.example.ac.il"

    def test_tunnel_host_uses_forwarded_proto(self):
        req = _request({"host": "foo-bar.trycloudflare.com", "x-forwarded-proto": "https"})
        assert _public_base_url(req) == "https://foo-bar.trycloudflare.com"

    def test_forwarded_host_preferred(self):
        req = _request({"host": "127.0.0.1:8000", "x-forwarded-host": "robotaste.example.org",
                        "x-forwarded-proto": "https"})
        assert _public_base_url(req) == "https://robotaste.example.org"

    @pytest.mark.parametrize("host", [
        "localhost:8000", "127.0.0.1:8000", "192.168.1.20:8000", "100.64.0.5:8000",
        "[::1]:8000", "my-laptop.local:8000", "my-laptop:8000", "",
    ])
    def test_local_hosts_fall_back_to_lan(self, host):
        assert _public_base_url(_request({"host": host} if host else {})) is None
