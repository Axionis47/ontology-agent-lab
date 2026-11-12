"""Reserve every model call before dispatch. Retain unknown usage."""

import asyncio
from dataclasses import asdict
from uuid import uuid4

from oak.model_client import ModelFailure

from .sources import now, save

NANOS = 1_000_000_000
PHASE_CAPS = {
    "discovery": 2 * NANOS,
    "training": 4 * NANOS,
    **{
        f"{name}_{mode}": NANOS // 2
        for name in ("deep", "wide", "many_entities", "many_relationships")
        for mode in ("baseline", "ontology")
    },
}


def cost(usage):
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump(mode="json")
    if not isinstance(usage, dict) or not all(
        k in usage for k in ("input_tokens", "output_tokens")
    ):
        return None
    return max(0, usage["input_tokens"]) * 1500 + max(0, usage["output_tokens"]) * 7500


class BudgetModel:
    def __init__(self, model, root):
        self.model, self.root = model, root
        self.phase = "discovery"
        self.entries = []
        self.lock = asyncio.Lock()
        if (root / "budget.json").exists():
            raise ValueError("This run already has a budget ledger. Use a new output directory.")
        self.persist()

    def persist(self):
        save(
            self.root / "budget.json",
            {
                "limit_usd": 10,
                "phase_caps_nanos": PHASE_CAPS,
                "accounted_usd": self.total() / NANOS,
                "entries": self.entries,
                "accounting": "Conservative Oak rates: input 1500 and output 7500 nanodollars per "
                "token. Output usage includes reasoning. Unknown usage retains the "
                "reservation. This is not a provider invoice.",
            },
        )

    def total(self, phase=None):
        return sum(
            e["accounted_nanos"] for e in self.entries if phase is None or e["phase"] == phase
        )

    async def invoke(self, method, args, kwargs, request):
        limits = kwargs["limits"]
        reservation = limits.input_tokens * 1500 + limits.output_tokens * 7500
        async with self.lock:
            if self.phase not in PHASE_CAPS:
                raise ValueError("Unknown budget phase.")
            if (
                self.total(self.phase) + reservation > PHASE_CAPS[self.phase]
                or self.total() + reservation > 10 * NANOS
            ):
                raise RuntimeError(
                    f"The {self.phase} cost limit stopped this call before dispatch."
                )
            entry = {
                "id": str(uuid4()),
                "phase": self.phase,
                "method": method,
                "started_at": now(),
                "status": "unknown",
                "reserved_nanos": reservation,
                "accounted_nanos": reservation,
            }
            self.entries.append(entry)
            request_path = self.root / "model-calls" / f"{entry['id']}.json"
            record = {"entry": entry, "limits": asdict(limits), "request": request}
            save(request_path, record)
            self.persist()
        try:
            result = await getattr(self.model, method)(*args, **kwargs)
            usage = result.get("usage") if isinstance(result, dict) else result.usage
            record["response"] = (
                result
                if isinstance(result, dict)
                else {
                    "data": result.data.model_dump(mode="json")
                    if hasattr(result.data, "model_dump")
                    else result.data,
                    "usage": usage.model_dump(mode="json") if usage is not None else None,
                    "request": result.request,
                }
            )
            entry["status"] = "succeeded"
            charged = cost(usage)
            if charged is not None:
                entry["accounted_nanos"] = charged
            return result
        except BaseException as exc:
            entry["status"] = "unknown" if isinstance(exc, asyncio.CancelledError) else "failed"
            record["error"] = str(exc)
            if isinstance(exc, ModelFailure):
                charged = cost(exc.usage)
                if charged is not None:
                    entry["accounted_nanos"] = charged
            raise
        finally:
            entry["finished_at"] = now()
            save(request_path, record)
            self.persist()

    async def turn(self, messages, tools, *, limits, instructions=""):
        return await self.invoke(
            "turn",
            (messages, tools),
            {"limits": limits, "instructions": instructions},
            {"messages": messages, "tools": tools, "instructions": instructions},
        )

    async def generate(self, instructions, data, response_schema, *, limits):
        return await self.invoke(
            "generate",
            (instructions, data, response_schema),
            {"limits": limits},
            {
                "instructions": instructions,
                "data": data,
                "response_schema": response_schema.model_json_schema(),
            },
        )
