import ast
import json
import sqlite3
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from . import native
from .kernel import Candidate, load_cases
from .native import prepare_episode, run_native

BACKEND = Path(__file__).resolve().parents[2]
SQLITE = BACKEND / ".local/real-mcp/sqlite-venv/bin/mcp-server-sqlite"
FILESYSTEM = BACKEND / ".local/real-mcp/node_modules/.bin/mcp-server-filesystem"
pytestmark = pytest.mark.skipif(
    not SQLITE.is_file() or not FILESYSTEM.is_file(), reason="Install the existing MCP servers."
)


def fixture():
    candidate = Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())
    return candidate, load_cases()["held_out"]


async def test_existing_mcp_servers_read_generated_view_and_take_local_action(tmp_path):
    candidate, case = fixture()
    prepare_episode(case, candidate, "full", tmp_path)
    database = tmp_path / "episode.db"
    params = StdioServerParameters(command=str(SQLITE), args=["--db-path", str(database)])
    async with Client(params, mode="legacy") as client:
        catalog = {tool.name for tool in (await client.list_tools()).tools}
        assert {"read_query", "write_query"} <= catalog
        response = await client.call_tool("read_query", {"query": "SELECT * FROM eligible_stays"})
        rows = ast.literal_eval(response.content[0].text)
        assert {row["offer_id"]: row["total_cents"] for row in rows} == case["expected"]
        response = await client.call_tool(
            "write_query",
            {
                "query": (
                    "INSERT INTO reservations "
                    "(reservation_id,offer_id,total_cents,idempotency_key) "
                    "VALUES ('r1','exact_boundary',50000,'k1')"
                )
            },
        )
        assert "Error:" not in response.content[0].text
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT offer_id FROM reservations").fetchone() == (
            "exact_boundary",
        )
    output = tmp_path / "gemini-workspace/output"
    params = StdioServerParameters(command=str(FILESYSTEM), args=[str(output)])
    async with Client(params, mode="legacy") as client:
        catalog = {tool.name for tool in (await client.list_tools()).tools}
        assert {"read_text_file", "write_file"} <= catalog
        content = json.dumps({"status": "complete", "eligible": rows})
        response = await client.call_tool(
            "write_file",
            {
                "path": str(output / "answer.json"),
                "content": content,
            },
        )
        assert not response.is_error
        assert (output / "answer.json").read_text() == content


def test_native_config_uses_only_existing_servers_and_keeps_gold_private(tmp_path):
    candidate, case = fixture()
    adapter, _ = prepare_episode(case, candidate, "strict", tmp_path)
    settings = json.loads(adapter.settings.read_text())
    assert settings["mcp"]["allowed"] == ["sqlite", "filesystem"]
    assert settings["mcpServers"]["sqlite"]["includeTools"] == ["read_query", "write_query"]
    assert settings["mcpServers"]["filesystem"]["includeTools"] == ["read_text_file", "write_file"]
    assert settings["mcpServers"]["filesystem"]["args"] == [
        str(tmp_path / "gemini-workspace/output")
    ]
    assert settings["tools"]["core"] == [
        "mcp_sqlite_read_query",
        "mcp_sqlite_write_query",
        "mcp_filesystem_read_text_file",
        "mcp_filesystem_write_file",
    ]
    assert settings["hooksConfig"]["enabled"]
    assert set(settings["hooks"]) == {"BeforeTool", "AfterTool"}
    assert settings["model"]["maxSessionTurns"] == 12
    assert adapter.environment["OAK_REQUIRE_TASK_GUARD"] == "1"
    assert "expected" not in json.loads((tmp_path / "public-case.json").read_text())
    assert list((tmp_path / "gemini-workspace/output").iterdir()) == []
    assert (
        settings["modelConfigs"]["customOverrides"][0]["modelConfig"]["generateContentConfig"][
            "maxOutputTokens"
        ]
        == 8192
    )


async def test_native_cli_argument_boundaries_without_network(tmp_path, monkeypatch):
    candidate, case = fixture()
    fake = tmp_path / "fake-gemini"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "assert '--allowed-mcp-server-names=sqlite' in sys.argv\n"
        "assert '--allowed-mcp-server-names=filesystem' in sys.argv\n"
        "assert 'filesystem' not in sys.argv\n"
        "prompt=sys.stdin.read()\n"
        "assert 'mcp_sqlite_read_query' in prompt\n"
        "assert 'SELECT * FROM eligible_stays' in prompt\n"
        "print(json.dumps({'response':'local adapter test','stats':{'tools':{'totalCalls':0}}}))\n"
    )
    fake.chmod(0o700)
    monkeypatch.setenv("OAK_GEMINI_CLI", str(fake))
    monkeypatch.setattr(native, "require_guard_patch", lambda command: None)
    result = await run_native(case, candidate, "strict", tmp_path / "episode")
    assert result["cli_exit_code"] == 0
    assert result["native_tool_calls"] == 0
    assert not result["completed"]
