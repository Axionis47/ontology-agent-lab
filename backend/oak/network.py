import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx2


async def resolve_public_url(url: str, allow_local: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
        raise ValueError("Use an MCP endpoint without credentials or a fragment in its URL.")
    if parsed.scheme != "https" and not (
        allow_local and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Use an HTTPS MCP endpoint.")
    loop = asyncio.get_running_loop()
    addresses = await loop.getaddrinfo(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    ips = list(dict.fromkeys(a[4][0] for a in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        if not (allow_local and ips and all(ipaddress.ip_address(ip).is_loopback for ip in ips)):
            raise ValueError("The MCP endpoint must resolve to a public internet address.")
    return ips[0]


class PublicTransport(httpx2.AsyncHTTPTransport):
    """Check and pin each destination, including OAuth discovery and redirects."""

    def __init__(self, allow_local=False):
        super().__init__()
        self.allow_local = allow_local

    async def handle_async_request(self, request):
        original = request.url
        address = await resolve_public_url(str(original), self.allow_local)
        request.extensions["sni_hostname"] = original.host
        request.url = original.copy_with(host=address)
        try:
            return await super().handle_async_request(request)
        finally:
            request.url = original
