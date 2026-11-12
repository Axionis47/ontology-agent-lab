"""Check the agent-side contract for unchanged external MCP packages."""

import json
import sqlite3
from pathlib import Path

import pytest

from .hook import handle
from .kernel import Candidate
from .sql_kernel import prepare_database
from .suite import make_suite, reference


@pytest.fixture
def episode(tmp_path):
    case = make_suite("guard", 48, 1)[0]
    candidate = Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())
    database = tmp_path / "episode.db"
    prepare_database(case, candidate, database)
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(case))
    return case, {
        "case_path": str(case_path),
        "database_path": str(database),
        "answer_path": str(tmp_path / "answer.json"),
        "state_path": str(tmp_path / "state.json"),
        "mode": "strict",
    }


def call(config, name, args, response=None):
    before = handle(
        config, {"hook_event_name": "BeforeTool", "tool_name": name, "tool_input": args}
    )
    if before["decision"] == "allow":
        handle(
            config,
            {
                "hook_event_name": "AfterTool",
                "tool_name": name,
                "tool_input": args,
                "tool_response": response or {},
            },
        )
    return before


def test_guard_rejects_bypass_and_records_wrong_proposal(episode):
    case, config = episode
    assert (
        call(config, "mcp_sqlite_read-query", {"query": "DROP TABLE hotel"})["decision"] == "deny"
    )
    wrong = {"status": "complete", "eligible": []}
    assert (
        call(
            config,
            "mcp_filesystem_write_file",
            {"path": config["answer_path"], "content": json.dumps(wrong)},
        )["decision"]
        == "deny"
    )
    state = json.loads(Path(config["state_path"]).read_text())
    assert state["first_proposal"] == wrong
    assert state["answer"] is None


def test_strict_requires_computation_and_rejects_source_change(episode):
    case, config = episode
    for table in ("hotel", "offer", "policy"):
        assert (
            call(config, "mcp_sqlite_read-query", {"query": f"SELECT * FROM {table}"})["decision"]
            == "allow"
        )
    expected = reference(case)
    answer = {
        "status": expected["status"],
        "eligible": [
            {"offer_id": key, "total_cents": value} for key, value in expected["eligible"].items()
        ],
    }
    event = {
        "hook_event_name": "BeforeTool",
        "tool_name": "mcp_filesystem_write_file",
        "tool_input": {"path": config["answer_path"], "content": json.dumps(answer)},
    }
    assert handle(config, event)["decision"] == "deny"
    call(config, "mcp_sqlite_read-query", {"query": "SELECT * FROM eligible_stays"})
    assert handle(config, event)["decision"] == "allow"
    Path(config["answer_path"]).write_text(json.dumps(answer))
    handle(config, {**event, "hook_event_name": "AfterTool", "tool_response": {}})
    with sqlite3.connect(config["database_path"]) as connection:
        connection.execute("UPDATE offer SET nightly_cents=nightly_cents+1")
    assert handle(config, event)["decision"] == "deny"


def test_sqlite_text_error_does_not_establish_read(episode):
    _, config = episode
    call(
        config,
        "mcp_sqlite_read-query",
        {"query": "SELECT * FROM hotel"},
        {"llmContent": [{"text": "Error: connection failed"}]},
    )
    state = json.loads(Path(config["state_path"]).read_text())
    assert state["read_tables"] == []


def test_guard_keeps_null_as_the_first_proposal(episode):
    _, config = episode
    for content in ("null", '{"status":"complete","eligible":[]}'):
        result = call(
            config,
            "mcp_filesystem_write_file",
            {"path": config["answer_path"], "content": content},
        )
        assert result["decision"] == "deny"
    state = json.loads(Path(config["state_path"]).read_text())
    assert state["first_proposal"] is None
    assert state["proposals"] == [None, {"status": "complete", "eligible": []}]
