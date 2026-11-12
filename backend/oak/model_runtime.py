"""Save connection checks and enforce their shared cost allowance."""

import asyncio
import hashlib
import json
import logging
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from google.genai import __version__ as sdk_version
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from oak.db import Store
from oak.model_client import INPUT_TOKEN_LIMIT, PROBLEMS, GeminiClient, ModelFailure
from oak.schemas import ModelCheck, ModelRuntime

logger = logging.getLogger(__name__)
NANOS_PER_USD = 1_000_000_000
CHECK_INSTRUCTIONS = 'Return {"status":"ok"} to confirm this connection check.'
CHECK_INPUT = {"check": "Oak model connection"}


class ConnectionReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


class ModelChecks:
    def __init__(self, store: Store, client=None):
        self.store, self.settings = store, store.settings
        self.client = client if client is not None else GeminiClient(self.settings)
        self.jobs: dict[UUID, asyncio.Task] = {}
        self.digest = hashlib.sha256(
            json.dumps(
                {
                    "project": self.settings.gemini_project,
                    "location": self.settings.gemini_location,
                    "model": self.settings.gemini_model,
                    "timeout": self.settings.gemini_timeout,
                    "output_limit": self.settings.gemini_max_output_tokens,
                    "sdk": sdk_version,
                    "check_version": 2,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    @property
    def budget(self):
        return int(self.settings.gemini_check_budget_usd * Decimal(NANOS_PER_USD))

    @property
    def reservation(self):
        # Use the published standard rates, above the 2026 introductory rates.
        # Source: https://cloud.google.com/model-garden/pricing (2026-11-08).
        return INPUT_TOKEN_LIMIT * 1500 + self.settings.gemini_max_output_tokens * 7500

    def configuration_problem(self):
        if not self.settings.gemini_project.strip():
            return "Set OAK_GEMINI_PROJECT in the backend configuration."
        if (
            self.settings.gemini_model != "gemini-3.8-flash"
            or self.settings.gemini_location != "global"
        ):
            return "Connection checks require gemini-3.8-flash in global with verified token rates."
        return None

    async def recover_interrupted(self):
        # The application runs one backend worker. Keep interrupted cost reservations.
        await self.store.all(
            "UPDATE model_runtime_checks SET status='check_failed',error_code='interrupted',"
            "finished_at=now() WHERE status='checking' RETURNING id"
        )

    async def snapshot(self):
        async with self.store.pool.connection() as db:
            row = await (
                await db.execute(
                    "SELECT *,sum(accounted_nanos) OVER () AS total_nanos "
                    "FROM model_runtime_checks ORDER BY started_at DESC LIMIT 1"
                )
            ).fetchone()
        accounted = row["total_nanos"] if row else 0
        remaining = max(0, self.budget - accounted)
        problem = self.configuration_problem()
        outdated = bool(row and row["config_digest"] != self.digest)
        status = "not_configured" if problem else "not_checked"
        last = None
        if row:
            message, recovery = PROBLEMS.get(row["error_code"], (None, None))
            last = ModelCheck(
                **{
                    key: row[key]
                    for key in (
                        "id",
                        "model",
                        "status",
                        "started_at",
                        "finished_at",
                        "duration_ms",
                        "error_code",
                        "usage",
                    )
                },
                message=message,
                recovery=recovery,
                accounted_usd=row["accounted_nanos"] / NANOS_PER_USD,
                usage_known=row["usage"] is not None,
            )
            if not problem and not outdated:
                status = row["status"]
        blocked = problem
        if status == "checking":
            blocked = "A connection check is in progress."
        elif not blocked and remaining < self.reservation:
            blocked = "The remaining connection-check allowance cannot fund another check."
        return ModelRuntime(
            model=self.settings.gemini_model,
            location=self.settings.gemini_location,
            configured=problem is None,
            status=status,
            outdated=outdated,
            last_check=last,
            can_check=blocked is None,
            blocked_reason=blocked,
            budget_usd=self.budget / NANOS_PER_USD,
            accounted_usd=accounted / NANOS_PER_USD,
            remaining_usd=remaining / NANOS_PER_USD,
        )

    async def start(self, request_id: UUID):
        problem = self.configuration_problem()
        if problem:
            raise HTTPException(409, problem)
        created = False
        async with self.store.pool.connection() as db:
            # Serialize duplicate checks and cost reservations in the same transaction.
            await db.execute("SELECT pg_advisory_xact_lock(183428)")
            previous = await (
                await db.execute("SELECT * FROM model_runtime_checks WHERE id=%s", (request_id,))
            ).fetchone()
            if previous:
                if previous["config_digest"] != self.digest:
                    raise HTTPException(409, "This request belongs to an earlier configuration.")
            else:
                active = await (
                    await db.execute("SELECT id FROM model_runtime_checks WHERE status='checking'")
                ).fetchone()
                if active:
                    raise HTTPException(
                        409, "A connection check is in progress. Refresh its status."
                    )
                total = await (
                    await db.execute(
                        "SELECT coalesce(sum(accounted_nanos),0) AS used FROM model_runtime_checks"
                    )
                ).fetchone()
                if total["used"] + self.reservation > self.budget:
                    raise HTTPException(409, "The connection-check allowance is exhausted.")
                introductory = datetime.now(UTC).date() <= date(2026, 12, 31)
                input_rate, output_rate = (750, 3750) if introductory else (1500, 7500)
                await db.execute(
                    "INSERT INTO model_runtime_checks "
                    "(id,config_digest,model,status,reserved_nanos,accounted_nanos,"
                    "input_rate_nanos,output_rate_nanos) VALUES (%s,%s,%s,'checking',%s,%s,%s,%s)",
                    (
                        request_id,
                        self.digest,
                        self.settings.gemini_model,
                        self.reservation,
                        self.reservation,
                        input_rate,
                        output_rate,
                    ),
                )
                created = True
        if created:
            job = asyncio.create_task(self._run(request_id))
            self.jobs[request_id] = job
            job.add_done_callback(lambda _: self.jobs.pop(request_id, None))
        return await self.snapshot()

    async def _run(self, request_id):
        started = time.monotonic()
        usage, error_code, status = None, None, "connected"
        try:
            result = await self.client.generate(CHECK_INSTRUCTIONS, CHECK_INPUT, ConnectionReply)
            usage = result.usage
        except ModelFailure as exc:
            status, error_code, usage = "check_failed", exc.code, exc.usage
        except asyncio.CancelledError:
            status, error_code = "check_failed", "interrupted"
        except Exception:
            # Do not expose provider messages or credentials.
            logger.warning("Model connection check failed.")
            status, error_code = "check_failed", "provider_error"
        await self.store.all(
            "UPDATE model_runtime_checks SET status=%s,error_code=%s,usage=%s,"
            "finished_at=now(),duration_ms=%s,accounted_nanos=CASE WHEN %s THEN "
            "%s*input_rate_nanos + %s*output_rate_nanos ELSE reserved_nanos END "
            "WHERE id=%s RETURNING id",
            (
                status,
                error_code,
                Jsonb(usage.model_dump()) if usage else None,
                round((time.monotonic() - started) * 1000),
                usage is not None,
                usage.input_tokens if usage else 0,
                usage.output_tokens if usage else 0,
                request_id,
            ),
        )

    async def close(self):
        jobs = list(self.jobs.values())
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
