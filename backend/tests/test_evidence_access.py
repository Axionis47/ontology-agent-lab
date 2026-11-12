"""Check bounded views, exact retrieval, and complete retained evidence."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from oak.evidence_access import (
    ContextCapacity,
    EvidenceStore,
    bounded_context,
    generate_with_evidence,
    size,
)


def test_large_array_remains_complete_and_can_be_read_by_exact_pointer():
    store = EvidenceStore()
    original = {
        "items": [{"id": str(i), "body": "x" * 500} for i in range(1000)],
        "raw": "original",
    }
    view = store.view("observation-1", original)
    assert size(view) <= 4096 and view["omitted"]
    item = store.read({"id": "observation-1", "path": "/items/999"})
    assert item["value"] == original["items"][999]
    assert store.records["observation-1"] == original


def test_array_pages_preserve_positions_and_escaped_fields():
    store = EvidenceStore()
    store.save("o", {"a/b~c": list(range(1000))})
    first = store.read({"id": "o", "path": "/a~1b~0c", "limit": 4}, 600)
    assert [i["value"] for i in first["items"]] == [0, 1, 2, 3]
    second = store.read(
        {"id": "o", "path": "/a~1b~0c", "offset": first["next_offset"], "limit": 4}, 600
    )
    assert second["items"][0]["path"] == "/a~1b~0c/4"


def test_text_ranges_and_search_do_not_claim_source_completeness():
    store = EvidenceStore()
    store.save("o", "x" * 5000 + "decisive answer" + "y" * 5000)
    view = store.read({"id": "o", "search": "decisive", "limit": 15})
    assert view["offset"] == 5000 and view["value"] == "decisive answer"
    assert view["omitted"] and view["next_offset"]


def test_reader_cannot_cross_run_or_replace_saved_evidence():
    store = EvidenceStore()
    store.save("current", {"secret": "[redacted]"})
    with pytest.raises(ValueError, match="unavailable"):
        store.read({"id": "another-run"})
    with pytest.raises(ValueError, match="cannot change"):
        store.save("current", {})
    with pytest.raises(ValueError, match="redacted"):
        store.read({"id": "current", "path": "/secret"})


def test_context_keeps_query_and_marks_unseen_evidence():
    store = EvidenceStore()
    data = {"query": "Exclude cancelled records.", "observations": ["payload" * 1000] * 20}
    view, omitted = bounded_context(data, store, 1000)
    assert omitted and view["query"] == data["query"]
    assert view["observations"]["omitted"]
    with pytest.raises(ContextCapacity, match="Mandatory"):
        bounded_context({"query": "q" * 2000}, store, 500)


async def test_large_structured_input_requests_decisive_saved_evidence():
    class Judgment(BaseModel):
        answer: str

    data = {
        "query": "Read the last value.",
        "observations": [{"text": "noise" * 1000}] * 200 + [{"text": "answer"}],
    }
    calls, events = [], []

    async def emit(kind, value):
        events.append((kind, value))

    async def generate(**kwargs):
        calls.append(kwargs)
        context = kwargs["data"]
        if not context["evidence_views"]:
            ref = context["observations"]["evidence_ref"]
            result = {"evidence_requests": [{**ref, "path": ref["path"] + "/200/text"}]}
        else:
            result = {"result": {"answer": context["evidence_views"][0]["value"]}}
        return SimpleNamespace(data=kwargs["response_schema"].model_validate(result))

    result = await generate_with_evidence(
        generate,
        instructions="Judge saved evidence.",
        data=data,
        response_schema=Judgment,
        input_tokens=8192,
        emit=emit,
    )
    assert result.data.answer == "answer"
    assert len(calls) == 2
    assert all(size(c["data"]) < 8192 for c in calls)
    assert any(kind == "evidence_read" for kind, _ in events)
    assert events[1][1]["value"] == data


def test_partial_text_cannot_authorize_replacing_a_declaration():
    store = EvidenceStore()
    store.save("candidate", {"definition": "x" * 7000})
    store.read({"id": "candidate", "path": "/definition", "limit": 1000})
    assert not store.inspected("candidate", "/definition")
    for offset in range(1000, 7000, 1000):
        store.read({"id": "candidate", "path": "/definition", "offset": offset, "limit": 1000})
    assert store.inspected("candidate", "/definition")


def test_search_has_bounded_scan_and_continues_without_false_absence():
    store = EvidenceStore()
    store.save("saved", ["noise"] * 1500 + ["decisive"])
    first = store.read({"id": "saved", "search": "decisive"})
    assert first["items"] == [] and first["next_offset"] == 1000 and first["omitted"]
    second = store.read({"id": "saved", "search": "decisive", "offset": first["next_offset"]})
    assert second["items"][0]["path"] == "/1500"


async def test_construction_cannot_replace_an_unread_large_declaration():
    class Change(BaseModel):
        op: str
        collection: str
        id: str

    class Revision(BaseModel):
        changes: list[Change]

    async def generate(**kwargs):
        return SimpleNamespace(
            data=kwargs["response_schema"].model_validate(
                {"result": {"changes": [{"op": "replace", "collection": "functions", "id": "f"}]}}
            )
        )

    async def emit(*args):
        pass

    with pytest.raises(ValueError, match="Inspect the complete declaration"):
        await generate_with_evidence(
            generate,
            instructions="Revise this declaration.",
            data={
                "current_candidate": {
                    "schema": {},
                    "functions": [{"id": "f", "definition": "x" * 50000}],
                }
            },
            response_schema=Revision,
            input_tokens=8192,
            emit=emit,
        )


async def test_unread_decisive_evidence_makes_evaluation_inconclusive():
    from oak.training_evaluation import TaskEvaluation

    async def generate(**kwargs):
        return SimpleNamespace(
            data=kwargs["response_schema"].model_validate(
                {
                    "result": {
                        "status": "passed",
                        "reason": "Assumed from the omitted result.",
                        "evidence_refs": [
                            {
                                "source": "artifact",
                                "id": "episode",
                                "path": "/result/observations/0",
                            }
                        ],
                    }
                }
            )
        )

    async def emit(*args):
        pass

    result = await generate_with_evidence(
        generate,
        instructions="Judge only the observed outcome.",
        data={"query": "Report the outcome.", "result": {"observations": ["x" * 100000]}},
        response_schema=TaskEvaluation,
        input_tokens=8192,
        emit=emit,
    )
    assert result.data.status == "inconclusive"


async def test_missing_saved_evidence_returns_unavailable_without_external_execution():
    class Answer(BaseModel):
        status: str

    async def generate(**kwargs):
        views = kwargs["data"]["evidence_views"]
        result = {"evidence_requests": [{"id": "not-in-this-run"}]}
        if views:
            assert views[-1]["status"] == "unavailable" and views[-1]["omitted"]
            result = {"result": {"status": "inconclusive"}}
        return SimpleNamespace(data=kwargs["response_schema"].model_validate(result))

    async def emit(*args):
        pass

    result = await generate_with_evidence(
        generate,
        instructions="Inspect saved evidence.",
        data={"observations": ["x" * 100000]},
        response_schema=Answer,
        input_tokens=8192,
        emit=emit,
    )
    assert result.data.status == "inconclusive"
