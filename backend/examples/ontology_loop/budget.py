"""Append-only accounting for the authorized USD 40 Gemini experiment budget."""

import fcntl
import json
import time
import uuid
from pathlib import Path

from .run import GeminiModel

PRICE_SOURCE = "https://cloud.google.com/model-garden/pricing"
MODEL = "gemini-3.8-flash"
# Use the regular rates. They are twice the introductory rates on 2026-11-07.
INPUT_PER_MILLION = 1.50
OUTPUT_PER_MILLION = 7.50


def usage_cost(stats):
    """Count cached input at full price and include reasoning tokens."""
    if isinstance(stats, list):
        parts = [usage_cost(item) for item in stats]
        return None if any(item is None for item in parts) else sum(parts)
    models = stats.get("models", {}) if isinstance(stats, dict) else {}
    if not models:
        return None
    total = 0.0
    for name, data in models.items():
        if name != MODEL:
            return None
        tokens = data.get("tokens", {})
        inputs = tokens.get("prompt", tokens.get("input", 0))
        outputs = tokens.get("candidates", 0) + tokens.get("thoughts", 0)
        # Account for any unclassified tokens at the higher output rate.
        outputs = max(outputs, tokens.get("total", 0) - inputs)
        total += (inputs * INPUT_PER_MILLION + outputs * OUTPUT_PER_MILLION) / 1_000_000
    return total


class Budget:
    def __init__(self, path, limit=40.0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = min(float(limit), 40.0)

    def _transaction(self, operation):
        with self.path.open("a+") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            file.seek(0)
            events = [json.loads(line) for line in file if line.strip()]
            state = {"charged_usd": 0.0, "open": {}, "events": len(events)}
            for event in events:
                if event["type"] == "reserve":
                    state["open"][event["id"]] = event
                elif event["type"] == "settle":
                    state["open"].pop(event["id"], None)
                    state["charged_usd"] += event["charged_usd"]
                elif event["type"] == "verified_no_request":
                    state["charged_usd"] -= event["released_usd"]
                elif event["type"] == "usage_reconciliation":
                    state["charged_usd"] += event["charged_usd"] - event["previous_charge_usd"]
            state["reserved_usd"] = sum(x["amount"] for x in state["open"].values())
            state["limit_usd"] = self.limit
            event, result = operation(state)
            if event:
                file.write(json.dumps({"time": time.time(), **event}) + "\n")
                file.flush()
            return result

    def snapshot(self):
        return self._transaction(lambda state: (None, state))

    def reserve(self, label, amount=3.0):
        def operation(state):
            if amount <= 0 or state["charged_usd"] + state["reserved_usd"] + amount > self.limit:
                raise RuntimeError("The experiment budget cannot fund this reservation.")
            identifier = uuid.uuid4().hex
            return {
                "type": "reserve",
                "id": identifier,
                "label": label,
                "amount": amount,
            }, identifier

        return self._transaction(operation)

    def settle(self, identifier, stats=None, note=""):
        def operation(state):
            reserved = state["open"][identifier]
            estimate = usage_cost(stats)
            charged = reserved["amount"] if estimate is None else estimate
            event = {
                "type": "settle",
                "id": identifier,
                "label": reserved["label"],
                "charged_usd": charged,
                "usage_known": estimate is not None,
                "note": note,
                "stats": stats,
            }
            return event, event

        return self._transaction(operation)

    def release_usage_error(self, identifier, stderr_path):
        """Release a reservation only for the verified pre-model CLI argument error."""
        evidence = Path(stderr_path).read_text()
        if "Cannot use both a positional prompt" not in evidence:
            raise ValueError("The log does not establish the recognized CLI usage error.")

        def operation(state):
            events = [json.loads(line) for line in self.path.read_text().splitlines()]
            if any(e["type"] == "verified_no_request" and e["id"] == identifier for e in events):
                raise ValueError("This reservation was already released.")
            entry = next(e for e in events if e["type"] == "settle" and e["id"] == identifier)
            if entry["usage_known"]:
                raise ValueError("Known model usage cannot be released as a CLI usage error.")
            event = {
                "type": "verified_no_request",
                "id": identifier,
                "released_usd": entry["charged_usd"],
                "evidence": str(stderr_path),
                "reason": "CLI argument validation failed before model initialization.",
            }
            return event, event

        return self._transaction(operation)

    def reconcile_completed_usage(self, identifier, stats, evidence, retry_reserve=1.0):
        """Retain a separate allowance for retries absent from completed-response logs."""
        observed = usage_cost(stats)
        if observed is None or retry_reserve < 1.0:
            raise ValueError("Require observed model usage and at least USD 1 for unknown retries.")

        def operation(state):
            events = [json.loads(line) for line in self.path.read_text().splitlines()]
            if any(
                e["type"] in {"usage_reconciliation", "verified_no_request"}
                and e["id"] == identifier
                for e in events
            ):
                raise ValueError("This reservation was already reconciled.")
            previous = next(e for e in events if e["type"] == "settle" and e["id"] == identifier)
            if previous["usage_known"]:
                raise ValueError("The original CLI usage was already available.")
            event = {
                "type": "usage_reconciliation",
                "id": identifier,
                "label": previous["label"],
                "previous_charge_usd": previous["charged_usd"],
                "observed_estimate_usd": observed,
                "retry_reserve_usd": retry_reserve,
                "charged_usd": observed + retry_reserve,
                "stats": stats,
                "evidence": evidence,
                "limitation": "Completed-response logs can omit invalid-stream retries."
                " The charge retains an additional USD 1 allowance; it is not an invoice.",
            }
            return event, event

        return self._transaction(operation)


class BudgetedModel(GeminiModel):
    def __init__(self, directory, budget, label):
        super().__init__(directory)
        self.budget, self.label = budget, label
        self.model_name = MODEL
        settings = json.loads(self.settings.read_text())
        settings["model"] = {"maxSessionTurns": 1}
        self.settings.write_text(json.dumps(settings))

    async def turn(self, prompt, history, tools):
        identifier = self.budget.reserve(self.label, amount=2.0)
        before = len(self.stats)
        try:
            return await super().turn(prompt, history, tools)
        finally:
            stats = self.stats[before:]
            self.budget.settle(identifier, stats or None)
