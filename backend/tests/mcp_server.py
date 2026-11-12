"""Controlled MCP servers for API and browser acceptance tests."""

import base64
import hashlib
import os
import secrets
from contextlib import AsyncExitStack, asynccontextmanager
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from mcp.server import MCPServer

BASE = f"http://127.0.0.1:{os.environ.get('OAK_FIXTURE_PORT', '9147')}"
servers = {
    name: MCPServer(name)
    for name in ("alpha", "beta", "secure", "oauth", "discovery", "acquisition")
}
calls = 0
authorizations = 0
codes = {}
clients = {}
catalog_changed = False
notes = [{"id": "note-1", "title": "Initial note"}]
probe_calls = []
probe_mode = "success"
acquisition_calls = []


@servers["acquisition"].tool()
def customer_records(
    guests: int,
    start_date: str,
    end_date: str,
    customer: str,
    fields: list[str],
    cursor: str | None = None,
    page_size: int = 10,
) -> dict:
    """Filter records by customer and requested dates and guests. Select fields by name.
    Follow next until null. complete=true on the final page establishes full scope coverage.
    """
    acquisition_calls.append(
        {
            "guests": guests,
            "start_date": start_date,
            "end_date": end_date,
            "customer": customer,
            "fields": fields,
            "cursor": cursor,
            "page_size": page_size,
        }
    )
    rows = (
        [
            {"id": "a", "capacity": 4, "total_cost": 12000},
            {"id": "b", "capacity": 4, "total_cost": 18000},
        ]
        if customer == "C17"
        else []
    )
    index = int(cursor or "0")
    selected = rows[index : index + page_size]
    next_cursor = str(index + page_size) if index + page_size < len(rows) else None
    return {
        "items": [{key: row[key] for key in fields} for row in selected],
        "next": next_cursor,
        "complete": next_cursor is None,
    }


@servers["discovery"].tool()
def list_notes() -> dict:
    """Read the current test notes without changing them."""
    probe_calls.append("list_notes")
    return {"items": notes}


@servers["discovery"].tool()
async def create_note(title: str) -> dict:
    """Create a note in the supplied test workspace."""
    import asyncio

    probe_calls.append("create_note")
    note = {"id": f"note-{len(notes) + 1}", "title": title}
    notes.append(note)
    if probe_mode == "timeout":
        await asyncio.sleep(2)
    return note


def search(query: str) -> str:
    """Search the research library for source documents."""
    global calls
    calls += 1
    return query


def inspect_document(document_id: str) -> str:
    """Read the metadata of a source document."""
    global calls
    calls += 1
    return document_id


def summarize(document_id: str) -> str:
    """Summarize a source document."""
    global calls
    calls += 1
    return document_id


for server in servers.values():
    server.tool()(search)
servers["alpha"].tool()(inspect_document)


@asynccontextmanager
async def lifespan(app):
    async with AsyncExitStack() as stack:
        for server in servers.values():
            await stack.enter_async_context(server.session_manager.run())
        yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def auth(request: Request, call_next):
    if request.url.path.startswith("/secure/"):
        if request.headers.get("authorization") != "Bearer fixture-token":
            return JSONResponse({"error": "invalid_token"}, status_code=401)
    if request.url.path.startswith("/oauth/"):
        if request.headers.get("authorization") != "Bearer fixture-oauth-token":
            return JSONResponse(
                {"error": "invalid_token"},
                status_code=401,
                headers={
                    "WWW-Authenticate": f'Bearer resource_metadata="{BASE}/oauth-resource"',
                },
            )
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "calls": calls, "authorizations": authorizations}


@app.get("/probe-state")
def probe_state():
    return {"calls": probe_calls, "notes": notes}


@app.get("/acquisition-state")
def acquisition_state():
    return {"calls": acquisition_calls}


@app.post("/probe-reset")
def probe_reset(mode: str = "success"):
    global probe_mode
    notes[:] = [{"id": "note-1", "title": "Initial note"}]
    probe_calls.clear()
    probe_mode = mode
    return {"mode": mode}


@app.post("/catalog/{mode}")
def change_catalog(mode: str):
    global catalog_changed
    if mode == "changed" and not catalog_changed:
        servers["alpha"].remove_tool("inspect_document")
        servers["alpha"].tool()(summarize)
        catalog_changed = True
    elif mode == "original" and catalog_changed:
        servers["alpha"].remove_tool("summarize")
        servers["alpha"].tool()(inspect_document)
        catalog_changed = False
    return {"changed": catalog_changed}


@app.get("/oauth-resource")
def resource_metadata():
    return {
        "resource": f"{BASE}/oauth/mcp",
        "authorization_servers": [BASE],
        "scopes_supported": ["tools:read"],
        "bearer_methods_supported": ["header"],
    }


@app.get("/.well-known/oauth-authorization-server")
def oauth_metadata():
    return {
        "issuer": BASE,
        "authorization_endpoint": f"{BASE}/authorize",
        "token_endpoint": f"{BASE}/token",
        "registration_endpoint": f"{BASE}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["tools:read"],
    }


@app.post("/register")
async def register(request: Request):
    data = await request.json()
    client_id = secrets.token_urlsafe(16)
    clients[client_id] = data
    return {**data, "client_id": client_id, "client_id_issued_at": 1}


@app.get("/authorize")
def authorize(request: Request):
    global authorizations
    query = dict(request.query_params)
    if query.get("redirect_uri") not in clients.get(query.get("client_id"), {}).get(
        "redirect_uris", []
    ):
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    authorizations += 1
    code = secrets.token_urlsafe(16)
    codes[code] = query
    return RedirectResponse(
        query["redirect_uri"]
        + "?"
        + urlencode({"code": code, "state": query["state"], "iss": BASE})
    )


@app.post("/token")
async def token(request: Request):
    data = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
    if data.get("grant_type") == "authorization_code":
        original = codes.pop(data.get("code"), None)
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(data.get("code_verifier", "").encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        if (
            not original
            or challenge != original.get("code_challenge")
            or data.get("redirect_uri") != original.get("redirect_uri")
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
    elif data.get("refresh_token") != "fixture-refresh-token":
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    return {
        "access_token": "fixture-oauth-token",
        "refresh_token": "fixture-refresh-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "tools:read",
    }


for name, server in servers.items():
    app.mount(f"/{name}", server.streamable_http_app(json_response=True, stateless_http=True))
