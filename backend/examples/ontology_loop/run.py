"""Run construction, inference, or a labelled local replay."""

import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path

from mcp import Client
from pydantic import ValidationError

from .kernel import (
    FIELDS,
    TASK,
    Candidate,
    Query,
    evaluate,
    load_cases,
    validate_candidate,
)
from .runtime import Runtime, agent_loop, source_servers


class GeminiModel:
    mode = "gemini_cli"

    def __init__(self, directory):
        backend = Path(__file__).resolve().parents[2]
        local = backend / ".local/gemini-cli/node_modules/.bin/gemini"
        self.command = os.environ.get("OAK_GEMINI_CLI") or shutil.which("gemini") or str(local)
        if not Path(self.command).is_file():
            raise ValueError("Install Gemini CLI or set OAK_GEMINI_CLI to its executable path.")
        profile_path = Path(
            os.environ.get("OAK_GEMINI_PROFILE", backend / ".local/gemini-auth.json")
        )
        profile = json.loads(profile_path.read_text()) if profile_path.exists() else {}
        self.model_name = os.environ.get("OAK_GEMINI_MODEL") or profile.get("model")
        # Apply the generated workspace settings before the CLI loads authentication.
        self.environment = {"GEMINI_CLI_TRUST_WORKSPACE": "true"}
        authentication = {}
        if profile.get("auth_type") == "vertex-ai":
            project = os.environ.get("GOOGLE_CLOUD_PROJECT") or profile.get("project")
            if not project:
                raise ValueError("The Vertex AI profile requires a Google Cloud project.")
            authentication = {"auth": {"selectedType": "vertex-ai"}}
            self.environment.update(
                {
                    "GEMINI_CLI_AUTH_OVERRIDE": "vertex-ai",
                    "GOOGLE_GENAI_USE_VERTEXAI": "true",
                    "GOOGLE_CLOUD_PROJECT": project,
                    "GOOGLE_CLOUD_LOCATION": os.environ.get("GOOGLE_CLOUD_LOCATION")
                    or profile.get("location", "global"),
                }
            )
        self.directory = (directory / "gemini-workspace").resolve()
        self.settings = self.directory / ".gemini/settings.json"
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(
            json.dumps(
                {
                    "security": authentication,
                    "tools": {"core": ["__oak_no_native_tools__"]},
                    "admin": {
                        "mcp": {"enabled": False},
                        "extensions": {"enabled": False},
                        "skills": {"enabled": False},
                    },
                    "hooksConfig": {"enabled": False},
                    "context": {"fileName": [], "includeDirectoryTree": False},
                    "advanced": {"ignoreLocalEnv": True},
                }
            )
        )
        self.calls = 0
        self.stats = []
        self.attempts = 0

    async def turn(self, prompt, history, tools):
        self.attempts += 1
        payload = json.dumps(
            {
                "instructions": prompt,
                "protocol": 'Return one JSON object: {"name": tool_name, "arguments": object}. '
                "Select a tool from this catalog. The host executes it. "
                "Do not use CLI tools. Do not include markdown or explanation.",
                "history": history,
                "tools": tools,
            }
        )
        command = [
            self.command,
            "--skip-trust",
            "--output-format",
            "json",
            "--prompt",
            "Use the JSON request on stdin. Return the next tool action as JSON.",
        ]
        if self.model_name:
            command.extend(["--model", self.model_name])
        environment = {**os.environ, **self.environment}
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.directory,
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(payload.encode()), 180)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            error_path = self.directory / "last-error.log"
            error_path.write_bytes(stderr)
            raise RuntimeError(
                "Gemini CLI failed. Check its login, quota, and model settings. "
                f"Exit code: {process.returncode}. See {error_path}."
            )
        response = json.loads(stdout)
        (self.directory / f"response-{self.attempts:03d}.json").write_text(
            json.dumps(response, indent=2)
        )
        self.stats.append(response.get("stats", {}))
        if response.get("error") or not isinstance(response.get("response"), str):
            raise RuntimeError("Gemini CLI did not return a successful model response.")
        if response.get("stats", {}).get("tools", {}).get("totalCalls", 0):
            raise ValueError("Return a JSON action without calling a CLI tool.")
        raw = response["response"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        action = json.loads(raw)
        if (
            set(action) != {"name", "arguments"}
            or not isinstance(action["name"], str)
            or not isinstance(action["arguments"], dict)
        ):
            raise ValueError("Gemini must return one tool name and an arguments object.")
        self.calls += 1
        return [
            {
                "type": "function_call",
                "call_id": f"gemini_{self.calls}",
                "name": action["name"],
                "arguments": json.dumps(action["arguments"]),
            }
        ]

    async def propose(self, cases, feedback):
        prompt = (
            "Construct a small operational ontology kernel. "
            + TASK
            + " Source record contracts: "
            + json.dumps(FIELDS)
            + " Each record has primary key id. Draft disjoint types and named relations. "
            "Map each relation to its source foreign-key field and target record type. "
            "Compose one function with entity lookup, relation traversal, typed comparisons, "
            "and arithmetic projection. Expressions can reference input fields and bound "
            "record fields. Use add or multiply for arithmetic. Constants 0 and 1 express "
            "structural counts; task thresholds must come from the request or source data. "
            "Derive the relationships and calculations from requirements and examples. "
            "Use repair feedback to revise the schema or function. Call propose_kernel."
        )
        output = await self.turn(
            prompt,
            [{"role": "user", "content": json.dumps({"examples": cases, "feedback": feedback})}],
            [
                {
                    "type": "function",
                    "name": "propose_kernel",
                    "description": "Submit the kernel draft.",
                    "parameters": Candidate.model_json_schema(),
                    "strict": False,
                }
            ],
        )
        calls = [
            x
            for x in output
            if x.get("type") == "function_call" and x.get("name") == "propose_kernel"
        ]
        if len(calls) != 1:
            raise ValueError("The composer must return one propose_kernel call.")
        return Candidate.model_validate_json(calls[0]["arguments"])


class ReplayModel:
    """A test double. It does not make an LLM call or learn a kernel."""

    mode = "scripted_replay"

    async def propose(self, cases, feedback):
        return Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())

    async def turn(self, prompt, history, tools):
        query = json.loads(history[0]["content"])
        observations = [
            json.loads(h["output"]) for h in history if h.get("type") == "function_call_output"
        ]
        step = len(observations)
        if step == 0:
            name, arguments = "inventory__read_inventory", {"city": query["city"]}
        elif step == 1:
            name, arguments = "policies__read_policies", {"city": query["city"]}
        elif step == 2:
            name, arguments = "eligible_stays", {"request": query}
        else:
            name, arguments = (
                "submit_answer",
                {"receipt": observations[-1].get("receipt", "missing")},
            )
        return [
            {
                "type": "function_call",
                "call_id": f"replay_{step}",
                "name": name,
                "arguments": json.dumps(arguments),
            }
        ]


async def run_case(model, candidate, case):
    inventory, policies = source_servers(case)
    async with Client(inventory) as inventory_client, Client(policies) as policy_client:
        # Discover before calling. The two fixture servers remain separate MCP sessions.
        await inventory_client.list_tools()
        await policy_client.list_tools()
        runtime = Runtime(
            candidate,
            Query.model_validate_json(json.dumps(case["query"])),
            inventory_client,
            policy_client,
        )
        result = await agent_loop(model, runtime)
        return {"mode": model.mode, "case": case["name"], **result}


def score_run(result, case):
    answer = result.get("answer")
    if not answer or answer["status"] != "complete":
        return False
    return {r["offer_id"]: r["total_cents"] for r in answer["eligible"]} == case["expected"]


async def build(model, directory: Path, max_rounds=3):
    cases = load_cases()["training"]
    feedback, rounds = [], []
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(1, max_rounds + 1):
        report = {"round": number, "mode": model.mode}
        try:
            candidate = await model.propose(cases, feedback)
            report["candidate"] = candidate.model_dump(mode="json")
            validate_candidate(candidate)
            feedback = evaluate(candidate, cases)
            if not feedback:
                runs = [await run_case(model, candidate, case) for case in cases]
                report["runs"] = runs
                feedback = [
                    {"case": case["name"], "run": run}
                    for case, run in zip(cases, runs, strict=True)
                    if not score_run(run, case)
                ]
        except (ValueError, ValidationError) as exc:
            feedback = [{"validation_error": str(exc)}]
        except RuntimeError as exc:
            report["infrastructure_error"] = str(exc)
            (directory / "construction.json").write_text(json.dumps([*rounds, report], indent=2))
            raise
        report["feedback"] = feedback
        rounds.append(report)
        (directory / "construction.json").write_text(json.dumps(rounds, indent=2))
        if not feedback:
            validate_candidate(candidate, directory / "schema.owl")
            (directory / "kernel.json").write_text(candidate.model_dump_json(indent=2))
            (directory / "validation.json").write_text(
                json.dumps(
                    {
                        "fingerprint": candidate.fingerprint,
                        "mode": model.mode,
                        "training_cases_passed": len(cases),
                        "owl_reasoner": "HermiT",
                    },
                    indent=2,
                )
            )
            return candidate
    raise ValueError(f"Construction failed after {max_rounds} rounds. See construction.json.")


def load_kernel(directory):
    candidate = Candidate.model_validate_json((directory / "kernel.json").read_text())
    validation = json.loads((directory / "validation.json").read_text())
    if candidate.fingerprint != validation["fingerprint"]:
        raise ValueError("The kernel changed after validation. Run construction again.")
    validate_candidate(candidate)
    return candidate


async def main(args):
    directory = Path(args.output)
    model = ReplayModel() if args.replay else GeminiModel(directory)
    if args.command in {"build", "demo"}:
        await build(model, directory)
    if args.command in {"run", "demo"}:
        candidate = load_kernel(directory)
        result = await run_case(model, candidate, load_cases()["held_out"])
        result["passed"] = score_run(result, load_cases()["held_out"])
        if isinstance(model, GeminiModel):
            result["model_stats"] = model.stats
        (directory / "run.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    else:
        print(f"Validated kernel: {directory / 'kernel.json'} ({model.mode})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "run", "demo"))
    parser.add_argument(
        "--replay", action="store_true", help="Use a scripted test double, not an LLM."
    )
    parser.add_argument("--output", default=".local/ontology-demo")
    try:
        asyncio.run(main(parser.parse_args()))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
