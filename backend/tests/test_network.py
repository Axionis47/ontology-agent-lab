import socket

import httpx2
import pytest

from oak.network import PublicTransport, resolve_public_url
from oak.settings import Settings


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://example.com/mcp",
        "https://user:password@example.com/mcp",
        "https://127.0.0.1/mcp",
        "https://169.254.169.254/",
        "https://[::1]/mcp",
        "https://example.com/#fragment",
    ],
)
async def test_private_and_unsafe_destinations_are_blocked(url):
    with pytest.raises(ValueError):
        await resolve_public_url(url)


async def test_dns_rebinding_cannot_reuse_the_original_hostname(monkeypatch):
    import asyncio

    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    async def send(self, request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        return httpx2.Response(200)

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)
    request = httpx2.Request("GET", "https://example.com/mcp")
    async with PublicTransport() as transport:
        await transport.handle_async_request(request)
    assert request.url.host == "example.com"


def test_production_cannot_enable_local_secret_storage_or_private_mcps():
    with pytest.raises(RuntimeError):
        Settings(
            _env_file=None, api_key="x" * 32, environment="production", allow_local_mcp=True
        ).validate_runtime()


def test_render_callback_url_uses_the_assigned_host_and_allows_overrides(monkeypatch):
    monkeypatch.delenv("OAK_PUBLIC_API_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://oak-assigned.onrender.com")
    assert Settings(_env_file=None).public_api_url == "https://oak-assigned.onrender.com"
    monkeypatch.setenv("OAK_PUBLIC_API_URL", "https://api.oak.example")
    assert Settings(_env_file=None).public_api_url == "https://api.oak.example"
    config = Settings(_env_file=None, public_api_url="http://localhost:8047")
    assert config.public_api_url == "http://localhost:8047"
