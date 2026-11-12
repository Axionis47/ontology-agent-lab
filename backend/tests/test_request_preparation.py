"""Check request preservation with fixed, local model responses."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from oak.discovery_validation import digest
from oak.evidence_graph import EvidenceGraph
from oak.kernel_dispatcher import KernelDispatcher
from oak.request_preparation import (
    EXTRACT,
    PRESERVE,
    RequestExtraction,
    prepare_request,
    validate_extraction,
)
from tests.kernel_fixtures import (
    DEFAULT_QUERY,
    DEFAULT_VALUES,
    READ_ID,
    WRITE_ID,
    arguments,
    candidate,
    observe,
    tools,
)


class ScriptedGeneration:
    def __init__(self, *responses):
        self.responses = list(deepcopy(responses))
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        assert self.responses, "The request exceeded its generation budget."
        return SimpleNamespace(data=self.responses.pop(0))


def extraction(values=None, *, query=DEFAULT_QUERY):
    values = DEFAULT_VALUES if values is None else values
    return {
        "fields": [
            {
                "name": name,
                "status": "resolved" if name in values else "unresolved",
                "value": values.get(name),
                "evidence": [{"source": "query", "quote": query}] if name in values else [],
            }
            for name in DEFAULT_VALUES
        ]
    }


def preservation(status="passed", *, query=DEFAULT_QUERY, constraint_status="covered", names=None):
    return {
        "status": status,
        "constraints": [
            {
                "statement": "Preserve the original party, dates, and budget.",
                "status": constraint_status,
                "field_names": list(DEFAULT_VALUES) if names is None else names,
                "evidence": [{"source": "query", "quote": query}],
            }
        ],
        "reason": "Check the original request values.",
    }


async def ignore_event(*args, **kwargs):
    return None


async def test_request_preserves_source_values_and_records_both_checks():
    generated = extraction()
    review = preservation()
    generate = ScriptedGeneration(generated, review)
    events = []
    boundaries = {"task": {"rules": "Use the granted catalog."}, "agent": {"id": "a"}}

    async def record(kind, body):
        events.append((kind, deepcopy(body)))

    result = await prepare_request(candidate(), DEFAULT_QUERY, boundaries, generate, record)

    assert result["status"] == "ready"
    assert result["values"] == DEFAULT_VALUES
    assert result["digest"] == digest({k: v for k, v in result.items() if k != "digest"})
    assert [call["instructions"] for call in generate.calls] == [EXTRACT, PRESERVE]
    assert generate.calls[1]["data"]["extraction"] == generated
    assert events == [
        ("request_preparation", {"attempt": 1, "extraction": generated, "preservation": review})
    ]
    assert "task_success" not in generate.calls[0]["data"]
    assert "arguments" not in generate.calls[0]["data"]
    boundaries["task"]["rules"] = "Changed after preparation."
    generated["fields"][0]["value"] = 1
    assert result["boundaries"]["task"]["rules"] == "Use the granted catalog."
    assert result["values"]["guests"] == 3


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unknown"])
def test_extraction_requires_each_declared_field_once(failure):
    data = extraction()
    if failure == "missing":
        data["fields"].pop()
    elif failure == "duplicate":
        data["fields"][-1] = deepcopy(data["fields"][0])
    else:
        data["fields"][-1]["name"] = "invented"
    with pytest.raises(ValueError, match="exactly once"):
        validate_extraction(RequestExtraction.model_validate(data), candidate(), DEFAULT_QUERY, {})


@pytest.mark.parametrize("value", [True, "3", 3.0, None])
def test_extraction_rejects_invalid_integer_values(value):
    data = extraction()
    data["fields"][0]["value"] = value
    with pytest.raises(ValueError, match="typed source evidence"):
        validate_extraction(RequestExtraction.model_validate(data), candidate(), DEFAULT_QUERY, {})


@pytest.mark.parametrize("status", ["absent", "unresolved"])
def test_unavailable_fields_cannot_keep_a_value(status):
    data = extraction()
    data["fields"][0]["status"] = status
    with pytest.raises(ValueError, match="cannot contain values"):
        validate_extraction(RequestExtraction.model_validate(data), candidate(), DEFAULT_QUERY, {})


@pytest.mark.parametrize("source", ["query", "boundaries"])
async def test_extraction_rejects_evidence_outside_original_sources(source):
    data = extraction()
    data["fields"][0]["evidence"] = [{"source": source, "quote": "Book for one person."}]
    generate = ScriptedGeneration(data)
    with pytest.raises(ValueError, match="does not match original text"):
        await prepare_request(candidate(), DEFAULT_QUERY, {}, generate, ignore_event)
    assert len(generate.calls) == 1


async def test_preservation_requires_original_evidence_and_known_fields():
    for change, message in [
        ({"evidence": [{"source": "query", "quote": "Invented rule."}]}, "does not match"),
        ({"field_names": ["invented"]}, "unknown request fields"),
    ]:
        review = preservation()
        review["constraints"][0].update(change)
        with pytest.raises(ValueError, match=message):
            await prepare_request(
                candidate(),
                DEFAULT_QUERY,
                {},
                ScriptedGeneration(extraction(), review),
                ignore_event,
            )


@pytest.mark.parametrize("failure", ["omitted_budget", "negated_party"])
async def test_preservation_can_repair_an_omission_or_negation_once(failure):
    query = DEFAULT_QUERY + " Do not change the party to 1 guest."
    wrong_values = deepcopy(DEFAULT_VALUES)
    if failure == "omitted_budget":
        wrong_values.pop("budget")
    else:
        wrong_values["guests"] = 1
    first = extraction(wrong_values, query=query)
    review = preservation("needs_correction", query=query, constraint_status="unresolved")
    generate = ScriptedGeneration(first, review, extraction(query=query), preservation(query=query))

    result = await prepare_request(candidate(), query, {}, generate, ignore_event)

    assert result["status"] == "ready"
    assert result["values"] == DEFAULT_VALUES
    assert len(result["attempts"]) == 2
    assert len(generate.calls) == 4
    assert generate.calls[2]["data"]["correction"] == {"extraction": first, "preservation": review}
    assert generate.calls[2]["data"]["query"] == query


async def test_request_correction_is_bounded_to_one_retry():
    review = preservation("needs_correction", constraint_status="unresolved", names=[])
    generate = ScriptedGeneration(extraction(), review, extraction(), review)
    result = await prepare_request(candidate(), DEFAULT_QUERY, {}, generate, ignore_event)
    assert result["status"] == "unresolved_request"
    assert len(result["attempts"]) == 2
    assert len(generate.calls) == 4


@pytest.mark.parametrize("outer_status", ["unsupported", "passed"])
async def test_unsupported_constraint_stops_without_a_correction(outer_status):
    query = DEFAULT_QUERY + " The room must have certified sound insulation."
    review = preservation(outer_status, query=query, constraint_status="unsupported", names=[])
    generate = ScriptedGeneration(extraction(query=query), review)
    result = await prepare_request(candidate(), query, {}, generate, ignore_event)
    assert result["status"] == "unsupported_request"
    assert len(result["attempts"]) == 1
    assert result["preservation"]["constraints"][0]["status"] == "unsupported"


async def test_unscoped_unresolved_constraint_blocks_the_whole_request():
    review = preservation("passed", constraint_status="unresolved", names=[])
    generate = ScriptedGeneration(extraction(), review, extraction(), review)
    result = await prepare_request(candidate(), DEFAULT_QUERY, {}, generate, ignore_event)
    assert result["status"] == "unresolved_request"


@pytest.mark.parametrize("status", ["passed", "needs_correction"])
async def test_scoped_unresolved_value_blocks_only_dependent_operations(status):
    review = preservation(status, constraint_status="unresolved", names=["budget"])
    generate = ScriptedGeneration(extraction(), review, extraction(), review)
    prepared = await prepare_request(candidate(), DEFAULT_QUERY, {}, generate, ignore_event)
    assert prepared["status"] == "ready"
    assert "budget" not in prepared["values"]
    budget = next(field for field in prepared["fields"] if field["name"] == "budget")
    assert budget["status"] == "unresolved"
    assert budget["value"] is None
    assert prepared["attempts"][-1]["extraction"]["fields"][1]["value"] == 30000
    graph = EvidenceGraph(candidate())
    observe(graph)
    granted = {tool["id"]: tool for tool in tools()}
    dispatcher = KernelDispatcher(
        candidate=candidate(),
        graph=graph,
        request_snapshot=prepared,
        tools=list(granted.values()),
        run_mode="inference",
        stage="inference",
        transport=ignore_event,
        record=ignore_event,
    )
    independent = dispatcher.check(granted[READ_ID], arguments(), "read")
    dependent = dispatcher.check(granted[WRITE_ID], arguments("offer-a"), "write")
    assert independent["status"] == "allowed"
    assert dependent["status"] == "missing_evidence"
    assert prepared["digest"] == digest({k: v for k, v in prepared.items() if k != "digest"})


def test_resolved_fields_require_evidence_even_when_the_value_is_typed():
    data = extraction()
    data["fields"][0]["evidence"] = []
    with pytest.raises(ValueError, match="typed source evidence"):
        validate_extraction(RequestExtraction.model_validate(data), candidate(), DEFAULT_QUERY, {})


def test_boundaries_can_supply_original_request_values():
    data = extraction()
    data["fields"][0]["evidence"] = [{"source": "boundaries", "quote": "The party has 3 guests."}]
    validate_extraction(
        RequestExtraction.model_validate(data),
        candidate(),
        DEFAULT_QUERY,
        {"task": {"rules": "The party has 3 guests."}},
    )
