"""Shared declarations for a small request-bound rental example."""

from copy import deepcopy

from oak.discovery_validation import digest
from oak.kernel_execution import VERSIONS
from oak.repair_schemas import CandidateV2

DEFAULT_QUERY = (
    "Book an offer for 3 guests from 2027-01-10 to 2027-01-12. Spend at most 30000 USD cents."
)
DEFAULT_VALUES = {
    "guests": 3,
    "budget": 30000,
    "start_date": "2027-01-10",
    "end_date": "2027-01-12",
}
READ_ID = "catalog.search"
WRITE_ID = "catalog.create"
REQUIREMENTS = {"party", "dates", "budget", "capacity"}
SOURCE = {"source": "artifact", "id": "search-contract", "path": "/output_schema"}


def expression(kind, name):
    return {"kind": kind, "name": name}


def candidate_data():
    requirements = [
        ("party", "Use the requested number of guests.", [READ_ID, WRITE_ID]),
        ("dates", "Use the requested start and end dates.", [READ_ID, WRITE_ID]),
        ("budget", "The total cost must not exceed the requested budget.", [WRITE_ID]),
        ("capacity", "The offer must accommodate the requested party.", [WRITE_ID]),
    ]
    request_fields = [
        {
            "id": "request.guests",
            "name": "guests",
            "type": "integer",
            "unit": "count",
            "description": "Requested number of guests.",
            "requirement_ids": ["party", "capacity"],
        },
        {
            "id": "request.budget",
            "name": "budget",
            "type": "integer",
            "unit": "USD.cent",
            "description": "Maximum total cost in USD cents.",
            "requirement_ids": ["budget"],
        },
        {
            "id": "request.start_date",
            "name": "start_date",
            "type": "string",
            "description": "Requested start date.",
            "requirement_ids": ["dates"],
        },
        {
            "id": "request.end_date",
            "name": "end_date",
            "type": "string",
            "description": "Requested end date.",
            "requirement_ids": ["dates"],
        },
    ]
    parameters = [
        {"name": "guests", "type": "integer", "unit": "count"},
        {"name": "start_date", "type": "string"},
        {"name": "end_date", "type": "string"},
    ]
    parameter_paths = {item["name"]: "/" + item["name"] for item in parameters}
    conditions = [
        {
            "id": "party_match",
            "entity_id": None,
            "requirement_ids": ["party"],
            "predicate": {
                "operator": "eq",
                "left": expression("argument", "guests"),
                "right": expression("request", "guests"),
            },
        },
        {
            "id": "start_match",
            "entity_id": None,
            "requirement_ids": ["dates"],
            "predicate": {
                "operator": "eq",
                "left": expression("argument", "start_date"),
                "right": expression("request", "start_date"),
            },
        },
        {
            "id": "end_match",
            "entity_id": None,
            "requirement_ids": ["dates"],
            "predicate": {
                "operator": "eq",
                "left": expression("argument", "end_date"),
                "right": expression("request", "end_date"),
            },
        },
        {
            "id": "capacity_ok",
            "entity_id": "offer",
            "requirement_ids": ["capacity"],
            "predicate": {
                "operator": "ge",
                "left": expression("field", "capacity"),
                "right": expression("request", "guests"),
            },
        },
        {
            "id": "budget_ok",
            "entity_id": "offer",
            "requirement_ids": ["budget"],
            "predicate": {
                "operator": "le",
                "left": expression("field", "total_cost"),
                "right": expression("request", "budget"),
            },
        },
    ]
    return {
        "version": "oak.candidate.v2",
        "original_input_digest": "a" * 64,
        "requirements": {
            "requirements": [
                {
                    "id": identifier,
                    "statement": statement,
                    "tool_ids": ids,
                    "evidence": [{"source": "input", "id": "surface", "path": "/rules"}],
                }
                for identifier, statement, ids in requirements
            ]
        },
        "schema": {
            "entities": [
                {
                    "id": "offer",
                    "name": "Offer",
                    "identity_keys": ["id"],
                    "requirement_ids": ["budget", "capacity"],
                    "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "capacity", "type": "integer", "unit": "count"},
                        {"name": "total_cost", "type": "integer", "unit": "USD.cent"},
                    ],
                }
            ]
        },
        "request_fields": request_fields,
        "mappings": [
            {
                "id": "offers",
                "entity_id": "offer",
                "tool_id": READ_ID,
                "collection_path": "/items",
                "fields": [
                    {"property": name, "path": "/" + name}
                    for name in ("id", "capacity", "total_cost")
                ],
                "scope": [
                    {"name": name, "path": "/" + name, "source": "arguments"}
                    for name in parameter_paths
                ],
                "coverage": {"kind": "flag", "path": "/complete", "support": SOURCE},
            }
        ],
        "constraints": conditions,
        "functions": [
            {
                "id": "check_parameters",
                "parameters": parameters,
                "required_constraint_ids": ["party_match", "start_match", "end_match"],
                "steps": [
                    {"op": "input", "id": "inputs"},
                    {
                        "op": "assert",
                        "id": "checks",
                        "input": "inputs",
                        "constraint_ids": ["party_match", "start_match", "end_match"],
                    },
                    {"op": "decision", "id": "result", "inputs": ["checks"]},
                ],
                "return_step": "result",
                "output": {"kind": "decision"},
            },
            {
                "id": "check_offer",
                "entity_id": "offer",
                "parameters": [{"name": "offer_id", "type": "string"}, *deepcopy(parameters)],
                "required_constraint_ids": ["capacity_ok", "budget_ok"],
                "steps": [
                    {
                        "op": "lookup",
                        "id": "offer",
                        "entity_id": "offer",
                        "identity": {"id": expression("argument", "offer_id")},
                        "context": {name: expression("argument", name) for name in parameter_paths},
                    },
                    {
                        "op": "assert",
                        "id": "checks",
                        "input": "offer",
                        "constraint_ids": ["capacity_ok", "budget_ok"],
                    },
                    {"op": "decision", "id": "result", "inputs": ["checks"]},
                ],
                "return_step": "result",
                "output": {"kind": "decision"},
            },
        ],
        "operation_bindings": [
            {
                "id": "search",
                "tool_id": READ_ID,
                "requirement_ids": ["party", "dates"],
                "checks": [{"function_id": "check_parameters", "arguments": parameter_paths}],
            },
            {
                "id": "create",
                "tool_id": WRITE_ID,
                "requirement_ids": ["party", "dates", "budget", "capacity"],
                "credential_paths": ["/auth"],
                "checks": [
                    {"function_id": "check_parameters", "arguments": deepcopy(parameter_paths)},
                    {
                        "function_id": "check_offer",
                        "arguments": {"offer_id": "/offer_id", **deepcopy(parameter_paths)},
                    },
                ],
            },
        ],
        "requirement_coverage": [
            {
                "id": "cover.party",
                "requirement_id": "party",
                "request_field_ids": ["request.guests"],
                "constraint_ids": ["party_match"],
                "binding_ids": ["search", "create"],
            },
            {
                "id": "cover.dates",
                "requirement_id": "dates",
                "request_field_ids": ["request.start_date", "request.end_date"],
                "constraint_ids": ["start_match", "end_match"],
                "binding_ids": ["search", "create"],
            },
            {
                "id": "cover.budget",
                "requirement_id": "budget",
                "request_field_ids": ["request.budget"],
                "constraint_ids": ["budget_ok"],
                "binding_ids": ["create"],
            },
            {
                "id": "cover.capacity",
                "requirement_id": "capacity",
                "request_field_ids": ["request.guests"],
                "constraint_ids": ["capacity_ok"],
                "binding_ids": ["create"],
            },
        ],
    }


def candidate():
    return CandidateV2.model_validate(candidate_data())


def with_source_access(data):
    """Attach supported access rules to a construction fixture."""
    for binding in data["operation_bindings"]:
        read = binding["tool_id"] == READ_ID
        support = {
            "source": "input",
            "id": "surface",
            "path": f"/tools/{0 if read else 1}/description",
        }
        binding["source_access"] = {
            "kind": "data" if read else "action",
            "mapping_ids": [
                m["id"] for m in data["mappings"] if m["tool_id"] == binding["tool_id"]
            ],
            "filters": [
                {"path": "/" + name, "value": expression("request", name), "support": support}
                for name in ("guests", "start_date", "end_date")
            ]
            if read
            else [],
            "support": support,
        }
    return data


def tools():
    common = {
        "guests": {"type": "integer"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
    }
    return [
        {
            "id": READ_ID,
            "name": "search_offers",
            "description": "Read offers for the supplied party and dates.",
            "connection_id": "00000000-0000-0000-0000-000000000001",
            "input_schema": {
                "type": "object",
                "properties": deepcopy(common),
                "required": list(common),
                "additionalProperties": False,
            },
            "output_schema": None,
            "annotations": None,
        },
        {
            "id": WRITE_ID,
            "name": "create_booking",
            "description": "Book the supplied offer for the specified party and dates.",
            "connection_id": "00000000-0000-0000-0000-000000000001",
            "input_schema": {
                "type": "object",
                "properties": {
                    **deepcopy(common),
                    "offer_id": {"type": "string"},
                    "auth": {"type": "string"},
                },
                "required": [*common, "offer_id"],
                "additionalProperties": False,
            },
            "output_schema": None,
            "annotations": None,
        },
    ]


def snapshot(values=None, query=DEFAULT_QUERY):
    values = deepcopy(DEFAULT_VALUES if values is None else values)
    fields = [
        {
            "name": name,
            "status": "resolved" if name in values else "unresolved",
            "value": values.get(name),
            "evidence": [{"source": "query", "quote": query}] if name in values else [],
        }
        for name in DEFAULT_VALUES
    ]
    result = {
        "version": VERSIONS["request_preparation"],
        "status": "ready",
        "query": query,
        "boundaries": {},
        "values": values,
        "fields": fields,
        "preservation": {"status": "passed", "constraints": [], "reason": "Fixed test request."},
        "attempts": [],
    }
    result["digest"] = digest(result)
    return result


def arguments(offer_id=None, **changes):
    result = {key: value for key, value in DEFAULT_VALUES.items() if key != "budget"}
    if offer_id is not None:
        result["offer_id"] = offer_id
    result.update(changes)
    return result


def observe(graph, rows=None, *, identifier="search-result", complete=False, **context):
    if rows is None:
        rows = [{"id": "offer-a", "capacity": 4, "total_cost": 24000}]
    return graph.add(
        {
            "id": identifier,
            "tool_id": READ_ID,
            "status": "succeeded",
            "coverage": "unknown",
            "data": {"items": deepcopy(rows), "complete": complete},
        },
        arguments=arguments(**context),
    )
