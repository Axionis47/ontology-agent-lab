"""Execute temporary data queries against the fixed harness and observed graph."""

import json
from typing import Annotated

from pydantic import Field, JsonValue

from oak.discovery_validation import digest
from oak.kernel_execution import _execute_expanded
from oak.repair_patch import candidate_digest, canonical_digest
from oak.repair_schemas import (
    AggregateStep,
    EntitiesOutput,
    FilterStep,
    Frozen,
    Function,
    LookupStep,
    Parameter,
    ProjectStep,
    RowsOutput,
    ScalarOutput,
    SelectGroupStep,
    SelectMinStep,
    SelectTypesStep,
    TraverseStep,
)

DataStep = Annotated[
    LookupStep
    | TraverseStep
    | SelectTypesStep
    | FilterStep
    | ProjectStep
    | AggregateStep
    | SelectGroupStep
    | SelectMinStep,
    Field(discriminator="op"),
]


class GraphQuery(Frozen):
    """A temporary plan. It cannot declare entities, relations, or permissions."""

    parameters: tuple[Parameter, ...] = Field(default=(), max_length=100)
    arguments: dict[str, JsonValue] = Field(default_factory=dict, max_length=100)
    steps: tuple[DataStep, ...] = Field(min_length=1, max_length=100)
    return_step: str
    output: Annotated[RowsOutput | ScalarOutput | EntitiesOutput, Field(discriminator="kind")]

    def function(self):
        constraints = tuple(
            dict.fromkeys(cid for step in self.steps for cid in getattr(step, "constraint_ids", ()))
        )
        return Function(
            id="query_" + digest(self.model_dump(mode="json")),
            parameters=self.parameters,
            required_constraint_ids=constraints,
            steps=self.steps,
            return_step=self.return_step,
            output=self.output,
        )


def execute_query(candidate, graph, query, request=None):
    query = GraphQuery.model_validate(query)
    function = query.function()
    return _execute_expanded(
        candidate, function.id, query.arguments, request or {}, graph, function=function
    )


def read_arguments(value):
    def invalid(value):
        raise ValueError("Arguments cannot contain non-finite numbers.")

    result = json.loads(value, parse_constant=invalid)
    if not isinstance(result, dict):
        raise ValueError("arguments_json must contain a JSON object.")
    return result


def definition_catalog(candidate):
    raw = candidate.model_dump(mode="json")
    definitions = {}
    index = []
    for owner in (raw["schema"], raw):
        for collection, items in owner.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                definitions.setdefault(collection, {})[item["id"]] = item
                index.append(
                    {"collection": collection, "id": item["id"], "digest": canonical_digest(item)}
                )
    return {
        "version": "oak.catalog.v1",
        "candidate_digest": candidate_digest(candidate),
        "index": index,
        "definitions": definitions,
        "query_schema": GraphQuery.model_json_schema(),
        "query_example": {
            "steps": [{"op": "lookup", "id": "rows", "entity_id": "ENTITY_ID"}],
            "return_step": "rows",
            "output": {"kind": "entities", "entity_types": ["ENTITY_ID"]},
        },
    }


GRAPH_TOOLS = [
    {
        "name": "run_function",
        "description": (
            "Execute an existing data function on observed graph facts. Read its parameters "
            "in harness_catalog with read_evidence first. Supply its exact function_id and a "
            "JSON object in arguments_json. Permission decision functions are not callable. "
            "Missing evidence returns dependencies. This operation makes no external calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"function_id": {"type": "string"}, "arguments_json": {"type": "string"}},
            "required": ["function_id", "arguments_json"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_graph",
        "description": (
            "Read existing graph relations without adding a function. Read query_schema and "
            "definitions in harness_catalog with read_evidence. query_json must encode a "
            "GraphQuery with steps, return_step, output, and optional parameters and arguments. "
            "Use only declared types, relations, and constraints. Values come from the request "
            "or observed evidence. Results retain scope, coverage, and missing dependencies. "
            "Missing data can be obtained through granted MCP tools after this query. "
            "This operation cannot change the harness, dispatch tools, or authorize actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query_json": {"type": "string", "maxLength": 100000}},
            "required": ["query_json"],
            "additionalProperties": False,
        },
    },
]
