import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import httpx2
from fastapi import HTTPException
from mcp import Client
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

from oak.db import Store
from oak.network import PublicTransport, resolve_public_url

logger = logging.getLogger(__name__)


class OAuthStorage:
    def __init__(self, store, connection_id):
        self.store, self.connection_id = store, connection_id

    async def get_tokens(self):
        stored = await self.store.read_secret(self.connection_id)
        data = stored.get("tokens")
        if not data:
            return None
        token = OAuthToken.model_validate(data)
        if stored.get("expires_at") is not None:
            token.expires_in = max(0, int(stored["expires_at"] - time.time()))
        return token

    async def set_tokens(self, tokens):
        data = await self.store.read_secret(self.connection_id)
        data["tokens"] = tokens.model_dump(mode="json")
        data["expires_at"] = (
            time.time() + tokens.expires_in if tokens.expires_in is not None else None
        )
        await self.store.write_secret(self.connection_id, data)

    async def get_client_info(self):
        data = (await self.store.read_secret(self.connection_id)).get("client")
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def set_client_info(self, client_info):
        data = await self.store.read_secret(self.connection_id)
        data["client"] = client_info.model_dump(mode="json")
        await self.store.write_secret(self.connection_id, data)


@dataclass
class Discovery:
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    callback: asyncio.Future | None = None
    state: str | None = None
    task: asyncio.Task | None = None


class Connections:
    def __init__(self, store: Store):
        self.store = store
        self.settings = store.settings
        self.jobs: dict[str, Discovery] = {}

    async def start(self, connection):
        key = str(connection["id"])
        job = self.jobs.get(key)
        if job is None:
            if len(self.jobs) >= 8:
                raise HTTPException(429, "Other MCP connections are busy. Try again shortly.")
            job = Discovery()
            self.jobs[key] = job
            job.task = asyncio.create_task(self._discover(connection, job))
        try:
            await asyncio.wait_for(job.ready.wait(), self.settings.discovery_timeout + 2)
        except TimeoutError:
            pass
        return await self.store.connection(connection["task_id"], connection["id"])

    async def _discover(self, connection, job):
        key = str(connection["id"])
        try:
            await self.store.status(connection["id"], "connecting")
            timeout = (
                self.settings.oauth_timeout
                if connection["auth_mode"] == "oauth"
                else self.settings.discovery_timeout
            )
            async with asyncio.timeout(timeout):
                await self._load(connection, job)
        except asyncio.CancelledError:
            await self.store.status(connection["id"], "error", "Connection interrupted. Reconnect.")
            raise
        except Exception as exc:
            # Do not log endpoint responses, URLs, OAuth codes, or tokens.
            logger.warning("MCP discovery failed: %s", type(exc).__name__)
            await self.store.status(
                connection["id"],
                "error",
                "Could not discover tools. Check the endpoint and credentials, then reconnect.",
            )
        finally:
            job.ready.set()
            self.jobs.pop(key, None)

    @asynccontextmanager
    async def session(self, connection, job=None):
        headers = {}
        auth = None
        if connection["auth_mode"] == "token":
            token = (await self.store.read_secret(connection["id"])).get("token")
            if not token:
                raise ValueError("Token required")
            headers["Authorization"] = f"Bearer {token}"
        if connection["auth_mode"] == "oauth":
            if job:
                job.callback = asyncio.get_running_loop().create_future()

            async def redirect(url):
                if job is None:
                    raise ValueError("Reconnect this MCP server before discovery.")
                await resolve_public_url(url, self.settings.allow_local_mcp)
                job.state = parse_qs(urlsplit(url).query).get("state", [None])[0]
                if not job.state:
                    raise ValueError("OAuth state required")
                await self.store.status(connection["id"], "auth_required", auth_url=url)
                job.ready.set()

            async def callback():
                if job is None:
                    raise ValueError("Reconnect this MCP server before discovery.")
                return await job.callback

            auth = OAuthClientProvider(
                server_url=connection["url"],
                client_metadata=OAuthClientMetadata(
                    client_name="Oak",
                    redirect_uris=[f"{self.settings.public_api_url}/oauth/callback"],
                    token_endpoint_auth_method="none",
                    grant_types=["authorization_code", "refresh_token"],
                    response_types=["code"],
                ),
                storage=OAuthStorage(self.store, connection["id"]),
                redirect_handler=redirect,
                callback_handler=callback,
                client_metadata_url=(
                    f"{self.settings.public_api_url}/oauth/client-metadata.json"
                    if self.settings.public_api_url.startswith("https://")
                    else None
                ),
            )
        async with httpx2.AsyncClient(
            transport=PublicTransport(self.settings.allow_local_mcp),
            headers=headers,
            auth=auth,
            timeout=httpx2.Timeout(20, read=60),
            follow_redirects=True,
        ) as http:
            async with Client(
                streamable_http_client(connection["url"], http_client=http)
            ) as client:
                yield client

    async def catalog(self, client):
        tools, cursor, seen = [], None, set()
        for _ in range(32):
            result = await client.list_tools(cursor=cursor)
            tools.extend(result.tools)
            if len(tools) > 2000:
                raise ValueError("MCP tool catalog exceeds the supported limit")
            cursor = result.next_cursor
            if not cursor:
                return tools
            if cursor in seen:
                raise ValueError("MCP returned a repeated cursor")
            seen.add(cursor)
        raise ValueError("MCP catalog page limit reached")

    async def _load(self, connection, job):
        async with self.session(connection, job) as client:
            await self.store.save_catalog(connection, await self.catalog(client))

    async def finish_oauth(self, state, code, issuer=None, error=None):
        for job in list(self.jobs.values()):
            if job.state == state and job.callback and not job.callback.done():
                job.state = None
                if error or not code:
                    job.callback.set_exception(ValueError("Authorization was cancelled"))
                    return False
                job.callback.set_result(AuthorizationCodeResult(code=code, state=state, iss=issuer))
                return True
        raise HTTPException(
            400, "This authorization expired or was already used. Reconnect in Oak."
        )

    async def close(self):
        jobs = [j.task for j in self.jobs.values() if j.task]
        for task in jobs:
            task.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
