"""Check local OaK infrastructure without models or persistent domain-data writes."""

from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def check_contracts() -> dict:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError

    class Request(BaseModel):
        model_config = ConfigDict(strict=True)
        people: int = Field(ge=1)

    assert Request(people=4).people == 4
    for invalid in (0, "4"):
        try:
            Request(people=invalid)
        except ValidationError:
            continue
        raise AssertionError("Strict request validation accepted invalid input")
    return {"valid_input": "accepted", "zero_and_string_inputs": "rejected"}


def check_workflow() -> dict:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    class State(TypedDict):
        value: int
        reviewed: bool

    def prepare(state: State) -> dict:
        return {"value": state["value"] + 1}

    def review(state: State) -> dict:
        decision = interrupt({"kind": "installation_probe", "value": state["value"]})
        return {"reviewed": decision is True}

    builder = StateGraph(State)
    builder.add_node("prepare", prepare)
    builder.add_node("review", review)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "review")
    builder.add_edge("review", END)
    config = {"configurable": {"thread_id": str(uuid4())}}
    with tempfile.TemporaryDirectory(prefix="oak-checkpoint-probe-") as tmp:
        path = str(Path(tmp) / "checkpoints.sqlite")
        with SqliteSaver.from_conn_string(path) as saver:
            workflow = builder.compile(checkpointer=saver)
            paused = workflow.invoke({"value": 2, "reviewed": False}, config)
            assert paused["__interrupt__"]
            resumed = workflow.invoke(Command(resume=True), config)
            assert resumed["value"] == 3 and resumed["reviewed"] is True
        with SqliteSaver.from_conn_string(path) as saver:
            recovered = builder.compile(checkpointer=saver).get_state(config)
            assert recovered.values == {"value": 3, "reviewed": True}
    return {"pause_resume": "passed", "checkpoint_reopen": "passed"}


def check_neo4j() -> dict:
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    probe_id = str(uuid4())
    with GraphDatabase.driver(
        uri,
        auth=(os.environ.get("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        connection_timeout=10,
    ) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            version = session.run(
                "CALL dbms.components() YIELD versions RETURN versions[0] AS version"
            ).single()["version"]
            with session.begin_transaction() as tx:
                try:
                    tx.run(
                        "CREATE (a:OakSetupProbe {probe_id: $id, capacity: 4}) "
                        "CREATE (b:OakSetupProbe {probe_id: $id, name: 'FixtureCity'}) "
                        "CREATE (a)-[:OAK_SETUP_LOCATED_IN]->(b)",
                        id=probe_id,
                    ).consume()
                    row = tx.run(
                        "MATCH (a:OakSetupProbe {probe_id: $id})"
                        "-[:OAK_SETUP_LOCATED_IN]->(b:OakSetupProbe {probe_id: $id}) "
                        "WHERE a.capacity >= $people RETURN b.name AS city",
                        id=probe_id,
                        people=4,
                    ).single()
                    assert row["city"] == "FixtureCity"
                finally:
                    tx.rollback()
            remaining = session.run(
                "MATCH (n:OakSetupProbe {probe_id: $id}) RETURN count(n) AS remaining",
                id=probe_id,
            ).single()["remaining"]
            assert remaining == 0
    return {"server_version": version, "query": "passed", "probe_nodes_remaining": 0}


def check_reasoner() -> dict:
    import owlready2 as owl

    java_home = os.environ.get("JAVA_HOME")
    java = str(Path(java_home) / "bin/java") if java_home else shutil.which("java")
    if not java:
        raise RuntimeError("Configure JAVA_HOME for HermiT")
    version = subprocess.run(
        [java, "-version"], capture_output=True, text=True, check=True, timeout=15
    )
    owl.JAVA_EXE = java
    world = owl.World()
    try:
        onto = world.get_ontology(f"https://example.org/oak/setup/{uuid4()}#")
        with onto:

            class Accommodation(owl.Thing):
                pass

            class Room(owl.Thing):
                pass

            class City(owl.Thing):
                pass

            class offers(owl.ObjectProperty):
                domain = [Accommodation]  # noqa: RUF012 - Owlready2 class declaration
                range = [Room]  # noqa: RUF012 - Owlready2 class declaration

            class Hotel(owl.Thing):
                equivalent_to = [Accommodation & offers.some(Room)]  # noqa: RUF012

            owl.AllDisjoint([Hotel, City])
            cedar = Accommodation("cedar")
            cedar.offers = [Room("room")]
        assert Hotel not in cedar.is_a
        owl.sync_reasoner(world, debug=0)
        assert Hotel in cedar.is_a
        cedar.is_a.append(City)
        try:
            owl.sync_reasoner(world, debug=0)
        except owl.OwlReadyInconsistentOntologyError:
            pass
        else:
            raise AssertionError("HermiT did not reject the deliberate contradiction")
    finally:
        world.close()
    return {
        "java": (version.stderr or version.stdout).splitlines()[0],
        "distribution": "Owlready2 bundled HermiT",
        "inferred_class": "passed",
        "contradiction_detection": "passed",
    }


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    # Infrastructure probes must never upload traces or make model calls.
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    report = {
        "kind": "installation_probe_not_benchmark",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "packages": {},
        "checks": {},
        "model_calls": 0,
        "hosted_trace_uploads": 0,
    }
    for package in (
        "langgraph",
        "langgraph-checkpoint-sqlite",
        "langgraph-cli",
        "langsmith",
        "neo4j",
        "pydantic",
        "owlready2",
        "httpx",
        "python-dotenv",
    ):
        report["packages"][package] = importlib.metadata.version(package)
    for name, check in (
        ("contracts", check_contracts),
        ("workflow", check_workflow),
        ("neo4j", check_neo4j),
        ("hermit", check_reasoner),
    ):
        try:
            report["checks"][name] = {"status": "passed", **check()}
        except Exception as exc:  # noqa: BLE001 - record each failed infrastructure probe
            # Avoid printing connection details, credentials, or environment values.
            report["checks"][name] = {"status": "failed", "error_type": type(exc).__name__}
        print(name + ": " + report["checks"][name]["status"], flush=True)
    configured = bool(os.environ.get("LANGSMITH_API_KEY"))
    report["langsmith"] = {
        "sdk": "installed",
        "api_key_present": configured,
        "project_configured": bool(os.environ.get("LANGSMITH_PROJECT")),
        "hosted_connection": "not_tested" if configured else "requires_user_api_key",
    }
    output = ROOT / ".runtime/setup-check.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(any(c["status"] != "passed" for c in report["checks"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
