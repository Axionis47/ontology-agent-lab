"""Require an invocation-specific kernel decision before external transport."""

import asyncio
from copy import deepcopy
from dataclasses import dataclass

from jsonschema import validators
from referencing import Registry

from oak.acquisition import Acquisition, validate_access
from oak.discovery_validation import digest, validate_json
from oak.kernel_execution import combine_conditions, execute_v2, validate_v2
from oak.repair_executor import MISSING, _pointer
from oak.repair_patch import candidate_digest
from oak.repair_schemas import Candidate


@dataclass
class DispatchPermit:
    invocation_id: str
    tool_id: str
    arguments_digest: str
    candidate_digest: str | None
    request_digest: str | None
    graph_revision: int | None
    credential_paths: tuple[str, ...]
    baseline: bool
    consumed: bool = False

    def consume(self, tool_id, arguments, invocation_id):
        if self.consumed or (self.tool_id, self.arguments_digest, self.invocation_id) != (
            str(tool_id),
            digest(arguments),
            invocation_id,
        ):
            raise ValueError("The dispatch permit does not match this invocation.")
        self.consumed = True


def credential_references(value, path=""):
    if isinstance(value, dict):
        return [
            p
            for k, v in value.items()
            for p in credential_references(v, path + "/" + k.replace("~", "~0").replace("/", "~1"))
        ]
    if isinstance(value, list):
        return [
            p for i, v in enumerate(value) for p in credential_references(v, path + "/" + str(i))
        ]
    return [path] if isinstance(value, str) and value.startswith("oak-secret:") else []


def declared_credential_paths(schema, path=""):
    """Read explicit credential declarations from the fixed tool input contract."""
    if not isinstance(schema, dict):
        return set()
    if schema.get("type") == "string" and (
        schema.get("writeOnly") is True
        or schema.get("format") == "password"
        or schema.get("x-oak-credential") is True
    ):
        return {path}
    return {
        item
        for key, child in schema.get("properties", {}).items()
        for item in declared_credential_paths(
            child, path + "/" + key.replace("~", "~0").replace("/", "~1")
        )
    }


def validate_dispatch_arguments(arguments, schema, credential_paths):
    """Validate a logical reference. Transport validates the resolved secret again."""
    refs = credential_references(arguments)
    if any(path not in credential_paths for path in refs):
        raise ValueError("A credential reference occurs in a task argument.")
    if not refs:
        validate_json(arguments, schema)
        return
    base = validators.validator_for(schema)
    base.check_schema(schema)

    def reference_or_value(check):
        def validate(validator, rule, value, subschema):
            if isinstance(value, str) and value.startswith("oak-secret:"):
                return
            yield from check(validator, rule, value, subschema)

        return validate

    overrides = {
        name: reference_or_value(base.VALIDATORS[name])
        for name in ("pattern", "enum", "const", "minLength", "maxLength", "format")
        if name in base.VALIDATORS
    }
    logical = validators.extend(base, overrides)(schema, registry=Registry())
    if any(logical.iter_errors(arguments)):
        raise ValueError("The value does not match its declared JSON Schema.")


def verify_transport_arguments(logical, resolved, paths):
    def check(a, b, path=""):
        if path in paths and isinstance(a, str) and a.startswith("oak-secret:"):
            if not isinstance(b, str):
                raise ValueError("A credential must resolve to a string.")
            return
        if type(a) is not type(b):
            raise ValueError("Transport changed checked task arguments.")
        if isinstance(a, dict):
            if a.keys() != b.keys():
                raise ValueError("Transport changed checked task arguments.")
            for key in a:
                check(a[key], b[key], path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(a, list):
            if len(a) != len(b):
                raise ValueError("Transport changed checked task arguments.")
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                check(x, y, path + "/" + str(i))
        elif a != b:
            raise ValueError("Transport changed checked task arguments.")

    check(logical, resolved)


class KernelDispatcher:
    def __init__(
        self, *, candidate, graph, request_snapshot, tools, run_mode, stage, transport, record
    ):
        self.baseline = run_mode == "training" and stage == "baseline"
        self.candidate = (
            Candidate.model_validate(candidate).model_copy(deep=True) if candidate else None
        )
        if not self.baseline and (
            self.candidate is None
            or self.candidate.version not in {"oak.candidate.v2", "oak.candidate.v3"}
        ):
            raise ValueError("This episode requires a supported scoped kernel.")
        self.tools = {str(t["id"]): deepcopy(t) for t in tools}
        self.request = deepcopy(request_snapshot)
        self.graph, self.transport, self.record = graph, transport, record
        self.lock = asyncio.Lock()
        if not self.baseline:
            all_tools = {m.tool_id for m in self.candidate.mappings} | {
                b.tool_id for b in self.candidate.operation_bindings
            }
            validate_v2(
                self.candidate, all_tools, {r.id for r in self.candidate.requirements.requirements}
            )
            if self.request is None or self.request.get("status") != "ready":
                raise ValueError("The fixed request is not ready.")
            saved = {k: v for k, v in self.request.items() if k != "digest"}
            if digest(saved) != self.request.get("digest"):
                raise ValueError("The fixed request digest does not match.")
            if credential_references(self.request.get("values", {})):
                raise ValueError("A credential reference cannot supply a task request value.")
        self.candidate_digest = candidate_digest(self.candidate) if self.candidate else None
        if not self.baseline and (
            self.graph is None or candidate_digest(self.graph.candidate) != self.candidate_digest
        ):
            raise ValueError("The graph does not belong to the checked kernel.")
        self.bindings = (
            {b.tool_id: b for b in self.candidate.operation_bindings} if self.candidate else {}
        )
        self.acquisition = None
        if not self.baseline:
            validate_access(self.candidate, self.tools)
            self.acquisition = Acquisition(self.candidate, self.request, self.graph)

    def check(self, tool, arguments, invocation_id):
        tid = str(tool["id"])
        decision = {
            "invocation_id": invocation_id,
            "tool_id": tid,
            "arguments": deepcopy(arguments),
            "arguments_digest": digest(arguments),
            "candidate_digest": self.candidate_digest,
            "request_digest": self.request.get("digest") if self.request else None,
            "graph_revision": self.graph.revision if self.graph else None,
            "conditions": [],
            "function_calls": [],
            "missing_dependencies": [],
        }
        try:
            if tid not in self.tools or tool != self.tools[tid]:
                raise ValueError("The tool is not selected and granted for this episode.")
            if self.baseline:
                paths = declared_credential_paths(tool["input_schema"])
                validate_dispatch_arguments(arguments, tool["input_schema"], paths)
                decision.update(status="allowed", baseline=True, credential_paths=sorted(paths))
                if any(path not in paths for path in credential_references(arguments)):
                    raise ValueError("Baseline credentials require explicit declared paths.")
                return decision
            binding = self.bindings.get(tid)
            if binding is None:
                raise ValueError("No accepted kernel binding exists for this tool.")
            validate_dispatch_arguments(arguments, tool["input_schema"], binding.credential_paths)
            if any(p not in binding.credential_paths for p in credential_references(arguments)):
                raise ValueError("A credential reference occurs in a task argument.")
            decision.update(binding_id=binding.id, credential_paths=list(binding.credential_paths))
            decision["acquisition"] = self.acquisition.check(binding, arguments)
            for check in binding.checks:
                parameters = {
                    name: _pointer(arguments, path) for name, path in check.arguments.items()
                }
                result = execute_v2(
                    self.candidate,
                    check.function_id,
                    parameters,
                    self.request["values"],
                    self.graph,
                )
                call = {
                    "function_id": check.function_id,
                    "arguments": {k: v for k, v in parameters.items() if v is not MISSING},
                    "result": result,
                    "automatic": True,
                    "invocation_id": invocation_id,
                }
                decision["function_calls"].append(call)
                decision["conditions"].extend(result["conditions"])
                for missing in result.get("missing_dependencies", []):
                    sources = self.graph.sources(check.function_id)
                    decision["missing_dependencies"].append(
                        {
                            **missing,
                            "sources": [
                                s
                                for s in sources
                                if s["tool_id"] in self.tools
                                and s["tool_id"] in self.bindings
                                and (
                                    not missing.get("property")
                                    or missing["property"] in s["properties"]
                                )
                            ],
                        }
                    )
            decision["status"] = combine_conditions(decision["conditions"])
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            decision.update(status="rejected", error="check_error", message=str(error))
        return decision

    async def __call__(self, tool, arguments, invocation_id):
        async with self.lock:
            arguments = deepcopy(arguments)
            decision = self.check(tool, arguments, invocation_id)
            await self.record("dispatch_decision", **decision)
            if decision["status"] != "allowed":
                return {**decision, "dispatched": False, "decision": decision}
            permit = DispatchPermit(
                invocation_id,
                str(tool["id"]),
                digest(arguments),
                self.candidate_digest,
                decision["request_digest"],
                decision["graph_revision"],
                tuple(decision["credential_paths"]),
                self.baseline,
            )
            result = await self.transport(tool, arguments, invocation_id, permit=permit)
            return {**result, "decision": decision}
