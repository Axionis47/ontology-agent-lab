import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from oak.db import Store
from oak.discovery import Discoveries
from oak.discovery_schemas import (
    DiscoveryArtifact,
    DiscoveryDetail,
    DiscoveryEvent,
    DiscoveryOverview,
    DiscoveryResume,
    DiscoveryStart,
)
from oak.mcp_client import Connections
from oak.model_runtime import ModelChecks
from oak.network import resolve_public_url
from oak.schemas import (
    Agent,
    AgentInput,
    Connection,
    ConnectionInput,
    ModelCheckInput,
    ModelRuntime,
    Task,
    TaskInput,
    TokenInput,
    Tool,
    ToolSelection,
    User,
)
from oak.settings import Settings, get_settings
from oak.training import Training
from oak.training_schemas import (
    InferenceStart,
    TrainingCase,
    TrainingCaseInput,
    TrainingDetail,
    TrainingEpisode,
    TrainingEvent,
    TrainingOverview,
    TrainingStart,
)

USERS = [User(id="demo-alex", name="Alex Morgan"), User(id="demo-sam", name="Sam Rivera")]


def create_app(
    settings: Settings | None = None,
    model_client=None,
    discovery_model=None,
    training_model=None,
    prepare_environment=None,
):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        settings.validate_runtime()
        # SDK errors can contain provider responses. Oak reports a safe connection error instead.
        logging.getLogger("mcp.client.auth.oauth2").disabled = True
        logging.getLogger("httpx2").setLevel(logging.CRITICAL)
        store = Store(settings)
        await store.pool.open(wait=True)
        app.state.store = store
        app.state.connections = Connections(store)
        app.state.model_checks = ModelChecks(store, model_client)
        app.state.discoveries = Discoveries(store, app.state.connections, discovery_model)
        app.state.training = Training(
            store,
            app.state.connections,
            app.state.discoveries,
            training_model,
            prepare_environment,
        )
        await app.state.model_checks.recover_interrupted()
        await app.state.discoveries.recover_interrupted()
        await app.state.training.recover_interrupted()
        # The preview runs one Python worker. Interrupted OAuth flows must be restarted.
        await store.all(
            "UPDATE mcp_connections SET status='error',auth_url=NULL,"
            "error='Connection interrupted. Reconnect.' "
            "WHERE status IN ('connecting','auth_required') RETURNING id"
        )
        try:
            yield
        finally:
            await app.state.training.close()
            await app.state.discoveries.close()
            await app.state.model_checks.close()
            await app.state.connections.close()
            await store.pool.close()

    app = FastAPI(
        title="Oak API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Validation responses must not echo tokens or request bodies.
        return JSONResponse(
            status_code=422, content={"detail": "Invalid request. Check the form values."}
        )

    def store(request: Request):
        return request.app.state.store

    DB = Annotated[Store, Depends(store)]

    def guard(x_oak_key: Annotated[str | None, Header()] = None):
        if not x_oak_key or not secrets.compare_digest(x_oak_key, settings.api_key):
            raise HTTPException(401, "Private preview access required.")

    def identity(x_oak_user: Annotated[str, Header()] = "demo-alex") -> str:
        if x_oak_user not in {u.id for u in USERS}:
            raise HTTPException(401, "Select a valid demo user.")
        return x_oak_user

    Identity = Annotated[str, Depends(identity)]
    api = APIRouter(prefix="/api", dependencies=[Depends(guard)])

    @api.get("/model-runtime", response_model=ModelRuntime)
    async def model_runtime(request: Request, user: Identity):
        return await request.app.state.model_checks.snapshot()

    @api.post("/model-runtime/check", response_model=ModelRuntime, status_code=202)
    async def check_model(body: ModelCheckInput, request: Request, user: Identity):
        return await request.app.state.model_checks.start(body.request_id)

    discovery_base = "/tasks/{task_id}/agents/{agent_id}/discovery"

    async def discovery_access(db, user, task_id, agent_id, run_id=None):
        await db.require_task(task_id, user)
        await db.agent(task_id, agent_id)
        if run_id is not None and not await db.one(
            "SELECT id FROM discovery_runs WHERE id=%s AND task_id=%s AND agent_id=%s",
            (run_id, task_id, agent_id),
        ):
            raise HTTPException(404, "Discovery run not found.")

    @api.get(discovery_base, response_model=DiscoveryOverview)
    async def discovery_overview(
        task_id: UUID, agent_id: UUID, request: Request, db: DB, user: Identity, offset: int = 0
    ):
        await discovery_access(db, user, task_id, agent_id)
        return await request.app.state.discoveries.overview(task_id, agent_id, max(0, offset))

    @api.post(discovery_base + "/runs", response_model=DiscoveryDetail, status_code=202)
    async def start_discovery(
        task_id: UUID,
        agent_id: UUID,
        body: DiscoveryStart,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await discovery_access(db, user, task_id, agent_id)
        return await request.app.state.discoveries.start(task_id, agent_id, user, body)

    @api.get(discovery_base + "/runs/{run_id}", response_model=DiscoveryDetail)
    async def discovery_detail(
        task_id: UUID, agent_id: UUID, run_id: UUID, request: Request, db: DB, user: Identity
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.discoveries.detail(task_id, agent_id, run_id)

    @api.get(discovery_base + "/runs/{run_id}/events", response_model=list[DiscoveryEvent])
    async def discovery_events(
        task_id: UUID, agent_id: UUID, run_id: UUID, db: DB, user: Identity, after: int = 0
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        return await db.all(
            "SELECT * FROM discovery_events WHERE run_id=%s AND sequence>%s ORDER BY sequence "
            "LIMIT 200",
            (run_id, after),
        )

    @api.get(
        discovery_base + "/runs/{run_id}/artifacts/{artifact_id}", response_model=DiscoveryArtifact
    )
    async def discovery_artifact(
        task_id: UUID, agent_id: UUID, run_id: UUID, artifact_id: UUID, db: DB, user: Identity
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        artifact = await db.one(
            "SELECT * FROM discovery_artifacts WHERE id=%s AND run_id=%s", (artifact_id, run_id)
        )
        if not artifact:
            raise HTTPException(404, "Evidence not found.")
        return artifact

    @api.post(
        discovery_base + "/runs/{run_id}/resume", response_model=DiscoveryDetail, status_code=202
    )
    async def resume_discovery(
        task_id: UUID,
        agent_id: UUID,
        run_id: UUID,
        body: DiscoveryResume,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.discoveries.control(
            task_id, agent_id, run_id, "resume", user, body
        )

    @api.post(
        discovery_base + "/runs/{run_id}/pause", response_model=DiscoveryDetail, status_code=202
    )
    async def pause_discovery(
        task_id: UUID, agent_id: UUID, run_id: UUID, request: Request, db: DB, user: Identity
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.discoveries.control(task_id, agent_id, run_id, "pause", user)

    @api.post(
        discovery_base + "/runs/{run_id}/stop", response_model=DiscoveryDetail, status_code=202
    )
    async def stop_discovery(
        task_id: UUID, agent_id: UUID, run_id: UUID, request: Request, db: DB, user: Identity
    ):
        await discovery_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.discoveries.control(task_id, agent_id, run_id, "stop", user)

    training_base = "/tasks/{task_id}/agents/{agent_id}/training"

    async def training_access(db, user, task_id, agent_id, run_id=None):
        await db.require_task(task_id, user)
        await db.agent(task_id, agent_id)
        if run_id is not None and not await db.one(
            "SELECT id FROM training_runs WHERE id=%s AND task_id=%s AND agent_id=%s",
            (run_id, task_id, agent_id),
        ):
            raise HTTPException(404, "Training run not found.")

    @api.get(training_base, response_model=TrainingOverview)
    async def training_overview(
        task_id: UUID,
        agent_id: UUID,
        request: Request,
        db: DB,
        user: Identity,
        offset: int = 0,
    ):
        await training_access(db, user, task_id, agent_id)
        return await request.app.state.training.overview(task_id, agent_id, max(0, offset))

    @api.post(training_base + "/cases", response_model=TrainingCase, status_code=201)
    async def create_training_case(
        task_id: UUID,
        agent_id: UUID,
        body: TrainingCaseInput,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id)
        return await request.app.state.training.save_case(task_id, agent_id, body)

    @api.put(training_base + "/cases/{case_id}", response_model=TrainingCase)
    async def update_training_case(
        task_id: UUID,
        agent_id: UUID,
        case_id: UUID,
        body: TrainingCaseInput,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id)
        return await request.app.state.training.save_case(task_id, agent_id, body, case_id)

    @api.delete(training_base + "/cases/{case_id}", status_code=204)
    async def delete_training_case(
        task_id: UUID,
        agent_id: UUID,
        case_id: UUID,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id)
        await request.app.state.training.delete_case(agent_id, case_id)

    @api.post(training_base + "/runs", response_model=TrainingDetail, status_code=202)
    async def start_training(
        task_id: UUID,
        agent_id: UUID,
        body: TrainingStart,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id)
        return await request.app.state.training.start(task_id, agent_id, user, body)

    @api.post(training_base + "/inference", response_model=TrainingDetail, status_code=202)
    async def start_inference(
        task_id: UUID,
        agent_id: UUID,
        body: InferenceStart,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id)
        return await request.app.state.training.start(task_id, agent_id, user, body, inference=True)

    @api.get(training_base + "/runs/{run_id}", response_model=TrainingDetail)
    async def training_detail(
        task_id: UUID,
        agent_id: UUID,
        run_id: UUID,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.training.detail(run_id)

    @api.post(training_base + "/runs/{run_id}/stop", response_model=TrainingDetail, status_code=202)
    async def stop_training(
        task_id: UUID,
        agent_id: UUID,
        run_id: UUID,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id, run_id)
        return await request.app.state.training.stop(run_id)

    @api.get(training_base + "/runs/{run_id}/events", response_model=list[TrainingEvent])
    async def training_events(
        task_id: UUID,
        agent_id: UUID,
        run_id: UUID,
        db: DB,
        user: Identity,
        after: int = 0,
    ):
        await training_access(db, user, task_id, agent_id, run_id)
        return await db.all(
            "SELECT * FROM training_events WHERE run_id=%s AND sequence>%s "
            "ORDER BY sequence LIMIT 200",
            (run_id, max(0, after)),
        )

    @api.get(training_base + "/runs/{run_id}/episodes/{episode_id}", response_model=TrainingEpisode)
    async def training_episode(
        task_id: UUID,
        agent_id: UUID,
        run_id: UUID,
        episode_id: UUID,
        db: DB,
        user: Identity,
    ):
        await training_access(db, user, task_id, agent_id, run_id)
        episode = await db.one(
            "SELECT * FROM training_episodes WHERE id=%s AND run_id=%s",
            (episode_id, run_id),
        )
        if not episode:
            raise HTTPException(404, "Episode not found.")
        return episode

    @app.get("/health")
    async def health(db: DB) -> dict[str, str]:
        await db.one("SELECT 1")
        return {"status": "ok", "release": settings.release_sha}

    @app.get("/oauth/client-metadata.json")
    async def oauth_metadata() -> dict:
        return {
            "client_id": f"{settings.public_api_url}/oauth/client-metadata.json",
            "client_name": "Oak",
            "client_uri": settings.frontend_url,
            "redirect_uris": [f"{settings.public_api_url}/oauth/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }

    @app.get("/oauth/callback", response_class=HTMLResponse)
    async def callback(
        request: Request,
        state: str,
        code: str | None = None,
        iss: str | None = None,
        error: str | None = None,
    ):
        success = await request.app.state.connections.finish_oauth(state, code, iss, error)
        text = (
            "Authorization received. Return to Oak to see the connection status."
            if success
            else "Authorization cancelled. Return to Oak and reconnect when ready."
        )
        return HTMLResponse(
            "<!doctype html><html><title>Oak authorization</title>"
            f"<body><p>{text}</p></body></html>",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
            },
        )

    @api.get("/users", response_model=list[User])
    def users():
        return USERS

    @api.get("/tasks", response_model=list[Task])
    async def tasks(db: DB, user: Identity):
        return await db.all(
            "SELECT t.* FROM tasks t JOIN task_members m ON t.id=m.task_id "
            "WHERE m.user_id=%s ORDER BY t.created_at",
            (user,),
        )

    @api.post("/tasks", response_model=Task, status_code=201)
    async def create_task(body: TaskInput, db: DB, user: Identity):
        task_id = uuid4()
        async with db.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "INSERT INTO tasks(id,name,objective,scope) VALUES (%s,%s,%s,%s) RETURNING *",
                    (
                        task_id,
                        body.name,
                        body.objective,
                        Jsonb(body.scope.model_dump()) if body.scope is not None else None,
                    ),
                )
            ).fetchone()
            await conn.execute("INSERT INTO task_members VALUES (%s,%s)", (task_id, user))
        return row

    @api.get("/tasks/{task_id}", response_model=Task)
    async def get_task(task_id: UUID, db: DB, user: Identity):
        return await db.require_task(task_id, user)

    @api.patch(
        "/tasks/{task_id}",
        response_model=Task,
        responses={409: {"description": "Task scope is read-only after creation."}},
    )
    async def update_task(task_id: UUID, body: TaskInput, db: DB, user: Identity):
        task = await db.require_task(task_id, user)
        scope = body.scope.model_dump() if body.scope is not None else None
        if body.objective != task["objective"] or (
            "scope" in body.model_fields_set and scope != task["scope"]
        ):
            raise HTTPException(409, "Task scope is read-only after creation. Create a new task.")
        return await db.one(
            "UPDATE tasks SET name=%s WHERE id=%s RETURNING *",
            (body.name, task_id),
        )

    @api.get("/tasks/{task_id}/agents", response_model=list[Agent])
    async def agents(task_id: UUID, db: DB, user: Identity):
        await db.require_task(task_id, user)
        rows = await db.all(
            "SELECT id FROM agents WHERE task_id=%s ORDER BY created_at", (task_id,)
        )
        return [await db.agent(task_id, row["id"]) for row in rows]

    @api.post("/tasks/{task_id}/agents", response_model=Agent, status_code=201)
    async def create_agent(task_id: UUID, body: AgentInput, db: DB, user: Identity):
        await db.require_task(task_id, user)
        return await db.save_agent(task_id, body)

    @api.patch("/tasks/{task_id}/agents/{agent_id}", response_model=Agent)
    async def update_agent(task_id: UUID, agent_id: UUID, body: AgentInput, db: DB, user: Identity):
        await db.require_task(task_id, user)
        return await db.save_agent(task_id, body, agent_id)

    @api.put("/tasks/{task_id}/agents/{agent_id}/tools", response_model=Agent)
    async def select_tools(
        task_id: UUID, agent_id: UUID, body: ToolSelection, db: DB, user: Identity
    ):
        await db.require_task(task_id, user)
        await db.agent(task_id, agent_id)
        await db.select_tools(task_id, agent_id, body.tool_ids)
        return await db.agent(task_id, agent_id)

    @api.get("/tasks/{task_id}/connections", response_model=list[Connection])
    async def connections(task_id: UUID, db: DB, user: Identity):
        await db.require_task(task_id, user)
        return await db.all(
            "SELECT * FROM mcp_connections WHERE task_id=%s ORDER BY created_at", (task_id,)
        )

    @api.post("/tasks/{task_id}/connections", response_model=Connection, status_code=201)
    async def create_connection(task_id: UUID, body: ConnectionInput, db: DB, user: Identity):
        await db.require_task(task_id, user)
        try:
            if urlsplit(body.url).query:
                raise ValueError("Use the authentication field for credentials.")
            await resolve_public_url(body.url, settings.allow_local_mcp)
        except (ValueError, OSError):
            raise HTTPException(422, "Use a valid public HTTPS MCP endpoint.") from None
        if body.auth_mode == "token" and not body.token:
            raise HTTPException(422, "Enter a bearer token for this connection.")
        connection_id = uuid4()
        try:
            row = await db.one(
                "INSERT INTO mcp_connections(id,task_id,name,url,auth_mode) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (connection_id, task_id, body.name, body.url, body.auth_mode),
            )
        except UniqueViolation:
            raise HTTPException(409, "This MCP endpoint is already added to the task.") from None
        if body.token and body.auth_mode == "token":
            await db.write_secret(connection_id, {"token": body.token})
        return row

    @api.post("/tasks/{task_id}/connections/{connection_id}/refresh", response_model=Connection)
    async def refresh(task_id: UUID, connection_id: UUID, request: Request, db: DB, user: Identity):
        await db.require_task(task_id, user)
        connection = await db.connection(task_id, connection_id)
        return await request.app.state.connections.start(connection)

    @api.put("/tasks/{task_id}/connections/{connection_id}/token", response_model=Connection)
    async def update_token(
        task_id: UUID,
        connection_id: UUID,
        body: TokenInput,
        request: Request,
        db: DB,
        user: Identity,
    ):
        await db.require_task(task_id, user)
        connection = await db.connection(task_id, connection_id)
        if connection["auth_mode"] != "token":
            raise HTTPException(422, "This connection does not use a bearer token.")
        if str(connection_id) in request.app.state.connections.jobs:
            raise HTTPException(409, "Wait for the current connection attempt to finish.")
        await db.write_secret(connection_id, {"token": body.token})
        return connection

    @api.delete("/tasks/{task_id}/connections/{connection_id}", status_code=204)
    async def remove_connection(
        task_id: UUID, connection_id: UUID, request: Request, db: DB, user: Identity
    ):
        await db.require_task(task_id, user)
        connection = await db.connection(task_id, connection_id)
        if str(connection_id) in request.app.state.connections.jobs:
            raise HTTPException(409, "Wait for the current connection attempt to finish.")
        async with db.pool.connection() as conn:
            await conn.execute("DELETE FROM mcp_connections WHERE id=%s", (connection_id,))
            if connection["secret_id"]:
                table = (
                    "vault.secrets" if settings.secret_backend == "vault" else "oak_local_secrets"
                )
                await conn.execute(f"DELETE FROM {table} WHERE id=%s", (connection["secret_id"],))

    @api.get("/tasks/{task_id}/tools", response_model=list[Tool])
    async def tools(task_id: UUID, db: DB, user: Identity):
        await db.require_task(task_id, user)
        return await db.all(
            "SELECT t.*,c.name AS connection_name FROM tools t JOIN mcp_connections c "
            "ON c.id=t.connection_id WHERE t.task_id=%s ORDER BY c.created_at,t.name",
            (task_id,),
        )

    app.include_router(api)
    return app


app = create_app()
