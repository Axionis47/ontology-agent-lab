from copy import deepcopy

import pytest

import oak.evidence_graph as graph_module
from oak.evidence_graph import EvidenceGraph, GraphIngestionError
from oak.repair_executor import IncompleteEvidence
from tests.test_repair_executor import candidate

SUPPORT = {"source": "artifact", "id": "tool-contract", "path": "/output_schema"}


def definition(*, scoped=True, coverage=None, partial=False):
    value = candidate().model_dump(mode="json")
    value["version"] = "oak.candidate.v2"
    value["constraints"] = [
        {
            "id": "ready",
            "entity_id": None,
            "requirement_ids": ["minimum"],
            "predicate": {
                "operator": "eq",
                "left": {"kind": "literal", "value": True},
                "right": {"kind": "literal", "value": True},
            },
        }
    ]
    value["functions"] = [
        {
            "id": "check",
            "required_constraint_ids": ["ready"],
            "steps": [
                {"op": "input", "id": "inputs"},
                {"op": "assert", "id": "asserts", "input": "inputs", "constraint_ids": ["ready"]},
                {"op": "decision", "id": "result", "inputs": ["asserts"]},
            ],
            "return_step": "result",
            "output": {"kind": "decision"},
        }
    ]
    value["operation_bindings"] = [
        {
            "id": "list",
            "tool_id": "catalog.list",
            "requirement_ids": ["minimum"],
            "checks": [{"function_id": "check", "arguments": {}}],
        }
    ]
    value["requirement_coverage"] = [
        {
            "id": "covered",
            "requirement_id": "minimum",
            "constraint_ids": ["ready"],
            "binding_ids": ["list"],
        }
    ]
    mapping = value["mappings"][0]
    mapping["scope"] = [{"name": "city", "source": "arguments", "path": "/city"}] if scoped else []
    if coverage:
        mapping["coverage"] = {
            "kind": coverage,
            "path": "/complete" if coverage == "flag" else "",
            "support": SUPPORT,
        }
    if partial:
        mapping["update_mode"] = "partial"
        mapping["update_support"] = SUPPORT
    return value


def observed(identifier, rows, *, status="succeeded", **data):
    return {
        "id": identifier,
        "tool_id": "catalog.list",
        "status": status,
        "coverage": "unknown",
        "data": {"items": rows, **data},
    }


def add(graph, identifier, rows, *, city="A", **data):
    return graph.add(observed(identifier, rows, **data), arguments={"city": city})


def test_same_identity_keeps_separate_contexts_and_exact_evidence():
    graph = EvidenceGraph(definition())
    add(graph, "a", [{"id": "same", "amount": 7}], city="A")
    add(graph, "b", [{"id": "same", "amount": 20}], city="B")
    first = graph.lookup("record", {"id": "same"}, {"city": "A", "unrelated": "ignored"})
    second = graph.lookup("record", {"id": "same"}, {"city": "B"})
    assert first.records == [{"id": "same", "amount": 7}]
    assert second.records == [{"id": "same", "amount": 20}]
    assert first.complete and second.complete
    assert all(ref["context"] == {"city": "A"} for ref in first.evidence)
    assert {ref["observation_id"] for ref in first.evidence} == {"a"}
    assert not graph.collection("record", {"city": "A"}).complete
    assert not graph.lookup("record", {"id": "same"}, {"city": "C"}).complete


def test_exact_lookup_is_not_blocked_by_an_unrelated_missing_property():
    graph = EvidenceGraph(definition(scoped=False))
    add(graph, "one", [{"id": "chosen", "amount": 9}, {"id": "other"}])
    result = graph.lookup("record", {"id": "chosen"}, {})
    assert result.records == [{"id": "chosen", "amount": 9}]
    assert all("/items/0/" in ref["path"] for ref in result.evidence)
    assert graph.lookup("record", {"id": "absent"}, {}).evidence == []


def test_exact_lookup_does_not_materialize_the_collection(monkeypatch):
    graph = EvidenceGraph(definition())
    add(graph, "one", [{"id": "chosen", "amount": 9}])

    def collection_is_not_needed(*args, **kwargs):
        raise AssertionError("Exact lookup must use the subject index.")

    monkeypatch.setattr(graph, "collection", collection_is_not_needed)
    assert graph.lookup("record", {"id": "chosen"}, {"city": "A"}).records[0]["amount"] == 9


def test_missing_context_and_invalid_identity_do_not_scan_other_scopes():
    graph = EvidenceGraph(definition())
    add(graph, "one", [{"id": "chosen", "amount": 9}])
    with pytest.raises(IncompleteEvidence, match="context"):
        graph.lookup("record", {"id": "chosen"}, {})
    with pytest.raises(ValueError, match="identity"):
        graph.lookup("record", {}, {"city": "A"})
    with pytest.raises(ValueError, match="type"):
        graph.lookup("record", {"id": 9}, {"city": "A"})


def test_replacement_invalidates_an_omitted_property_and_preserves_history():
    graph = EvidenceGraph(definition())
    add(graph, "old", [{"id": "same", "amount": 7}])
    change = add(graph, "new", [{"id": "same"}])
    result = graph.lookup("record", {"id": "same"}, {"city": "A"})
    assert result.records == [{"id": "same"}]
    missing = next(item for item in change["changes"] if item["property"] == "amount")
    assert missing["valid"] is False
    assert missing["reason"] == "property_missing"
    assert missing["supersedes"]["observation_id"] == "old"
    assert missing["evidence"]["observation_id"] == "new"
    gaps = graph.missing_facts(
        "record", {"id": "same"}, {"city": "A"}, ["amount"], tool_ids={"catalog.list"}
    )
    assert gaps[0]["reason"] == "property_missing"
    assert gaps[0]["sources"][0]["tool_id"] == "catalog.list"


def test_supported_partial_update_keeps_unmentioned_properties():
    graph = EvidenceGraph(definition(partial=True))
    add(graph, "old", [{"id": "same", "amount": 7}])
    add(graph, "new", [{"id": "same"}])
    result = graph.lookup("record", {"id": "same"}, {"city": "A"})
    assert result.records == [{"id": "same", "amount": 7}]
    assert any(
        ref["observation_id"] == "old" and ref["path"].endswith("/amount")
        for ref in result.evidence
    )


def test_partial_update_cannot_restore_facts_from_a_previously_absent_subject():
    graph = EvidenceGraph(definition(partial=True, coverage="flag"))
    add(graph, "old", [{"id": "same", "amount": 7}], complete=True)
    add(graph, "absent", [], complete=True)
    add(graph, "returned", [{"id": "same"}], complete=False)
    assert graph.lookup("record", {"id": "same"}, {"city": "A"}).records == [{"id": "same"}]


def test_partial_update_requires_contract_support():
    value = definition(partial=True)
    value["mappings"][0]["update_support"] = None
    with pytest.raises(ValueError):
        graph = EvidenceGraph(value)
        add(graph, "one", [{"id": "same", "amount": 7}])


def test_only_explicit_contract_can_establish_complete_collection():
    graph = EvidenceGraph(definition())
    response = observed("one", [{"id": "same", "amount": 7}])
    response["coverage"] = "complete"
    graph.add(response, arguments={"city": "A"})
    assert not graph.collection("record", {"city": "A"}).complete
    assert not graph.lookup("record", {"id": "absent"}, {"city": "A"}).complete


def test_complete_membership_is_scoped_and_can_establish_exact_absence():
    graph = EvidenceGraph(definition(coverage="complete_response"))
    add(graph, "a", [{"id": "same", "amount": 7}], city="A")
    add(graph, "b", [{"id": "same", "amount": 20}], city="B")
    add(graph, "empty", [], city="A")
    absent = graph.lookup("record", {"id": "same"}, {"city": "A"})
    assert absent.records == [] and absent.complete
    assert absent.evidence[0]["observation_id"] == "empty"
    assert absent.evidence[0]["coverage"] == "complete"
    assert graph.lookup("record", {"id": "same"}, {"city": "B"}).records[0]["amount"] == 20
    assert not graph.lookup("record", {"id": "same"}, {"city": "C"}).complete
    assert graph.missing_facts("record", {"id": "same"}, {"city": "A"}, ["amount"]) == []


@pytest.mark.parametrize("flag", [False, None])
def test_false_or_missing_coverage_flag_does_not_establish_completeness(flag):
    graph = EvidenceGraph(definition(coverage="flag"))
    data = {} if flag is None else {"complete": flag}
    add(graph, "one", [], **data)
    assert not graph.collection("record", {"city": "A"}).complete


def test_true_coverage_flag_establishes_complete_scope():
    graph = EvidenceGraph(definition(coverage="flag"))
    add(graph, "one", [], complete=True)
    assert graph.collection("record", {"city": "A"}).complete


def test_object_response_does_not_establish_population_completeness():
    value = definition(scoped=False, coverage="complete_response")
    value["mappings"][0]["collection_path"] = ""
    graph = EvidenceGraph(value)
    graph.add(
        {
            "id": "one",
            "tool_id": "catalog.list",
            "status": "succeeded",
            "coverage": "unknown",
            "data": {"id": "created", "amount": 9},
        }
    )
    assert graph.lookup("record", {"id": "created"}, {}).complete
    assert not graph.collection("record", {}).complete
    assert not graph.lookup("record", {"id": "absent"}, {}).complete


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": "new", "amount": 8}, {"id": "invalid", "amount": "9"}],
        [{"id": "new", "amount": 8}, {"amount": 9}],
        [{"id": "new", "amount": 8}, {"id": "new", "amount": 9}],
        [{"id": "new", "amount": None}],
        [{"id": "new", "amount": True}],
        "invalid collection",
    ],
)
def test_mapping_failure_publishes_no_partial_state(rows):
    graph = EvidenceGraph(definition())
    add(graph, "before", [{"id": "old", "amount": 7}])
    before = graph.snapshot()
    with pytest.raises(GraphIngestionError) as error:
        add(graph, "failed", rows)
    assert error.value.issues
    assert graph.snapshot() == before
    assert "failed" not in graph.observations


def test_invalid_coverage_flag_rolls_back_valid_rows():
    graph = EvidenceGraph(definition(coverage="flag"))
    before = graph.snapshot()
    with pytest.raises(GraphIngestionError):
        add(graph, "bad", [{"id": "new", "amount": 9}], complete="true")
    assert graph.snapshot() == before


def test_context_failure_and_record_limit_are_atomic(monkeypatch):
    graph = EvidenceGraph(definition())
    before = graph.snapshot()
    with pytest.raises(GraphIngestionError):
        graph.add(observed("missing-context", [{"id": "new", "amount": 9}]))
    assert graph.snapshot() == before
    add(graph, "one", [{"id": "one", "amount": 1}])
    before = graph.snapshot()
    monkeypatch.setattr(graph_module, "MAX_RECORDS", 1)
    with pytest.raises(GraphIngestionError):
        add(graph, "two", [{"id": "two", "amount": 2}])
    assert graph.snapshot() == before


def test_actual_arguments_are_part_of_observation_identity():
    graph = EvidenceGraph(definition())
    response = observed("one", [{"id": "same", "amount": 7}])
    graph.add(response, arguments={"city": "A"})
    assert graph.add(response, arguments={"city": "A"})["duplicate"]
    with pytest.raises(ValueError, match="different evidence"):
        graph.add(response, arguments={"city": "B"})
    with pytest.raises(ValueError, match="actual call"):
        graph.add({**response, "arguments": {"city": "A"}}, arguments={"city": "B"})
    assert graph.revision == 1


def test_data_context_and_scalar_context_types_are_preserved():
    value = definition()
    value["mappings"][0]["scope"][0].update(source="data", path="/context")
    graph = EvidenceGraph(value)
    add(graph, "integer", [{"id": "same", "amount": 7}], context=1)
    add(graph, "boolean", [{"id": "same", "amount": 9}], context=True)
    assert graph.lookup("record", {"id": "same"}, {"city": 1}).records[0]["amount"] == 7
    assert graph.lookup("record", {"id": "same"}, {"city": True}).records[0]["amount"] == 9


def test_incompatible_scope_names_are_rejected():
    value = definition()
    second = deepcopy(value["mappings"][0])
    second.update(id="other", scope=[])
    value["mappings"].append(second)
    with pytest.raises(ValueError, match="scope|context"):
        EvidenceGraph(value)


def test_sources_are_filtered_to_selected_tools_and_missing_properties():
    graph = EvidenceGraph(definition())
    assert graph.sources(entity_id="record", property="amount", tool_ids={"catalog.list"})
    assert graph.sources(entity_id="record", property="amount", tool_ids=set()) == []
    assert graph.sources(entity_id="record", property="not_mapped") == []


def test_snapshot_copies_context_and_arguments():
    graph = EvidenceGraph(definition())
    update = add(graph, "one", [{"id": "same", "amount": 7}])
    update["changes"][0]["evidence"]["context"]["city"] = "B"
    snapshot = graph.snapshot()
    snapshot["observations"][0]["arguments"]["city"] = "B"
    snapshot["entities"]["record"][0]["context"]["city"] = "B"
    snapshot["coverage"]["record"][0]["context"]["city"] = "B"
    assert graph.lookup("record", {"id": "same"}, {"city": "A"}).records
    assert all(
        ref["context"] == {"city": "A"}
        for ref in graph.lookup("record", {"id": "same"}, {"city": "A"}).evidence
    )
    assert not graph.lookup("record", {"id": "same"}, {"city": "B"}).records
