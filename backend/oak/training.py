"""Persist and execute bounded training runs without automatic continuation."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from mcp import types as mcp_types
from psycopg.types.json import Jsonb

from oak.discovery_credentials import Credentials
from oak.discovery_validation import canonical, digest, redact, validate_json
from oak.kernel_acceptance import inference_eligibility
from oak.kernel_dispatcher import (
    DispatchPermit,
    credential_references,
    validate_dispatch_arguments,
    verify_transport_arguments,
)
from oak.kernel_execution import VERSIONS
from oak.model_client import GeminiClient, GenerationLimits, ModelFailure
from oak.repair_patch import candidate_digest
from oak.repair_schemas import Candidate
from oak.request_preparation import prepare_request
from oak.training_evaluation import EVALUATOR_VERSION

logger = logging.getLogger(__name__)
NANOS = 1_000_000_000


class TrainingHalt(Exception):
    pass


def snapshot(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return json.loads(canonical(value))


class Training:
    def __init__(self, store, connections, discoveries, model=None, prepare_environment=None):
        self.store, self.connections, self.discoveries = store, connections, discoveries
        self.settings = store.settings
        self.model = model or GeminiClient(self.settings)
        self.prepare_environment = prepare_environment
        self.credentials = Credentials(self.settings, "training_credentials")
        self.jobs = {}

    async def recover_interrupted(self):
        async with self.store.pool.connection() as db:
            rows = await (
                await db.execute(
                    "UPDATE training_runs SET status='interrupted',stage='finished',"
                    "message='Execution was interrupted. No call was repeated.',updated_at=now() "
                    "WHERE status IN ('running','stopping') RETURNING id"
                )
            ).fetchall()
            for row in rows:
                await self._interrupt(db, row["id"])

    async def _interrupt(self, db, run_id):
        await db.execute(
            "UPDATE training_calls SET status='unknown',finished_at=now() "
            "WHERE run_id=%s AND status='dispatched'",
            (run_id,),
        )
        await db.execute(
            "UPDATE training_episodes SET status='interrupted',finished_at=now() "
            "WHERE run_id=%s AND status IN ('running','evaluating')",
            (run_id,),
        )
        await self._event(db, run_id, "interrupted", {"no_automatic_replay": True})

    async def close(self):
        jobs = list(self.jobs.values())
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)

    async def _event(self, db, run_id, kind, data, episode_id=None):
        event_id = uuid4()
        await db.execute(
            "INSERT INTO training_events(id,run_id,episode_id,kind,message,data) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                event_id,
                run_id,
                episode_id,
                kind,
                str(data.get("message", "")),
                Jsonb(redact(snapshot(data), preserve_schemas=True)),
            ),
        )
        return str(event_id)

    async def emit(self, run_id, kind, data, episode_id=None):
        async with self.store.pool.connection() as db:
            return await self._event(db, run_id, kind, data, episode_id)

    async def cases(self, agent_id):
        return await self.store.all(
            "SELECT * FROM training_cases WHERE agent_id=%s ORDER BY created_at,id", (agent_id,)
        )

    async def save_case(self, task_id, agent_id, body, case_id=None):
        async with self.store.pool.connection() as db:
            await db.execute("SELECT id FROM tasks WHERE id=%s FOR UPDATE", (task_id,))
            await self._check_tools(db, agent_id, body.tool_ids)
            if case_id:
                row = await (
                    await db.execute(
                        "UPDATE training_cases SET query=%s,tool_ids=%s,task_success=%s,"
                        "updated_at=now() "
                        "WHERE id=%s AND agent_id=%s RETURNING *",
                        (
                            body.query,
                            Jsonb([str(i) for i in body.tool_ids]),
                            body.task_success,
                            case_id,
                            agent_id,
                        ),
                    )
                ).fetchone()
                if not row:
                    raise HTTPException(404, "Test case not found.")
                return row
            return await (
                await db.execute(
                    "INSERT INTO training_cases(id,task_id,agent_id,query,tool_ids,task_success) "
                    "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                    (
                        uuid4(),
                        task_id,
                        agent_id,
                        body.query,
                        Jsonb([str(i) for i in body.tool_ids]),
                        body.task_success,
                    ),
                )
            ).fetchone()

    async def delete_case(self, agent_id, case_id):
        row = await self.store.one(
            "DELETE FROM training_cases WHERE id=%s AND agent_id=%s RETURNING id",
            (case_id, agent_id),
        )
        if not row:
            raise HTTPException(404, "Test case not found.")

    async def _check_tools(self, db, agent_id, tool_ids):
        ids = {str(i) for i in tool_ids}
        rows = await (
            await db.execute(
                "SELECT t.id FROM tools t JOIN agent_tools a ON a.tool_id=t.id "
                "WHERE a.agent_id=%s AND t.available=true",
                (agent_id,),
            )
        ).fetchall()
        if not ids or not ids <= {str(r["id"]) for r in rows}:
            raise HTTPException(422, "Select available tools granted to this agent.")

    async def _stats(self, run):
        stats = await self.store.one(
            "SELECT count(*) FILTER(WHERE kind='model') AS model_calls,"
            "count(*) FILTER(WHERE kind='mcp') AS mcp_calls,"
            "coalesce(sum(accounted_nanos),0) AS accounted FROM training_calls WHERE run_id=%s",
            (run["id"],),
        )
        return {
            **run,
            "model_calls": stats["model_calls"],
            "mcp_calls": stats["mcp_calls"],
            "accounted_usd": float(stats["accounted"]) / NANOS,
        }

    async def accepted(self, agent_id):
        return await self.store.one(
            "SELECT c.*,r.input_digest FROM training_candidates c "
            "JOIN training_runs r ON r.id=c.run_id "
            "WHERE r.agent_id=%s AND r.accepted_candidate_id=c.id AND r.mode='training' "
            "AND r.status='completed' ORDER BY r.created_at DESC LIMIT 1",
            (agent_id,),
        )

    async def _eligibility(self, row, inputs):
        events = (
            await self.store.all(
                "SELECT id,data FROM training_events WHERE run_id=%s AND kind='kernel_validation'",
                (row["run_id"],),
            )
            if row
            else []
        )
        return inference_eligibility(
            row, digest(inputs), {str(t["id"]) for t in inputs["tools"] if t["available"]}, events
        )

    async def overview(self, task_id, agent_id, offset=0):
        rows = await self.store.all(
            "SELECT * FROM training_runs WHERE agent_id=%s ORDER BY created_at DESC "
            "LIMIT 31 OFFSET %s",
            (agent_id, offset),
        )
        discovery = await self.store.one(
            "SELECT id,input_digest FROM discovery_runs WHERE agent_id=%s AND status='completed' "
            "AND reason='ready' ORDER BY created_at DESC LIMIT 1",
            (agent_id,),
        )
        cases = await self.cases(agent_id)
        async with self.store.pool.connection() as db:
            inputs = await self.discoveries._inputs(db, task_id, agent_id)
        available = {t["id"] for t in inputs["tools"] if t["available"]}
        ready = bool(discovery and cases and discovery["input_digest"] == digest(inputs))
        ready = ready and all(set(case["tool_ids"]) <= available for case in cases)
        accepted = await self.accepted(agent_id)
        eligibility = await self._eligibility(accepted, inputs)
        return {
            **eligibility,
            "cases": cases,
            "runs": [await self._stats(row) for row in rows[:30]],
            "has_more": len(rows) > 30,
            "accepted_candidate": accepted,
            "ready": ready,
            "message": ""
            if ready
            else "Complete current discovery and check the saved case tools.",
        }

    async def detail(self, run_id):
        run = await self.store.one("SELECT * FROM training_runs WHERE id=%s", (run_id,))
        if not run:
            raise HTTPException(404, "Training run not found.")
        return {
            "run": await self._stats(run),
            "episodes": await self.store.all(
                "SELECT * FROM training_episodes WHERE run_id=%s ORDER BY created_at,id", (run_id,)
            ),
            "candidates": await self.store.all(
                "SELECT * FROM training_candidates WHERE run_id=%s OR id=%s ORDER BY created_at,id",
                (run_id, run["accepted_candidate_id"]),
            ),
            "events": await self.store.all(
                "SELECT * FROM training_events WHERE run_id=%s ORDER BY sequence", (run_id,)
            ),
        }

    async def start(self, task_id, agent_id, user, body, inference=False):
        if isinstance(self.model, GeminiClient):
            problem = self.discoveries.configuration_problem()
            if problem:
                raise HTTPException(422, problem.replace("discovery", "training"))
        mode = "inference" if inference else "training"
        request_digest = digest({"mode": mode, "body": snapshot(body)})
        for key in ("cost_usd", "model_calls", "mcp_calls", "active_seconds"):
            ceiling = getattr(self.settings, "surface_max_" + key)
            if getattr(body.limits, key) > ceiling:
                raise HTTPException(422, f"{key} exceeds the backend ceiling.")
        async with self.store.pool.connection() as db:
            await db.execute("SELECT id FROM tasks WHERE id=%s FOR UPDATE", (task_id,))
            prior = await (
                await db.execute(
                    "SELECT * FROM training_runs WHERE request_id=%s",
                    (body.request_id,),
                )
            ).fetchone()
            if prior:
                if prior["agent_id"] != agent_id or prior["request_digest"] != request_digest:
                    raise HTTPException(409, "The request ID was used for different inputs.")
                run_id = prior["id"]
            else:
                busy_discovery = await (
                    await db.execute(
                        "SELECT id FROM discovery_runs WHERE agent_id=%s "
                        "AND status IN ('running','pausing')",
                        (agent_id,),
                    )
                ).fetchone()
                if busy_discovery:
                    raise HTTPException(409, "Finish or stop this agent's active discovery run.")
                active = await (
                    await db.execute(
                        "SELECT id FROM training_runs WHERE agent_id=%s "
                        "AND status IN ('running','stopping')",
                        (agent_id,),
                    )
                ).fetchone()
                if active:
                    raise HTTPException(409, "This agent already has an active training run.")
                inputs = await self.discoveries._inputs(db, task_id, agent_id)
                selected_discovery = getattr(body, "discovery_run_id", None)
                discovery = await (
                    await db.execute(
                        "SELECT * FROM discovery_runs WHERE agent_id=%s AND status='completed' "
                        "AND reason='ready' AND (%s::uuid IS NULL OR id=%s) "
                        "ORDER BY created_at DESC LIMIT 1",
                        (agent_id, selected_discovery, selected_discovery),
                    )
                ).fetchone()
                if not discovery or discovery["input_digest"] != digest(inputs):
                    raise HTTPException(409, "Complete discovery for the current task and grants.")
                if inference:
                    accepted = await (
                        await db.execute(
                            "SELECT c.*,r.input_digest,r.discovery_run_id "
                            "FROM training_candidates c "
                            "JOIN training_runs r ON r.accepted_candidate_id=c.id "
                            "WHERE r.agent_id=%s AND r.mode='training' AND r.status='completed' "
                            "ORDER BY r.created_at DESC LIMIT 1",
                            (agent_id,),
                        )
                    ).fetchone()
                    if not accepted or accepted["input_digest"] != digest(inputs):
                        raise HTTPException(
                            409, "Train an accepted kernel for the current surface."
                        )
                    events = await (
                        await db.execute(
                            "SELECT id,data FROM training_events WHERE run_id=%s "
                            "AND kind='kernel_validation'",
                            (accepted["run_id"],),
                        )
                    ).fetchall()
                    eligibility = inference_eligibility(
                        accepted,
                        digest(inputs),
                        {str(t["id"]) for t in inputs["tools"] if t["available"]},
                        events,
                    )
                    if not eligibility["inference_ready"]:
                        raise HTTPException(409, eligibility["inference_message"])
                    if not set(map(str, body.tool_ids)) <= set(eligibility["inference_tool_ids"]):
                        raise HTTPException(422, "Select tools enabled by the accepted kernel.")
                    if body.accepted_candidate_id and body.accepted_candidate_id != accepted["id"]:
                        raise HTTPException(
                            409, "The accepted version changed. Refresh before inference."
                        )
                    discovery["id"] = accepted["discovery_run_id"]
                    cases = [
                        {
                            "id": str(uuid4()),
                            "query": body.query,
                            "tool_ids": [str(i) for i in body.tool_ids],
                        }
                    ]
                else:
                    cases = snapshot(
                        await (
                            await db.execute(
                                "SELECT * FROM training_cases WHERE agent_id=%s "
                                "ORDER BY created_at,id",
                                (agent_id,),
                            )
                        ).fetchall()
                    )
                if not cases:
                    raise HTTPException(422, "Save at least one test case.")
                for case in cases:
                    await self._check_tools(db, agent_id, case["tool_ids"])
                run_id = uuid4()
                await db.execute(
                    "INSERT INTO training_runs(id,task_id,agent_id,request_id,request_digest,"
                    "created_by,mode,discovery_run_id,inputs,input_digest,cases,limits,environment_ref,"
                    "evaluator_version,status,stage,accepted_candidate_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s,%s)",
                    (
                        run_id,
                        task_id,
                        agent_id,
                        body.request_id,
                        request_digest,
                        user,
                        mode,
                        discovery["id"],
                        Jsonb(inputs),
                        digest(inputs),
                        Jsonb(cases),
                        Jsonb(snapshot(body.limits)),
                        getattr(body, "environment_ref", None),
                        EVALUATOR_VERSION,
                        "inference" if inference else "baseline",
                        accepted["id"] if inference else None,
                    ),
                )
                await self._event(db, run_id, "run_started", {"mode": mode})
        if not prior:
            self.jobs[str(run_id)] = asyncio.create_task(self._run(run_id))
        return await self.detail(run_id)

    async def stop(self, run_id):
        await self.store.all(
            "UPDATE training_runs SET status='stopping',message='Stop requested.',updated_at=now() "
            "WHERE id=%s AND status='running' RETURNING id",
            (run_id,),
        )
        job = self.jobs.get(str(run_id))
        if job:
            job.cancel()
        return await self.detail(run_id)

    async def _set(self, run_id, *, stage=None, status=None, message=""):
        await self.store.all(
            "UPDATE training_runs SET stage=coalesce(%s,stage),status=coalesce(%s,status),"
            "message=%s,updated_at=now() WHERE id=%s RETURNING id",
            (stage, status, message, run_id),
        )

    async def _stopped(self, run_id):
        row = await self.store.one("SELECT status FROM training_runs WHERE id=%s", (run_id,))
        return not row or row["status"] != "running"

    async def _reserve(self, run_id, episode_id, kind, request):
        reservation = (
            (
                self.settings.surface_input_tokens * 1500
                + self.settings.surface_proposal_output_tokens * 7500
            )
            if kind == "model"
            else 0
        )
        async with self.store.pool.connection() as db:
            row = await (
                await db.execute(
                    "SELECT * FROM training_runs WHERE id=%s FOR UPDATE",
                    (run_id,),
                )
            ).fetchone()
            if row["status"] != "running":
                raise TrainingHalt("The run stopped before dispatch.")
            if (datetime.now(UTC) - row["created_at"]).total_seconds() >= row["limits"][
                "active_seconds"
            ]:
                raise TrainingHalt("The run time limit was reached.")
            current = await self.discoveries._inputs(db, row["task_id"], row["agent_id"])
            if digest(current) != row["input_digest"]:
                raise TrainingHalt("The task, grants, or tool contracts changed.")
            stats = await (
                await db.execute(
                    "SELECT count(*) FILTER(WHERE kind=%s) AS calls,"
                    "coalesce(sum(accounted_nanos),0) AS spent FROM training_calls WHERE run_id=%s",
                    (kind, run_id),
                )
            ).fetchone()
            if stats["calls"] >= row["limits"][kind + "_calls"]:
                raise TrainingHalt(f"The {kind} call limit was reached.")
            if stats["spent"] + reservation > int(Decimal(row["limits"]["cost_usd"]) * NANOS):
                raise TrainingHalt("The model cost limit was reached before dispatch.")
            call_id = uuid4()
            await db.execute(
                "INSERT INTO training_calls(id,run_id,episode_id,kind,request,status,"
                "reserved_nanos,accounted_nanos) VALUES (%s,%s,%s,%s,%s,'dispatched',%s,%s)",
                (
                    call_id,
                    run_id,
                    episode_id,
                    kind,
                    Jsonb(redact(snapshot(request), preserve_schemas=True)),
                    reservation,
                    reservation,
                ),
            )
            await self._event(
                db,
                run_id,
                "call_dispatched",
                {"call_id": str(call_id), "kind": kind, "request": snapshot(request)},
                episode_id,
            )
        return str(call_id)

    async def _finish(self, call_id, status, response, usage=None):
        usage = snapshot(usage) if usage is not None else None
        async with self.store.pool.connection() as db:
            call = await (
                await db.execute(
                    "SELECT * FROM training_calls WHERE id=%s FOR UPDATE",
                    (call_id,),
                )
            ).fetchone()
            if call["status"] != "dispatched":
                return
            cost = call["reserved_nanos"]
            if usage is not None and "input_tokens" in usage and "output_tokens" in usage:
                cost = max(0, usage["input_tokens"]) * 1500 + max(0, usage["output_tokens"]) * 7500
            await db.execute(
                "UPDATE training_calls SET status=%s,response=%s,usage=%s,accounted_nanos=%s,"
                "finished_at=now() WHERE id=%s",
                (
                    status,
                    Jsonb(redact(snapshot(response), preserve_schemas=True)),
                    Jsonb(usage) if usage is not None else None,
                    cost,
                    call_id,
                ),
            )
            await self._event(
                db,
                call["run_id"],
                "call_finished",
                {"call_id": str(call_id), "status": status, "response": snapshot(response)},
                call["episode_id"],
            )

    def _generate(self, run_id, episode_id=None):
        from oak.evidence_access import ContextCapacity, generate_with_evidence

        async def single(*, instructions, data, response_schema):
            call_id = await self._reserve(
                run_id,
                episode_id,
                "model",
                {
                    "instructions": instructions,
                    "data": data,
                    "response_schema": response_schema.model_json_schema(),
                },
            )
            try:
                result = await self.model.generate(
                    instructions,
                    data,
                    response_schema,
                    limits=GenerationLimits(
                        self.settings.surface_input_tokens,
                        self.settings.surface_proposal_output_tokens,
                        self.settings.surface_model_timeout,
                    ),
                )
                if getattr(result, "request", None) is not None:
                    await self.emit(
                        run_id,
                        "structured_model_request",
                        {"call_id": str(call_id), "request": result.request},
                        episode_id,
                    )
                await self._finish(call_id, "succeeded", snapshot(result.data), result.usage)
                return result
            except ModelFailure as exc:
                diagnostic = {"error": exc.code}
                for field in ("validation_errors", "failed_output"):
                    value = getattr(exc, field, None)
                    if value is not None:
                        diagnostic[field] = value
                await self._finish(call_id, "failed", diagnostic, exc.usage)
                if exc.code == "invalid_output":
                    raise
                raise TrainingHalt("The model could not complete a structured request.") from exc
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._finish(call_id, "failed", {"error": "invalid_model_result"})
                raise

        async def generate(*, instructions, data, response_schema, saved_evidence=None):
            async def emit(kind, payload):
                await self.emit(run_id, kind, payload, episode_id)

            try:
                return await generate_with_evidence(
                    single,
                    instructions=instructions,
                    data=data,
                    response_schema=response_schema,
                    input_tokens=self.settings.surface_input_tokens,
                    emit=emit,
                    saved_evidence=saved_evidence,
                )
            except ContextCapacity as error:
                raise TrainingHalt(str(error)) from error

        return generate

    async def _dispatch(self, run, episode_id, tool, arguments, invocation_id, *, permit):
        if not isinstance(permit, DispatchPermit):
            raise TrainingHalt("External execution requires a kernel dispatch permit.")
        episode = await self.store.one(
            "SELECT e.stage,c.digest,r.mode FROM training_episodes e "
            "JOIN training_runs r ON r.id=e.run_id LEFT JOIN training_candidates c "
            "ON c.id=e.candidate_id WHERE e.id=%s AND e.run_id=%s",
            (episode_id, run["id"]),
        )
        if not episode:
            raise TrainingHalt("The dispatch episode is unavailable.")
        if permit.baseline:
            if episode["mode"] != "training" or episode["stage"] != "baseline":
                raise TrainingHalt("Only persisted baseline training can omit kernel checks.")
        elif episode["digest"] != permit.candidate_digest:
            raise TrainingHalt("The dispatch kernel differs from the pinned candidate.")
        permit.consume(tool["id"], arguments, invocation_id)
        if any(path not in permit.credential_paths for path in credential_references(arguments)):
            raise TrainingHalt("A credential reference occurs outside its declared field.")
        validate_dispatch_arguments(arguments, tool["input_schema"], permit.credential_paths)
        connection = await self.store.connection(run["task_id"], UUID(tool["connection_id"]))
        async with self.store.pool.connection() as db:
            resolved = await self.credentials.resolve(db, run["id"], connection["id"], arguments)
        verify_transport_arguments(arguments, resolved, permit.credential_paths)
        validate_json(resolved, tool["input_schema"])
        call_id, raw, data = None, None, None
        external_status, sanitized = None, False
        try:
            async with asyncio.timeout(self.settings.surface_tool_timeout):
                async with self.connections.session(connection) as client:
                    native = {t.name: t for t in await self.connections.catalog(client)}.get(
                        tool["name"]
                    )
                    if (
                        not native
                        or native.input_schema != tool["input_schema"]
                        or native.output_schema != tool["output_schema"]
                        or (native.description or "") != tool["description"]
                        or (
                            native.annotations.model_dump(mode="json")
                            if native.annotations
                            else None
                        )
                        != tool["annotations"]
                    ):
                        raise TrainingHalt("The MCP tool contract changed before dispatch.")
                    call_id = await self._reserve(
                        run["id"],
                        episode_id,
                        "mcp",
                        {
                            "tool_id": tool["id"],
                            "arguments": arguments,
                            "invocation_id": invocation_id,
                        },
                    )
                    response = await client.session.send_request(
                        mcp_types.CallToolRequest(
                            params=mcp_types.CallToolRequestParams(
                                name=tool["name"], arguments=resolved
                            )
                        ),
                        mcp_types.CallToolResult,
                        request_read_timeout_seconds=self.settings.surface_tool_timeout,
                    )
                    external_status = "unknown" if response.is_error else "succeeded"
                    raw = response.model_dump(mode="json", by_alias=True)
                    data = response.structured_content
                    if data is None:
                        texts = [c.text for c in response.content if c.type == "text"]
                        if len(texts) == 1:
                            try:
                                data = json.loads(texts[0])
                            except ValueError:
                                data = {"text": texts[0]}
                    validation_error = None
                    if not response.is_error and tool["output_schema"] is not None:
                        try:
                            validate_json(data, tool["output_schema"])
                        except ValueError as error:
                            validation_error = str(error)
                    async with self.store.pool.connection() as db:
                        data = await self.credentials.capture(db, run["id"], connection["id"], data)
                        raw = await self.credentials.scrub(db, run["id"], raw)
                        data = await self.credentials.scrub(db, run["id"], data)
                    raw, data = redact(raw), redact(data)
                    sanitized = True
                    result = {
                        "status": external_status,
                        "dispatched": True,
                        "raw": raw,
                        "data": data,
                        "error": "tool_error" if response.is_error else None,
                        "coverage": "unknown",
                        "validation_error": validation_error,
                    }
                    await self._finish(call_id, result["status"], result)
                    return result
        except asyncio.CancelledError:
            if call_id:
                await self._finish(
                    call_id,
                    external_status or "unknown",
                    {
                        "error": "interrupted",
                        "dispatched": True,
                        "raw": raw if sanitized else None,
                        "data": data if sanitized else None,
                        "validation_error": "Response processing was interrupted.",
                    },
                )
            raise
        except TrainingHalt:
            raise
        except Exception:
            status = external_status or ("unknown" if call_id else "failed")
            result = {
                "status": status,
                "dispatched": call_id is not None,
                "raw": raw if sanitized else None,
                "data": data if sanitized else None,
                "error": "invalid_tool_result" if raw is not None else "transport_error",
                "coverage": "unknown",
                "validation_error": "Response processing failed." if external_status else None,
            }
            if call_id:
                await self._finish(call_id, status, result)
            return result

    async def _prepare(self, run, case, episode_index):
        if run["mode"] == "inference":
            return "current-state"
        if self.prepare_environment:
            prepared = await self.prepare_environment(run, case, episode_index)
            if prepared:
                return prepared
        if run["environment_ref"] == "stable":
            return "trainer-declared-stable-state"
        if episode_index == 0:
            return run["environment_ref"] or "initial-state"
        raise TrainingHalt(
            "A comparable prepared environment is unavailable. No repeated calls were dispatched."
        )

    async def _episode(self, run, case, stage, round_index, candidate_row=None):
        from oak.training_evaluation import evaluate_task
        from oak.training_runner import run_episode

        episode_id = uuid4()
        candidate = Candidate.model_validate(candidate_row["payload"]) if candidate_row else None
        await self.store.all(
            "INSERT INTO training_episodes(id,run_id,case_id,case_snapshot,candidate_id,"
            "round_index,"
            "stage,status,environment_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,'running',%s) RETURNING id",
            (
                episode_id,
                run["id"],
                case["id"],
                Jsonb(case),
                candidate_row["id"] if candidate_row else None,
                round_index,
                stage,
                None,
            ),
        )
        try:
            prepared = await self._prepare(run, case, round_index)
            if round_index > 0:
                baseline = await self.store.one(
                    "SELECT environment_ref FROM training_episodes WHERE run_id=%s "
                    "AND case_id=%s AND round_index=0",
                    (run["id"], case["id"]),
                )
                if not baseline or baseline["environment_ref"] != prepared:
                    raise TrainingHalt("The prepared state does not match this case's baseline.")
        except TrainingHalt as exc:
            await self.store.all(
                "UPDATE training_episodes SET status='blocked',result=%s,finished_at=now() "
                "WHERE id=%s RETURNING id",
                (Jsonb({"status": "blocked", "reason": str(exc)}), episode_id),
            )
            raise
        await self.store.all(
            "UPDATE training_episodes SET environment_ref=%s WHERE id=%s RETURNING id",
            (prepared, episode_id),
        )
        selected = [t for t in run["inputs"]["tools"] if t["id"] in case["tool_ids"]]

        async def dispatch(tool, arguments, invocation_id, *, permit):
            if tool["id"] not in case["tool_ids"]:
                raise TrainingHalt("The operation is not selected for this case.")
            return await self._dispatch(
                run, episode_id, tool, arguments, invocation_id, permit=permit
            )

        async def emit(kind, data):
            return await self.emit(run["id"], kind, data, episode_id)

        async def reserve(kind, request):
            return await self._reserve(run["id"], episode_id, kind, request)

        async def should_stop():
            return await self._stopped(run["id"])

        await emit(
            "episode_started", {"stage": stage, "case_id": case["id"], "environment_ref": prepared}
        )
        request_snapshot = None
        if candidate is not None:
            request_snapshot = await prepare_request(
                candidate,
                case["query"],
                {"task": run["inputs"]["task"], "agent": run["inputs"]["agent"]},
                self._generate(run["id"], episode_id),
                emit,
            )
            await emit("request_prepared", request_snapshot)
        result = await run_episode(
            run_mode=run["mode"],
            stage=stage,
            request_snapshot=request_snapshot,
            case={**case, "task_boundaries": run["inputs"]},
            tools=selected,
            candidate=candidate,
            model=self.model,
            dispatch=dispatch,
            emit=emit,
            instructions=canonical(
                {"task": run["inputs"]["task"], "agent": run["inputs"]["agent"]}
            ),
            limits={
                **run["limits"],
                "input_tokens": self.settings.surface_input_tokens,
                "output_tokens": self.settings.surface_probe_output_tokens,
            },
            should_stop=should_stop,
            reserve=reserve,
            finish=self._finish,
        )
        async with self.store.pool.connection() as db:
            result = redact(
                await self.credentials.scrub(db, run["id"], snapshot(result)), preserve_schemas=True
            )
        await self.store.all(
            "UPDATE training_episodes SET result=%s,status='evaluating' WHERE id=%s RETURNING id",
            (Jsonb(result), episode_id),
        )
        if stage == "inference":
            await self.store.all(
                "UPDATE training_episodes SET status=%s,finished_at=now() WHERE id=%s RETURNING id",
                ("completed" if result["status"] == "complete" else result["status"], episode_id),
            )
            await emit("inference_finished", {"status": result["status"]})
            return {
                "id": str(episode_id),
                "case_id": case["id"],
                "case_snapshot": case,
                "stage": stage,
                "result": result,
                "evaluation": None,
            }
        refs = [
            {"source": "artifact", "id": str(episode_id), "path": "/result/" + key}
            for key in (
                "final_output",
                "trace",
                "observations",
                "graph",
                "function_calls",
                "request_snapshot",
                "dispatch_decisions",
                "graph_processing",
            )
            if key in result
        ]
        context = {
            "inputs": run["inputs"],
            "case": case,
            "episode": result,
            "result": result,
            "evidence_refs": refs,
        }
        try:
            evaluation = snapshot(
                await evaluate_task(self.model, context, self._generate(run["id"], episode_id))
            )
        except TrainingHalt:
            raise
        except Exception:
            evaluation = {
                "status": "error",
                "reason": "The evaluator could not complete.",
                "evidence_refs": [],
            }
        if result.get("unresolved_outcomes") and evaluation.get("status") == "passed":
            evaluation = {
                "status": "inconclusive",
                "reason": "An operation outcome is unresolved.",
                "evidence_refs": refs,
            }
        await self.store.all(
            "UPDATE training_episodes SET evaluation=%s,status='completed',finished_at=now() "
            "WHERE id=%s RETURNING id",
            (Jsonb(evaluation), episode_id),
        )
        await emit("episode_evaluated", evaluation)
        return {
            "id": str(episode_id),
            "case_id": case["id"],
            "case_snapshot": case,
            "stage": stage,
            "result": result,
            "evaluation": evaluation,
        }

    async def _candidate(self, run_id, candidate, patch=None):
        row = await self.store.one(
            "INSERT INTO training_candidates(id,run_id,digest,payload,patch,status) "
            "VALUES (%s,%s,%s,%s,%s,'provisional') ON CONFLICT(run_id,digest) "
            "DO UPDATE SET digest=EXCLUDED.digest RETURNING *",
            (
                uuid4(),
                run_id,
                candidate_digest(candidate),
                Jsonb(snapshot(candidate)),
                Jsonb(snapshot(patch)) if patch else None,
            ),
        )
        await self.emit(
            run_id, "candidate_created", {"candidate_id": str(row["id"]), "digest": row["digest"]}
        )
        return row

    async def _decision(self, row, status, reason, **data):
        previous = await self.store.one(
            "SELECT decision FROM training_candidates WHERE id=%s", (row["id"],)
        )
        decision = {**(previous or {}).get("decision", {}), "reason": reason, **data}
        await self.store.all(
            "UPDATE training_candidates SET status=%s,decision=%s WHERE id=%s RETURNING id",
            (status, Jsonb(decision), row["id"]),
        )
        await self.emit(
            row["run_id"],
            "candidate_decision",
            {"candidate_id": str(row["id"]), "status": status, **decision},
        )

    async def _context(self, run):
        artifacts = await self.store.all(
            "SELECT kind,payload FROM discovery_artifacts WHERE run_id=%s "
            "AND kind IN ('requirements','schema','source_access') ORDER BY created_at",
            (run["discovery_run_id"],),
        )
        discovery = {a["kind"]: a["payload"] for a in artifacts}
        return {
            "inputs": run["inputs"],
            "original_input_digest": run["input_digest"],
            "discovery": discovery,
            "cases": run["cases"],
            "allowed_tool_ids": [t["id"] for t in run["inputs"]["tools"]],
            "requirement_ids": [r["id"] for r in discovery["requirements"]["requirements"]],
        }

    @staticmethod
    def _passes(episodes):
        return {e["case_id"] for e in episodes if e["evaluation"].get("status") == "passed"}

    async def _run(self, run_id):
        try:
            run = await self.store.one("SELECT * FROM training_runs WHERE id=%s", (run_id,))
            async with asyncio.timeout(run["limits"]["active_seconds"]):
                if run["mode"] == "inference":
                    candidate = await self.store.one(
                        "SELECT c.*,r.input_digest FROM training_candidates c "
                        "JOIN training_runs r ON r.id=c.run_id WHERE c.id=%s",
                        (run["accepted_candidate_id"],),
                    )
                    async with self.store.pool.connection() as db:
                        current_inputs = await self.discoveries._inputs(
                            db, run["task_id"], run["agent_id"]
                        )
                    eligibility = await self._eligibility(candidate, current_inputs)
                    if not eligibility["inference_ready"]:
                        raise TrainingHalt(eligibility["inference_message"])
                    episode = await self._episode(run, run["cases"][0], "inference", 0, candidate)
                    await self._set(
                        run_id,
                        stage="finished",
                        status="completed"
                        if episode["result"]["status"] == "complete"
                        else "stopped",
                        message="Inference ended with the fixed kernel. Inspect the result.",
                    )
                else:
                    await self._train(run)
        except asyncio.CancelledError:
            async with self.store.pool.connection() as db:
                await self._interrupt(db, run_id)
                await db.execute(
                    "UPDATE training_runs SET status=CASE WHEN status='stopping' THEN 'stopped' "
                    "ELSE 'interrupted' END,stage='finished',message='Execution stopped. "
                    "No call was repeated.',updated_at=now() WHERE id=%s",
                    (run_id,),
                )
        except (TrainingHalt, TimeoutError) as exc:
            await self._set(
                run_id,
                stage="finished",
                status="stopped",
                message=str(exc) or "The run time limit was reached.",
            )
            await self.emit(run_id, "run_stopped", {"message": str(exc)})
        except Exception:
            logger.exception("Training failed for run %s", run_id)
            await self._set(
                run_id,
                stage="finished",
                status="failed",
                message="Training could not complete. Inspect the saved events.",
            )
            await self.emit(run_id, "run_failed", {"message": "Training could not complete."})
        finally:
            async with self.store.pool.connection() as db:
                await db.execute(
                    "UPDATE training_episodes SET status='interrupted',finished_at=now() "
                    "WHERE run_id=%s AND status IN ('running','evaluating')",
                    (run_id,),
                )
                await db.execute(
                    "UPDATE training_calls SET status='unknown',finished_at=now() "
                    "WHERE run_id=%s AND status='dispatched'",
                    (run_id,),
                )
            self.jobs.pop(str(run_id), None)

    async def _validation_event(self, run, row, kind, report, validation):
        event_id = await self.emit(
            run["id"],
            "kernel_validation",
            {
                "candidate_id": str(row["id"]),
                "candidate_digest": row["digest"],
                "validation_kind": kind,
                "report": report,
            },
        )
        validation[kind + "_event_id"] = event_id
        await self._decision(
            row, "provisional", "Candidate validation is in progress.", validation=validation
        )
        return event_id

    async def _reuse_candidate(self, run, context):
        if not run.get("agent_id"):
            return None
        from oak.acquisition import validate_access
        from oak.repair_executor import validate_candidate

        rows = await self.store.all(
            "SELECT c.* FROM training_candidates c JOIN training_runs r ON r.id=c.run_id "
            "WHERE r.agent_id=%s AND r.input_digest=%s AND c.status='accepted' "
            "ORDER BY c.created_at DESC,c.id DESC",
            (run["agent_id"], run["input_digest"]),
        )
        for row in rows:
            try:
                candidate = Candidate.model_validate(row["payload"])
                if (
                    candidate.version != "oak.candidate.v3"
                    or candidate.original_input_digest != run["input_digest"]
                ):
                    continue
                if candidate_digest(candidate) != row["digest"]:
                    continue
                if validate_candidate(
                    candidate, context["allowed_tool_ids"], context["requirement_ids"]
                ):
                    continue
                validate_access(candidate, required=True)
            except (ValueError, KeyError):
                continue
            await self.emit(
                run["id"],
                "harness_base",
                {
                    "source_candidate_id": str(row["id"]),
                    "source_run_id": str(row["run_id"]),
                    "candidate_digest": row["digest"],
                    "message": "Revalidate this saved candidate before acceptance.",
                },
            )
            return candidate
        return None

    async def _train(self, run):
        from oak.definition_checks import check_definitions, proposal_key
        from oak.kernel_validation import (
            build_validation_suite,
            check_refs,
            replay_validation_suite,
            review_coverage,
            validate_suite_coverage,
        )
        from oak.ontology_verification import verify_candidate
        from oak.repair_patch import apply_targeted_patch, canonical_digest
        from oak.repair_review import (
            RepairReview,
            _context_key,
            check_reviewed_patch,
            review_repair,
        )
        from oak.training_construction import (
            _validate_construction,
            construct_candidate,
            execution_evidence,
            propose_repair,
        )

        context = await self._context(run)
        initial = await self._reuse_candidate(run, context)
        rejected_proposals = set()
        if run.get("agent_id"):
            prior_rejections = await self.store.all(
                "SELECT e.data FROM training_events e JOIN training_runs r ON r.id=e.run_id "
                "WHERE r.agent_id=%s AND r.input_digest=%s AND e.kind='proposal_rejected'",
                (run["agent_id"], run["input_digest"]),
            )
            rejected_proposals = {r["data"].get("proposal_key") for r in prior_rejections}
        episodes = []
        for case in run["cases"]:
            episodes.append(await self._episode(run, case, "baseline", 0))
            if episodes[-1]["result"].get("unresolved_outcomes"):
                raise TrainingHalt("An outcome is unresolved. Training did not repeat the case.")
        passed = self._passes(episodes)
        generate = self._generate(run["id"])
        await self._set(run["id"], stage="construction")

        async def invalid_proposal(proposal, errors):
            event_id = await self.emit(
                run["id"],
                "kernel_validation",
                {
                    "candidate_digest": canonical_digest(proposal),
                    "candidate_id": None,
                    "validation_kind": "structural",
                    "report": {"status": "invalid", "errors": errors, "proposal": proposal},
                },
            )
            return {"source": "artifact", "id": event_id, "path": "/report"}

        candidate = await construct_candidate(
            self.model,
            {**context, "episodes": episodes},
            generate,
            validate_output=False,
            initial=initial,
            on_invalid=invalid_proposal,
            on_progress=lambda data: self.emit(run["id"], "construction_progress", data),
        )
        suite = None
        fixed_suite_review = None
        correction = None
        pending_proposal = None

        async def reject_pending():
            nonlocal pending_proposal
            if pending_proposal is not None:
                rejected_proposals.add(pending_proposal["proposal_key"])
                await self.emit(
                    run["id"],
                    "proposal_rejected",
                    {
                        **pending_proposal,
                        "reason": "The proposed candidate failed acceptance checks.",
                        "validation": correction,
                    },
                )
                pending_proposal = None

        for round_index in range(1, run["limits"]["max_rounds"] + 1):
            patch = None
            if correction is not None:
                await reject_pending()
                await self._set(run["id"], stage="repair")
                failed = correction.get("failed_episodes", [])
                target = failed[0]["case_snapshot"] if failed else None
                allowed_refs = [
                    correction["evidence_ref"],
                    {"source": "input", "id": "surface", "path": ""},
                ]
                allowed_refs.extend(
                    {"source": "artifact", "id": str(e["id"]), "path": "/result"} for e in episodes
                )
                review_context = {
                    **context,
                    "episodes": episodes,
                    "candidate": snapshot(candidate),
                    "candidate_digest": candidate_digest(candidate),
                    "target_case": target,
                    "construction_correction": correction,
                    "fixed_validation_suite": snapshot(suite) if suite else None,
                    "evidence_refs": allowed_refs,
                }
                review = None
                for failure in failed or [None]:
                    review_context["target_case"] = failure["case_snapshot"] if failure else None
                    if failure:
                        review_context["construction_correction"] = {
                            **correction,
                            "failed_episodes": [failure],
                        }
                    try:
                        review = await review_repair(
                            candidate, review_context, generate, execution_evidence
                        )
                    except ValueError as error:
                        review = RepairReview(
                            candidate_digest=candidate_digest(candidate),
                            evidence_digest=_context_key(review_context),
                            decision="unresolved",
                            verification="rejected_review",
                            reason="The review could not be verified: " + str(error),
                        )
                    await self.emit(run["id"], "repair_review", snapshot(review))
                    if review.verified:
                        break
                    await self.emit(
                        run["id"],
                        "harness_unchanged",
                        {
                            "candidate_digest": candidate_digest(candidate),
                            "decision": review.decision,
                            "reason": review.reason,
                            "case_id": str(failure["case_id"]) if failure else None,
                        },
                    )
                if not review.verified:
                    raise TrainingHalt("The harness is unchanged. " + review.reason)

                async def rejected_patch(proposal, reason):
                    await self.emit(
                        run["id"],
                        "proposal_rejected",
                        {
                            "proposal_key": proposal_key(
                                candidate, proposal, review.evidence_digest
                            ),
                            "candidate_digest": candidate_digest(candidate),
                            "evidence_digest": review.evidence_digest,
                            "patch": snapshot(proposal),
                            "reason": reason,
                        },
                    )

                try:
                    patch = await propose_repair(
                        self.model,
                        {**review_context, "repair_review": snapshot(review)},
                        generate,
                        on_evidence=allowed_refs.append,
                        on_rejected=rejected_patch,
                    )
                except ValueError as error:
                    raise TrainingHalt("The harness is unchanged. " + str(error)) from error
                if patch is None:
                    await self.emit(
                        run["id"],
                        "harness_unchanged",
                        {
                            "candidate_digest": candidate_digest(candidate),
                            "reason": "The review produced no supported change.",
                        },
                    )
                    raise TrainingHalt("No supported declaration repair was available.")
                key = proposal_key(candidate, patch, review.evidence_digest)
                try:
                    check_refs(patch.evidence_refs, allowed_refs)
                    if patch.fault.sample_id:
                        if patch.fault.sample_id not in {str(e["case_id"]) for e in failed}:
                            raise ValueError("The repair does not cite a failed saved case.")
                    elif patch.fault.validation_event_id != correction["evidence_ref"]["id"]:
                        raise ValueError(
                            "The repair does not cite its immutable validation report."
                        )
                    if key in rejected_proposals:
                        raise ValueError(
                            "This proposal was rejected against the same definitions and evidence."
                        )
                    application = apply_targeted_patch(
                        candidate,
                        patch,
                        allowed_tool_ids=context["allowed_tool_ids"],
                        requirement_ids=context["requirement_ids"],
                    )
                    constant_sources = check_definitions(application.candidate, before=candidate)
                    check_reviewed_patch(
                        review, patch, candidate, application.candidate, review_context
                    )
                except ValueError as error:
                    await self.emit(
                        run["id"],
                        "proposal_rejected",
                        {
                            "proposal_key": key,
                            "candidate_digest": candidate_digest(candidate),
                            "evidence_digest": review.evidence_digest,
                            "patch": snapshot(patch),
                            "reason": str(error),
                        },
                    )
                    raise TrainingHalt("The harness is unchanged. " + str(error)) from error
                pending_proposal = {
                    "proposal_key": key,
                    "candidate_digest": candidate_digest(candidate),
                    "evidence_digest": review.evidence_digest,
                    "patch": snapshot(patch),
                }
                candidate = application.candidate
                await self.emit(run["id"], "definition_sources", {"constants": constant_sources})
                await self.emit(run["id"], "repair_applied", snapshot(application.receipt))
            row = await self._candidate(run["id"], candidate, patch)
            validation = {"versions": VERSIONS}
            refs = [{"source": "input", "id": "surface", "path": ""}]
            refs += [
                {"source": "artifact", "id": str(e["id"]), "path": "/result"} for e in episodes
            ]
            try:
                _validate_construction(candidate, {**context, "episodes": episodes})
                sources = check_definitions(candidate, before=initial)
                await self.emit(
                    run["id"],
                    "definition_sources",
                    {"candidate_digest": candidate_digest(candidate), "constants": sources},
                )
                issues = []
            except ValueError as error:
                issues = [str(error)]
            if issues:
                report = {"status": "invalid", "errors": issues}
                event_id = await self._validation_event(run, row, "structural", report, validation)
                correction = {
                    "report": report,
                    "validation_kind": "structural",
                    "evidence_ref": {"source": "artifact", "id": event_id, "path": "/report"},
                }
                await self._decision(
                    row,
                    "rejected",
                    "The typed declarations failed validation.",
                    validation=validation,
                )
                continue
            remaining = (
                run["limits"]["active_seconds"]
                - (datetime.now(UTC) - run["created_at"]).total_seconds()
            )
            report = await verify_candidate(
                candidate, timeout=min(30, max(0.1, remaining)), heap_mb=128
            )
            event_id = await self._validation_event(run, row, "formal", report, validation)
            refs.append({"source": "artifact", "id": event_id, "path": "/report"})
            if report["status"] == "infrastructure_error":
                raise TrainingHalt(
                    "Formal verification is unavailable. Inspect the saved infrastructure report."
                )
            if report["status"] != "passed":
                correction = {
                    "report": report,
                    "evidence_ref": refs[-1],
                    "validation_kind": "formal",
                }
                await self._decision(
                    row, "rejected", "The schema failed formal verification.", validation=validation
                )
                continue
            evidence_context = {
                **context,
                "candidate": snapshot(candidate),
                "episodes": episodes,
                "evidence_refs": refs,
            }
            coverage = await review_coverage(evidence_context, generate)
            coverage_event = await self._validation_event(
                run, row, "coverage", coverage, validation
            )
            refs.append({"source": "artifact", "id": coverage_event, "path": "/report"})
            if coverage["status"] != "passed":
                correction = {
                    "report": coverage,
                    "evidence_ref": refs[-1],
                    "validation_kind": "coverage",
                }
                await self._decision(
                    row,
                    "rejected",
                    "Original requirement coverage was not established.",
                    validation=validation,
                )
                continue
            extend_suite = False
            if suite is not None:
                try:
                    validate_suite_coverage(suite, candidate)
                except ValueError:
                    extend_suite = True
            if suite is None or extend_suite:
                try:
                    suite, fixed_suite_review = await build_validation_suite(
                        evidence_context, generate, existing=suite
                    )
                except ValueError as error:
                    raise TrainingHalt(
                        "The fixed validation cases are unsupported: " + str(error)
                    ) from error
                await self.emit(
                    run["id"],
                    "validation_suite_extended" if extend_suite else "validation_suite_fixed",
                    {
                        "suite": snapshot(suite),
                        "digest": digest(snapshot(suite)),
                        "review": fixed_suite_review,
                    },
                )

            async def emit(kind, data):
                return await self.emit(run["id"], kind, data)

            checks = await replay_validation_suite(candidate, suite, run["inputs"], generate, emit)
            probe_event = await self._validation_event(
                run, row, "counterexamples", checks, validation
            )
            refs.append({"source": "artifact", "id": probe_event, "path": "/report"})
            if checks["status"] != "passed":
                correction = {
                    "report": checks,
                    "evidence_ref": refs[-1],
                    "validation_kind": "counterexamples",
                }
                await self._decision(
                    row, "rejected", "The fixed validation cases failed.", validation=validation
                )
                continue
            await self._set(run["id"], stage="harness")
            results = []
            for case in run["cases"]:
                results.append(await self._episode(run, case, "harness", round_index, row))
                if results[-1]["result"].get("unresolved_outcomes"):
                    raise TrainingHalt(
                        "An outcome is unresolved. Training did not repeat the case."
                    )
            episodes.extend(results)
            current_passes = self._passes(results)
            executed_functions = {f for e in results for f in e["result"].get("function_ids", [])}
            executed_bindings = set()
            for episode in results:
                succeeded = {
                    o["invocation_id"]
                    for o in episode["result"].get("observations", [])
                    if o["status"] == "succeeded"
                }
                executed_bindings.update(
                    d["binding_id"]
                    for d in episode["result"].get("dispatch_decisions", [])
                    if d.get("status") == "allowed"
                    and d["invocation_id"] in succeeded
                    and "binding_id" in d
                )
            uncovered_functions = {f.id for f in candidate.functions} - executed_functions
            uncovered_bindings = {b.id for b in candidate.operation_bindings} - executed_bindings
            if (
                len(current_passes) == len(run["cases"])
                and not uncovered_functions
                and not uncovered_bindings
            ):
                await self._decision(
                    row,
                    "accepted",
                    "All saved cases and kernel checks passed.",
                    validation=validation,
                    evaluation={
                        "version": EVALUATOR_VERSION,
                        "coverage": coverage,
                        "task_outcomes": [
                            {
                                "case_id": e["case_id"],
                                "episode_id": e["id"],
                                "report": e["evaluation"],
                            }
                            for e in results
                        ],
                    },
                )
                await self.store.all(
                    "UPDATE training_runs SET accepted_candidate_id=%s WHERE id=%s RETURNING id",
                    (row["id"], run["id"]),
                )
                await self._set(
                    run["id"],
                    stage="finished",
                    status="completed",
                    message="The verified kernel is ready for inference.",
                )
                return
            correction = {
                "failed_episodes": [
                    e for e in results if e["evaluation"].get("status") == "failed"
                ],
                "inconclusive_episodes": [
                    e for e in results if e["evaluation"].get("status") == "inconclusive"
                ],
                "error_episodes": [e for e in results if e["evaluation"].get("status") == "error"],
                "regressions": sorted(passed - current_passes),
                "unexecuted_functions": sorted(uncovered_functions),
                "unexecuted_bindings": sorted(uncovered_bindings),
            }
            report = {"status": "failed", **correction}
            correction["report"] = report
            correction["validation_kind"] = "execution"
            event_id = await self._validation_event(run, row, "execution", report, validation)
            correction["evidence_ref"] = {"source": "artifact", "id": event_id, "path": "/report"}
            passed |= current_passes
            await self._decision(
                row,
                "rejected",
                "The candidate did not pass all acceptance checks.",
                validation=validation,
                **{k: v for k, v in correction.items() if k != "failed_episodes"},
            )
        await reject_pending()
        await self._set(
            run["id"],
            stage="finished",
            status="completed",
            message="The round limit was reached. No kernel was accepted.",
        )
