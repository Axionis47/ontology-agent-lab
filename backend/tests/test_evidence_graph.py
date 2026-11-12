from copy import deepcopy

import pytest

from oak.evidence_graph import EvidenceGraph
from oak.repair_executor import validate_candidate
from tests.test_repair_executor import candidate


def graph_candidate():
    value = candidate(True).model_dump(mode="json")
    value["requirements"]["requirements"][0]["tool_ids"].append("catalog.create")
    value["schema"]["entities"][0]["properties"].append({"name": "unrelated", "type": "string"})
    value["mappings"].append(
        {
            "id": "created",
            "entity_id": "record",
            "tool_id": "catalog.create",
            "collection_path": "",
            "fields": deepcopy(value["mappings"][0]["fields"]),
        }
    )
    return value


def observation(identifier, data, tool="catalog.list", status="succeeded", coverage="sample"):
    return {"id": identifier, "tool_id": tool, "status": status, "coverage": coverage, "data": data}


def test_action_object_updates_same_graph_and_is_immediately_usable():
    graph = EvidenceGraph(graph_candidate())
    graph.add(observation("read", {"items": [{"id": "old", "amount": 2}]}))
    change = graph.add(observation("write", {"id": "booked", "amount": 9}, "catalog.create"))
    result = graph.execute("select_records", {"minimum": 5})
    assert result["status"] == "complete"
    assert result["value"] == [{"id": "booked", "amount": 9}]
    assert result["graph_revision"] == change["revision"] == 2
    assert result["coverage"] == "observed"
    assert any(ref["observation_id"] == "write" for ref in result["evidence_refs"])
    assert graph.snapshot()["entities"]["record"][1]["evidence"]["amount"]["path"] == "/amount"


def test_repeated_observation_updates_properties_and_keeps_history():
    graph = EvidenceGraph(graph_candidate())
    first = observation("first", {"items": [{"id": "same", "amount": 7}]})
    graph.add(first)
    graph.add(observation("second", {"items": [{"id": "same", "amount": 10}]}))
    result = graph.execute("select_records", {"minimum": 5})
    assert result["value"] == [{"id": "same", "amount": 10}]
    assert result["graph_revision"] == 2
    history = graph.snapshot()["history"]
    assert history[-1]["supersedes"]["observation_id"] == "first"
    assert graph.add(first)["duplicate"]
    assert graph.revision == 2
    with pytest.raises(ValueError, match="different evidence"):
        graph.add(observation("first", {"items": []}))


@pytest.mark.parametrize("value", [None, True, "9", 9.5])
def test_invalid_later_value_does_not_leave_old_value_usable(value):
    graph = EvidenceGraph(graph_candidate())
    graph.add(observation("first", {"items": [{"id": "same", "amount": 7}]}))
    graph.add(observation("second", {"items": [{"id": "same", "amount": value}]}))
    result = graph.execute("select_records", {"minimum": 5})
    assert result["status"] == "incomplete"
    assert result["missing_dependencies"]
    assert "amount" not in graph.snapshot()["entities"]["record"][0]["values"]


@pytest.mark.parametrize("status", ["failed", "unknown"])
def test_unsuccessful_call_is_evidence_but_does_not_publish_success_facts(status):
    graph = EvidenceGraph(graph_candidate())
    change = graph.add(
        observation("write", {"id": "invented", "amount": 9}, "catalog.create", status)
    )
    assert change["changes"] == []
    assert graph.execute("select_records", {"minimum": 5})["status"] == "incomplete"


def test_missing_used_field_blocks_but_missing_unrelated_field_does_not():
    graph = EvidenceGraph(graph_candidate())
    graph.add(observation("one", {"items": [{"id": "new"}]}))
    assert graph.execute("select_records", {"minimum": 5})["status"] == "incomplete"
    graph.add(observation("two", {"id": "new", "amount": 8}, "catalog.create"))
    assert graph.execute("select_records", {"minimum": 5})["value"] == [{"id": "new", "amount": 8}]


def test_complete_collection_membership_changes_without_erasing_history():
    graph = EvidenceGraph(graph_candidate())
    graph.add(observation("first", {"items": [{"id": "old", "amount": 7}]}, coverage="complete"))
    graph.add(observation("second", {"items": [{"id": "new", "amount": 10}]}, coverage="complete"))
    assert graph.execute("select_records", {"minimum": 5})["value"] == [{"id": "new", "amount": 10}]
    assert len(graph.snapshot()["history"]) == 4


def test_aggregate_requires_complete_scoped_evidence():
    value = candidate().model_dump(mode="json")
    function = value["functions"][0]
    function["steps"][-1] = {
        "op": "aggregate",
        "id": "result",
        "input": "records",
        "operation": "count",
    }
    function["output"] = {"kind": "scalar", "type": "integer"}
    graph = EvidenceGraph(value)
    graph.add(observation("sample", {"items": [{"id": "a", "amount": 1}]}))
    assert graph.execute("select_records", {"minimum": 5})["status"] == "incomplete"
    graph.add(observation("complete", {"items": [{"id": "a", "amount": 1}]}, coverage="complete"))
    assert graph.execute("select_records", {"minimum": 5})["value"] == 1
    graph.add(
        observation("different-query", {"items": [{"id": "b", "amount": 1}]}, coverage="complete"),
        scope="other",
    )
    assert graph.execute("select_records", {"minimum": 5})["status"] == "incomplete"


def test_mapping_still_requires_known_fields_and_identity():
    value = graph_candidate()
    assert validate_candidate(value, {"catalog.list", "catalog.create"}, {"minimum"}) == []
    value["mappings"][0]["fields"] = [{"property": "amount", "path": "/amount"}]
    assert (
        "identity" in validate_candidate(value, {"catalog.list", "catalog.create"}, {"minimum"})[0]
    )


def test_conflicting_duplicate_identity_cannot_choose_a_source_row():
    graph = EvidenceGraph(graph_candidate())
    change = graph.add(
        observation(
            "duplicate",
            {
                "items": [
                    {"id": "same", "amount": 1},
                    {"id": "same", "amount": 9},
                ]
            },
        )
    )
    assert any(issue["reason"] == "duplicate_identity" for issue in change["issues"])
    assert graph.execute("select_records", {"minimum": 5})["status"] == "incomplete"


def test_empty_complete_collection_retains_source_evidence():
    graph = EvidenceGraph(graph_candidate())
    graph.add(observation("empty", {"items": []}, coverage="complete"))
    result = graph.execute("select_records", {"minimum": 5})
    assert result["status"] == "complete"
    assert result["value"] == []
    assert result["evidence_refs"][0]["observation_id"] == "empty"


def test_graph_holds_immutable_candidate_and_returns_snapshot_copies():
    value = graph_candidate()
    graph = EvidenceGraph(value)
    value["functions"] = []
    graph.add(observation("write", {"id": "booked", "amount": 9}, "catalog.create"))
    snapshot = graph.snapshot()
    snapshot["entities"]["record"][0]["values"]["amount"] = 0
    assert graph.execute("select_records", {"minimum": 5})["value"][0]["amount"] == 9
