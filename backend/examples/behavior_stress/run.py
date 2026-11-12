"""Run the four live comparisons with a shared USD 10 allowance."""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import socket
import time
from datetime import date, datetime
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import psycopg
import uvicorn
from cryptography.fernet import Fernet
from mcp import Client
from mcp import types as mcp_types
from mcp.client.streamable_http import streamable_http_client
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from oak.db import migrate
from oak.discovery_validation import canonical, validate_json
from oak.main import create_app
from oak.model_client import GeminiClient
from oak.settings import Settings
from oak.training_runner import run_episode

from .budget import BudgetModel
from .cases import ALL_TOOLS, SCOPE, cases
from .report import render
from .server import build_server
from .sources import Sources, now, save


def configuration(database):
    settings = Settings()
    original = conninfo_to_dict(settings.database_url)
    if original.get("host", "localhost") not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("This runner requires a local Postgres server.")
    if not database.startswith("oak_behavior_") or not database.endswith("_test"):
        raise ValueError("Use a separate oak_behavior_*_test database.")
    return settings.model_copy(
        update={
            "database_url": make_conninfo(settings.database_url, dbname=database),
            "environment": "local",
            "secret_backend": "local",
            "local_secret_key": Fernet.generate_key().decode(),
            "api_key": "behavior-" + uuid4().hex,
            "allow_local_mcp": True,
        }
    )


async def create_database(settings):
    conn = await psycopg.AsyncConnection.connect(
        make_conninfo(settings.database_url, dbname="postgres"), autocommit=True
    )
    async with conn:
        name = conninfo_to_dict(settings.database_url)["dbname"]
        if await (
            await conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,))
        ).fetchone():
            raise ValueError("The test database already exists. No records were changed.")
        await conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name))
        )
    await migrate(settings)


async def native_call(client, name, arguments):
    response = await client.session.send_request(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(name=name, arguments=arguments)
        ),
        mcp_types.CallToolResult,
        request_read_timeout_seconds=30,
    )
    data = response.structured_content
    if data is None:
        texts = [part.text for part in response.content if part.type == "text"]
        if len(texts) == 1:
            try:
                data = json.loads(texts[0])
            except ValueError:
                data = {"text": texts[0]}
    return response, data


async def preflight(endpoint, manifest, root):
    output = {"started_at": now(), "calls": [], "schemas": []}
    async with Client(streamable_http_client(endpoint)) as client:
        catalog = (await client.list_tools()).tools
        assert {tool.name for tool in catalog} == set(ALL_TOOLS)
        for tool in catalog:
            assert tool.annotations.read_only_hint and not tool.annotations.destructive_hint
            output["schemas"].append(tool.model_dump(mode="json", by_alias=True))

        async def probe(name, arguments):
            item = {"name": name, "arguments": arguments}
            try:
                response, data = await native_call(client, name, arguments)
                item.update(
                    response=response.model_dump(mode="json", by_alias=True),
                    status="error" if response.is_error else "complete",
                )
                contract = next(t for t in catalog if t.name == name)
                validate_json(arguments, contract.input_schema)
                if not response.is_error and contract.output_schema:
                    validate_json(data, contract.output_schema)
                return data if not response.is_error else None
            except Exception as exc:
                item.update(status="error", error=str(exc))
                return None
            finally:
                output["calls"].append(item)
                save(root / "preflight.json", output)

        await probe(
            "weather_forecast",
            {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "start_date": manifest["saturday"],
                "end_date": manifest["sunday"],
            },
        )
        food = await probe("food_search", {"category": "en:canned-beans", "page_size": 2})
        if food and food.get("products"):
            await probe("food_product", {"barcode": food["products"][0]["code"]})
        books = await probe("book_search", {"query": "title:The Hobbit author:Tolkien", "limit": 1})
        if books and books.get("records"):
            work_key = books["records"][0]["key"]
            record = await probe("book_record", {"kind": "work", "identifier": work_key})
            await probe("book_editions", {"work_id": work_key, "limit": 2})
            authors = [
                link["target"]
                for link in (record or {}).get("links", [])
                if link["field"] == "authors"
            ]
            if authors:
                await probe("book_record", {"kind": "author", "identifier": authors[0]})
                await probe("author_works", {"author_id": authors[0], "limit": 2})
    output["finished_at"] = now()
    save(root / "preflight.json", output)
    return output


async def request(client, method, path, body=None):
    response = await client.request(method, path, json=body)
    if response.is_error:
        raise RuntimeError(f"Oak {method} {path}: {response.status_code} {response.text[:800]}")
    return response.json()


async def settled(client, path, output, *, discovery=False):
    previous = None
    while True:
        detail = await request(client, "GET", path)
        save(output, detail)
        run = detail["run"]
        status = (run["status"], run["stage"], run.get("model_calls"), run.get("mcp_calls"))
        if status != previous:
            print(
                json.dumps(
                    {"artifact": output.name, "status": status, "message": run.get("message")}
                ),
                flush=True,
            )
            previous = status
        active = {"running", "pausing"} if discovery else {"running", "stopping"}
        if run["status"] not in active:
            return detail
        await asyncio.sleep(2)


async def baseline(case, tools, app, model, root, scope):
    events, calls = [], []
    started = time.monotonic()
    selected = [tool for tool in tools if tool["name"] in case["tools"]]
    output = root / f"{case['name']}-baseline.json"

    async def emit(kind, payload):
        events.append({"kind": kind, "data": payload})
        save(output, {"status": "running", "events": events, "calls": calls})

    async def stop():
        return time.monotonic() - started >= 300

    async def dispatch(tool, arguments, invocation_id, *, permit):
        if len(calls) >= 30 or await stop():
            raise RuntimeError("The comparison tool or time limit was reached.")
        if not permit.baseline:
            raise ValueError("The baseline received a non-baseline permit.")
        permit.consume(tool["id"], arguments, invocation_id)
        validate_json(arguments, tool["input_schema"])
        entry = {
            "tool_id": tool["id"],
            "name": tool["name"],
            "arguments": arguments,
            "invocation_id": invocation_id,
            "started_at": now(),
        }
        calls.append(entry)
        save(output, {"status": "running", "events": events, "calls": calls})
        try:
            connection = await app.state.store.one(
                "SELECT * FROM mcp_connections WHERE id=%s", (tool["connection_id"],)
            )
            async with app.state.connections.session(connection) as client:
                native = {t.name: t for t in await app.state.connections.catalog(client)}[
                    tool["name"]
                ]
                if (
                    native.input_schema != tool["input_schema"]
                    or native.output_schema != tool["output_schema"]
                ):
                    raise ValueError("The MCP contract changed.")
                response, data = await native_call(client, tool["name"], arguments)
                if not response.is_error and tool["output_schema"]:
                    validate_json(data, tool["output_schema"])
                result = {
                    "status": "unknown" if response.is_error else "succeeded",
                    "dispatched": True,
                    "data": data,
                    "raw": response.model_dump(mode="json", by_alias=True),
                    "error": "tool_error" if response.is_error else None,
                    "coverage": "unknown",
                }
        except Exception as exc:
            result = {"status": "unknown", "dispatched": True, "error": str(exc)}
        entry.update(result=result, finished_at=now())
        return result

    try:
        async with asyncio.timeout(300):
            result = await run_episode(
                case={
                    "query": case["query"],
                    "tool_ids": [t["id"] for t in selected],
                    "task_boundaries": scope,
                },
                tools=tools,
                candidate=None,
                model=model,
                dispatch=dispatch,
                emit=emit,
                instructions=canonical(scope),
                run_mode="training",
                stage="baseline",
                limits={
                    "max_steps": 20,
                    "active_seconds": 300,
                    "input_tokens": app.state.store.settings.surface_input_tokens,
                    "output_tokens": app.state.store.settings.surface_probe_output_tokens,
                },
                should_stop=stop,
            )
    except Exception as exc:
        result = {
            "status": "interrupted" if isinstance(exc, TimeoutError) else "failed",
            "final_output": "",
            "error": str(exc) or type(exc).__name__,
        }
    document = {
        "result": result,
        "events": events,
        "calls": calls,
        "elapsed_seconds": time.monotonic() - started,
    }
    save(output, document)
    return {
        "artifact": output.name,
        "status": result["status"],
        "message": result.get("error", ""),
        "elapsed_seconds": document["elapsed_seconds"],
    }


async def live(settings, sources, endpoint, root, manifest, state):
    model = BudgetModel(GeminiClient(settings), root)

    async def prepare(run, case, episode_index):
        sources.select_group("training")
        return "public-response-cache:training:v1"

    app = create_app(
        settings, discovery_model=model, training_model=model, prepare_environment=prepare
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://oak.local",
            headers={"X-Oak-Key": settings.api_key, "X-Oak-User": "demo-alex"},
        ) as client:
            scope = {
                **SCOPE,
                "context_and_rules": SCOPE["context_and_rules"]
                + f" Today is {manifest['anchor_date']}."
                + f" Probe weather from {manifest['saturday']} to {manifest['sunday']}"
                + " in America/New_York.",
            }
            task = await request(
                client,
                "POST",
                "/api/tasks",
                {
                    "name": "Live behavior stress test",
                    "objective": SCOPE["responsibilities"],
                    "scope": scope,
                },
            )
            task_path = f"/api/tasks/{task['id']}"
            connection = await request(
                client,
                "POST",
                task_path + "/connections",
                {"name": "Public research data", "url": endpoint, "auth_mode": "none"},
            )
            connection = await request(
                client, "POST", task_path + f"/connections/{connection['id']}/refresh"
            )
            if connection["status"] != "connected":
                raise RuntimeError("Oak could not discover the public source tools.")
            tools = await request(client, "GET", task_path + "/tools")
            tools = [tool for tool in tools if tool["name"] in ALL_TOOLS]
            agent = await request(
                client,
                "POST",
                task_path + "/agents",
                {
                    "name": "Public research agent",
                    "responsibilities": SCOPE["responsibilities"],
                    "scope": scope,
                    "tool_ids": [tool["id"] for tool in tools],
                },
            )
            agent_path = task_path + f"/agents/{agent['id']}"
            state.update(task_id=task["id"], agent_id=agent["id"], tools=tools)
            save(root / "run.json", state)

            def selected(item):
                return [tool["id"] for tool in tools if tool["name"] in item["tools"]]

            training_path = agent_path + "/training"
            for item in manifest["training"]:
                await request(
                    client,
                    "POST",
                    training_path + "/cases",
                    {
                        "query": item["query"],
                        "tool_ids": selected(item),
                        "task_success": item["task_success"],
                    },
                )
            sources.select_group("discovery")
            model.phase = "discovery"
            discovery_path = agent_path + "/discovery"
            discovery = await request(
                client,
                "POST",
                discovery_path + "/runs",
                {
                    "request_id": str(uuid4()),
                    "environment": "Live public sources with a timestamped response cache",
                    "limits": {
                        "cost_usd": "2",
                        "model_calls": 40,
                        "mcp_calls": 30,
                        "active_seconds": 1200,
                        "clarification_rounds": 2,
                    },
                },
            )
            discovery = await settled(
                client,
                discovery_path + f"/runs/{discovery['run']['id']}",
                root / "discovery.json",
                discovery=True,
            )
            state["discovery"] = discovery["run"]
            accepted = None
            if discovery["run"].get("reason") == "ready":
                model.phase = "training"
                sources.select_group("training")
                detail = await request(
                    client,
                    "POST",
                    training_path + "/runs",
                    {
                        "request_id": str(uuid4()),
                        "environment_ref": "public-response-cache:training:v1",
                        "limits": {
                            "cost_usd": "4",
                            "model_calls": 100,
                            "mcp_calls": 100,
                            "max_steps": 20,
                            "max_rounds": 2,
                            "active_seconds": 1800,
                        },
                    },
                )
                detail = await settled(
                    client, training_path + f"/runs/{detail['run']['id']}", root / "training.json"
                )
                state["training"] = detail["run"]
                overview = await request(client, "GET", training_path)
                if overview["inference_ready"]:
                    accepted = overview["accepted_candidate"]
                    save(root / "accepted.json", accepted)
                    state["frozen_digest"] = accepted["digest"]
            else:
                state["training"] = {
                    "status": "blocked",
                    "message": "Discovery did not produce a ready handoff.",
                }
            save(root / "run.json", state)
            async with app.state.store.pool.connection() as db:
                inputs = await app.state.discoveries._inputs(
                    db, UUID(task["id"]), UUID(agent["id"])
                )
            for case in manifest["comparisons"]:
                sources.select_group("pair_" + case["name"])
                model.phase = case["name"] + "_baseline"
                pair = state["comparisons"].setdefault(case["name"], {})
                print(json.dumps({"comparison": model.phase, "state": "starting"}), flush=True)
                pair["baseline"] = await baseline(
                    case,
                    inputs["tools"],
                    app,
                    model,
                    root,
                    {"task": inputs["task"], "agent": inputs["agent"]},
                )
                save(root / "run.json", state)
                if accepted:
                    model.phase = case["name"] + "_ontology"
                    started = time.monotonic()
                    try:
                        detail = await request(
                            client,
                            "POST",
                            training_path + "/inference",
                            {
                                "request_id": str(uuid4()),
                                "accepted_candidate_id": accepted["id"],
                                "query": case["query"],
                                "tool_ids": selected(case),
                                "limits": {
                                    "cost_usd": "0.5",
                                    "model_calls": 40,
                                    "mcp_calls": 30,
                                    "max_steps": 20,
                                    "active_seconds": 300,
                                },
                            },
                        )
                        artifact = f"{case['name']}-ontology.json"
                        detail = await settled(
                            client, training_path + f"/runs/{detail['run']['id']}", root / artifact
                        )
                        current = await request(client, "GET", training_path)
                        if current["accepted_candidate"]["digest"] != accepted["digest"]:
                            raise RuntimeError("The accepted ontology changed during inference.")
                        pair["ontology"] = {
                            "artifact": artifact,
                            "status": detail["run"]["status"],
                            "message": detail["run"]["message"],
                            "elapsed_seconds": time.monotonic() - started,
                        }
                    except Exception as exc:
                        pair["ontology"] = {"status": "failed", "message": str(exc)}
                else:
                    pair["ontology"] = {
                        "status": "blocked",
                        "message": (
                            "No accepted ontology is available. No ontology episode was dispatched."
                        ),
                    }
                save(root / "run.json", state)
                render(root)
            state["status"] = "finished"


async def main(args):
    root = Path(args.output).resolve()
    if args.report_only:
        render(root)
        return
    if (root / "run.json").exists() or (root / "budget.json").exists():
        raise ValueError("This output directory already contains a run. It will not be replayed.")
    root.mkdir(parents=True, exist_ok=True)
    anchor = (
        date.fromisoformat(args.date)
        if args.date
        else datetime.now(ZoneInfo("America/New_York")).date()
    )
    manifest = cases(anchor)
    source_paths = [
        *Path(__file__).parent.glob("*.py"),
        *Path(__file__).parents[2].joinpath("oak").glob("*.py"),
    ]
    manifest["source_hashes"] = {
        str(path.relative_to(Path(__file__).parents[2])): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(source_paths)
    }
    save(root / "manifest.json", manifest)
    state = {
        "started_at": now(),
        "status": "preflight",
        "comparisons": {},
        "database": args.database,
    }
    save(root / "run.json", state)
    sources = Sources(root)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}/public/mcp"
    server = uvicorn.Server(
        uvicorn.Config(build_server(sources), log_level="error", access_log=False)
    )
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    job = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started:
            if job.done():
                await job
                raise RuntimeError("The local MCP server did not start.")
            await asyncio.sleep(0.05)
        checked = await preflight(endpoint, manifest, root)
        state["preflight"] = {
            "calls": len(checked["calls"]),
            "errors": sum(c["status"] == "error" for c in checked["calls"]),
        }
        print(json.dumps({"preflight": state["preflight"]}), flush=True)
        if args.live:
            if not any(c["status"] == "complete" for c in checked["calls"]):
                raise RuntimeError(
                    "No public source operation completed. Model calls were not started."
                )
            settings = configuration(args.database)
            if not settings.gemini_project:
                raise ValueError("The backend Gemini project is not configured.")
            os.environ.setdefault("OAK_JAVA", "/opt/homebrew/opt/openjdk@21/bin/java")
            await create_database(settings)
            state["status"] = "running"
            await live(settings, sources, endpoint, root, manifest, state)
        else:
            state["status"] = "preflight_finished"
    except BaseException as exc:
        state.update(
            status="interrupted" if isinstance(exc, asyncio.CancelledError) else "failed",
            error=str(exc) or type(exc).__name__,
        )
        raise
    finally:
        state["finished_at"] = now()
        save(root / "run.json", state)
        render(root)
        server.should_exit = True
        await job
        await sources.close()
        listener.close()
        print(
            json.dumps({"report": str(root / "report.html"), "status": state["status"]}), flush=True
        )


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--database", default="oak_behavior_20261110_test")
    parser.add_argument("--date", help="Resolve request dates once in America/New_York.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Permit the planned model calls, with a USD 10 total cap.",
    )
    parser.add_argument("--report-only", action="store_true")
    asyncio.run(main(parser.parse_args()))
