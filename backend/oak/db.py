import json
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from oak.settings import Settings


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool = AsyncConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def all(self, sql: str, args=()):
        async with self.pool.connection() as db:
            return await (await db.execute(sql, args)).fetchall()

    async def one(self, sql: str, args=()):
        rows = await self.all(sql, args)
        return rows[0] if rows else None

    async def require_task(self, task_id: UUID, user_id: str):
        task = await self.one(
            "SELECT t.* FROM tasks t JOIN task_members m ON t.id=m.task_id "
            "WHERE t.id=%s AND m.user_id=%s",
            (task_id, user_id),
        )
        if not task:
            raise HTTPException(404, "Task not found.")
        return task

    async def agent(self, task_id: UUID, agent_id: UUID):
        row = await self.one("SELECT * FROM agents WHERE id=%s AND task_id=%s", (agent_id, task_id))
        if not row:
            raise HTTPException(404, "Agent not found.")
        row["tool_ids"] = [
            r["tool_id"]
            for r in await self.all(
                "SELECT tool_id FROM agent_tools WHERE agent_id=%s ORDER BY tool_id", (agent_id,)
            )
        ]
        return row

    async def connection(self, task_id: UUID, connection_id: UUID):
        row = await self.one(
            "SELECT * FROM mcp_connections WHERE id=%s AND task_id=%s", (connection_id, task_id)
        )
        if not row:
            raise HTTPException(404, "MCP connection not found.")
        return row

    async def status(self, connection_id, status, error=None, auth_url=None):
        await self.all(
            "UPDATE mcp_connections SET status=%s, error=%s, auth_url=%s WHERE id=%s RETURNING id",
            (status, error, auth_url, connection_id),
        )

    async def read_secret(self, connection_id) -> dict:
        row = await self.one("SELECT secret_id FROM mcp_connections WHERE id=%s", (connection_id,))
        if not row or not row["secret_id"]:
            return {}
        if self.settings.secret_backend == "vault":
            result = await self.one(
                "SELECT decrypted_secret AS value FROM vault.decrypted_secrets WHERE id=%s",
                (row["secret_id"],),
            )
            return json.loads(result["value"]) if result else {}
        result = await self.one(
            "SELECT value FROM oak_local_secrets WHERE id=%s", (row["secret_id"],)
        )
        if not result:
            return {}
        cipher = Fernet(self.settings.local_secret_key.encode())
        return json.loads(cipher.decrypt(result["value"].encode()))

    async def write_secret(self, connection_id, value: dict):
        async with self.pool.connection() as db:
            row = await (
                await db.execute(
                    "SELECT secret_id FROM mcp_connections WHERE id=%s FOR UPDATE", (connection_id,)
                )
            ).fetchone()
            secret_id = row["secret_id"]
            serialized = json.dumps(value)
            if self.settings.secret_backend == "vault":
                if secret_id:
                    await db.execute("SELECT vault.update_secret(%s, %s)", (secret_id, serialized))
                else:
                    result = await (
                        await db.execute("SELECT vault.create_secret(%s) AS id", (serialized,))
                    ).fetchone()
                    secret_id = result["id"]
            else:
                secret_id = secret_id or uuid4()
                encrypted = (
                    Fernet(self.settings.local_secret_key.encode())
                    .encrypt(serialized.encode())
                    .decode()
                )
                await db.execute(
                    "INSERT INTO oak_local_secrets(id,value) VALUES (%s,%s) "
                    "ON CONFLICT (id) DO UPDATE SET value=EXCLUDED.value",
                    (secret_id, encrypted),
                )
            await db.execute(
                "UPDATE mcp_connections SET secret_id=%s WHERE id=%s", (secret_id, connection_id)
            )

    async def save_catalog(self, connection: dict, tools: list):
        async with self.pool.connection() as db:
            # Serialize refreshes with permission edits against this task.
            await db.execute(
                "SELECT id FROM tasks WHERE id=%s FOR UPDATE", (connection["task_id"],)
            )
            await db.execute(
                "UPDATE tools SET available=false WHERE connection_id=%s", (connection["id"],)
            )
            for tool in tools:
                await db.execute(
                    "INSERT INTO tools(id,task_id,connection_id,name,title,description,"
                    "input_schema) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(connection_id,name) DO UPDATE SET "
                    "title=EXCLUDED.title,description=EXCLUDED.description,"
                    "input_schema=EXCLUDED.input_schema,available=true",
                    (
                        uuid4(),
                        connection["task_id"],
                        connection["id"],
                        tool.name,
                        tool.title,
                        tool.description or "",
                        Jsonb(tool.input_schema),
                    ),
                )
            await db.execute(
                "UPDATE mcp_connections SET status='connected', error=NULL,auth_url=NULL,"
                "refreshed_at=now() WHERE id=%s",
                (connection["id"],),
            )

    async def select_tools(self, task_id, agent_id, tool_ids):
        unique_ids = list(set(tool_ids))
        async with self.pool.connection() as db:
            await db.execute("SELECT id FROM tasks WHERE id=%s FOR UPDATE", (task_id,))
            rows = await (
                await db.execute(
                    "SELECT t.id,t.available,EXISTS(SELECT 1 FROM agent_tools a "
                    "WHERE a.agent_id=%s AND a.tool_id=t.id) AS already_selected "
                    "FROM tools t WHERE t.task_id=%s AND t.id=ANY(%s::uuid[])",
                    (agent_id, task_id, unique_ids),
                )
            ).fetchall()
            if len(rows) != len(unique_ids):
                raise HTTPException(422, "Select only tools from this task.")
            if any(not r["available"] and not r["already_selected"] for r in rows):
                raise HTTPException(422, "An unavailable tool cannot receive a new grant.")
            await db.execute("DELETE FROM agent_tools WHERE agent_id=%s", (agent_id,))
            for tool_id in unique_ids:
                await db.execute(
                    "INSERT INTO agent_tools(agent_id,tool_id,task_id) VALUES (%s,%s,%s)",
                    (agent_id, tool_id, task_id),
                )


async def migrate(settings: Settings):
    settings.validate_runtime()
    store = Store(settings)
    await store.pool.open()
    try:
        async with store.pool.connection() as db:
            await db.execute("SELECT pg_advisory_xact_lock(183427)")
            await db.execute("CREATE TABLE IF NOT EXISTS oak_migrations(name text PRIMARY KEY)")
            for path in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
                if not await (
                    await db.execute("SELECT name FROM oak_migrations WHERE name=%s", (path.name,))
                ).fetchone():
                    await db.execute(path.read_text())
                    await db.execute("INSERT INTO oak_migrations VALUES (%s)", (path.name,))
            if settings.secret_backend == "vault":
                await db.execute("CREATE EXTENSION IF NOT EXISTS supabase_vault CASCADE")
            elif settings.secret_backend == "local" and settings.local_secret_key:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS oak_local_secrets(id uuid PRIMARY KEY,value text)"
                )
            else:
                raise RuntimeError("Configure Vault, or an encrypted local secret store.")
    finally:
        await store.pool.close()


if __name__ == "__main__":
    import asyncio

    from oak.settings import get_settings

    asyncio.run(migrate(get_settings()))
