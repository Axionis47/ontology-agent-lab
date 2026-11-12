import asyncio
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from oak import ontology_verification as verifier
from oak.ontology_worker import verify_file


def candidate(axioms=()):
    return {
        "requirements": {"requirements": [{"id": "requirement"}]},
        "schema": {
            "entities": [
                {
                    "id": name,
                    "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "enabled", "type": "boolean"},
                    ],
                    "identity_keys": ["id"],
                }
                for name in ("a", "b")
            ],
            "relations": [
                {
                    "id": "r",
                    "from_entity": "a",
                    "to_entity": "b",
                    "from_property": "id",
                    "to_property": "id",
                }
            ],
        },
        "formal_axioms": list(axioms),
    }


def axiom(identifier, kind, **fields):
    return {"id": identifier, "kind": kind, "requirement_ids": ["requirement"], **fields}


@pytest.fixture(autouse=True)
def isolated_lock(monkeypatch):
    monkeypatch.setattr(verifier, "_PROCESS_LOCK", asyncio.Lock())


@pytest.fixture
def java(monkeypatch):
    homebrew = Path("/opt/homebrew/opt/openjdk@21/bin/java")
    selected = os.environ.get("OAK_JAVA") or (str(homebrew) if homebrew.exists() else "java")
    monkeypatch.setenv("OAK_JAVA", selected)
    return selected


def test_encoder_is_deterministic_and_emits_no_instances_or_imports():
    first = candidate([axiom("disjoint", "disjoint", entity_id="a", target_entity_id="b")])
    second = deepcopy(first)
    second["schema"]["entities"].reverse()
    for entity in second["schema"]["entities"]:
        entity["properties"].reverse()
    text = verifier.encode_ontology(first)
    assert verifier.encode_ontology(second) == text
    assert verifier.formal_schema_digest(second) == verifier.formal_schema_digest(first)
    root = ET.fromstring(text)
    assert not any(node.tag.endswith(("}NamedIndividual", "}imports")) for node in root.iter())
    assert "XMLSchema#integer" in text
    assert "XMLSchema#boolean" in text
    assert "urn:oak:property:a/id" in text and "urn:oak:property:b/id" in text
    assert first == candidate([axiom("disjoint", "disjoint", entity_id="a", target_entity_id="b")])


@pytest.mark.parametrize("kind", ["object", "array", "number"])
async def test_unsupported_property_type_is_a_source_error(kind):
    value = candidate()
    value["schema"]["entities"][0]["properties"][0]["type"] = kind
    report = await verifier.verify_candidate(value)
    assert report["status"] == "invalid"
    assert report["errors"][0]["declaration_id"] == "a"
    assert report["versions"] == {"encoder": verifier.ENCODER_VERSION}


@pytest.mark.parametrize(
    "bad",
    [
        axiom("bad", "transitive", relation_id="r"),
        axiom("bad", "functional", relation_id="unknown"),
        axiom("bad", "subclass", entity_id="a", target_entity_id="unknown"),
        axiom("bad", "disjoint", entity_id="a", target_entity_id="a"),
        axiom(
            "bad",
            "restriction",
            entity_id="a",
            relation_id="r",
            target_entity_id="b",
            restriction="min",
            cardinality=True,
        ),
        axiom(
            "bad",
            "restriction",
            entity_id="a",
            relation_id="r",
            target_entity_id="b",
            restriction="only",
            cardinality=1,
        ),
        {"id": "bad", "kind": "functional", "relation_id": "r", "requirement_ids": ["unknown"]},
    ],
)
async def test_unsupported_axiom_returns_correctable_error(bad):
    report = await verifier.verify_candidate(candidate([bad]))
    assert report["status"] == "invalid"
    assert report["errors"][0]["declaration_id"] == "bad"


async def test_property_profile_limit_is_enforced():
    value = candidate()
    value["schema"]["entities"][0]["properties"] += [
        {"name": f"p{index}", "type": "integer"} for index in range(verifier.MAX_PROPERTIES)
    ]
    report = await verifier.verify_candidate(value)
    assert report["status"] == "invalid"
    assert "300" in report["errors"][0]["message"]


async def test_real_hermit_accepts_supported_schema(java):
    value = candidate(
        [
            axiom("disjoint", "disjoint", entity_id="a", target_entity_id="b"),
            axiom(
                "exists",
                "restriction",
                entity_id="a",
                target_entity_id="b",
                relation_id="r",
                restriction="some",
            ),
            axiom(
                "only",
                "restriction",
                entity_id="a",
                target_entity_id="b",
                relation_id="r",
                restriction="only",
            ),
            axiom(
                "exact",
                "restriction",
                entity_id="a",
                target_entity_id="b",
                relation_id="r",
                restriction="exactly",
                cardinality=1,
            ),
            axiom("functional", "functional", relation_id="r"),
            axiom("inverse-functional", "inverse_functional", relation_id="r"),
            axiom("inverse", "inverse", relation_id="r", inverse_relation_id="reverse"),
        ]
    )
    value["schema"]["relations"].append(
        {
            "id": "reverse",
            "from_entity": "b",
            "to_entity": "a",
            "from_property": "id",
            "to_property": "id",
        }
    )
    report = await verifier.verify_candidate(value)
    assert report["status"] == "passed", report
    assert report["errors"] == report["unsatisfiable_classes"] == []
    assert report["versions"]["owlready2"] == "0.51"
    assert report["versions"]["hermit"]
    assert report["versions"]["java"]
    assert len(report["versions"]["hermit_jar_sha256"]) == 64
    assert report["schema_digest"] == verifier.formal_schema_digest(value)
    assert "individuals" not in report


async def test_real_hermit_rejects_unsatisfiable_declared_class(java):
    value = candidate(
        [
            axiom("subtype", "subclass", entity_id="a", target_entity_id="b"),
            axiom("disjoint", "disjoint", entity_id="a", target_entity_id="b"),
        ]
    )
    report = await verifier.verify_candidate(value)
    assert report["status"] == "invalid", report
    assert report["unsatisfiable_classes"] == ["a"]
    assert report["errors"][0]["code"] == "unsatisfiable_classes"


@pytest.mark.parametrize("upper", ["cardinality", "functional"])
async def test_real_hermit_checks_restrictions_and_property_features(java, upper):
    axioms = [
        axiom(
            "lower",
            "restriction",
            entity_id="a",
            target_entity_id="b",
            relation_id="r",
            restriction="min",
            cardinality=2,
        )
    ]
    axioms.append(
        axiom(
            "upper",
            "restriction",
            entity_id="a",
            target_entity_id="b",
            relation_id="r",
            restriction="max",
            cardinality=1,
        )
        if upper == "cardinality"
        else axiom("upper", "functional", relation_id="r")
    )
    report = await verifier.verify_candidate(candidate(axioms))
    assert report["status"] == "invalid", report
    assert report["unsatisfiable_classes"] == ["a"]


def test_real_hermit_worker_detects_global_inconsistency(java, tmp_path):
    # The generated profile has no individuals. This fixture tests the worker separately.
    path = tmp_path / "inconsistent.owl"
    path.write_text("""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
 <owl:Ontology rdf:about="urn:test:global"/>
 <owl:Class rdf:about="http://www.w3.org/2002/07/owl#Thing">
  <rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Nothing"/>
 </owl:Class>
</rdf:RDF>""")
    report = verify_file(path, 128)
    assert report["status"] == "invalid", report
    assert report["errors"][0]["code"] == "inconsistent_ontology"


async def test_missing_java_is_an_infrastructure_failure(monkeypatch):
    monkeypatch.setenv("OAK_JAVA", "/nonexistent/oak-java")
    report = await verifier.verify_candidate(candidate())
    assert report["status"] == "infrastructure_error"
    assert report["errors"][0]["code"] == "missing_java"
    assert report["owl"] and report["schema_digest"]


@pytest.mark.parametrize(
    "code", ["print('not-json')", "raise SystemExit(7)", "print('{}')", "print('[]')"]
)
async def test_worker_failure_never_becomes_permission(monkeypatch, code):
    monkeypatch.setattr(verifier, "_worker_command", lambda *_: [sys.executable, "-c", code])
    report = await verifier.verify_candidate(candidate())
    assert report["status"] == "infrastructure_error"
    assert report["errors"][0]["code"] == "worker_failure"


async def test_waiting_for_process_lock_counts_against_deadline(monkeypatch):
    async with verifier._PROCESS_LOCK:
        report = await verifier.verify_candidate(candidate(), timeout=0.01)
    assert report["status"] == "infrastructure_error"
    assert report["errors"][0]["code"] == "verification_timeout"


async def test_cancellation_during_process_start_reaps_created_worker(monkeypatch):
    real_create = asyncio.create_subprocess_exec
    started = asyncio.Event()
    processes = []

    async def create(*args, **kwargs):
        process = await real_create(*args, **kwargs)
        processes.append(process)
        started.set()
        await asyncio.sleep(0.05)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(
        verifier,
        "_worker_command",
        lambda *_: [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    task = asyncio.create_task(verifier.verify_candidate(candidate()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert processes[0].returncode is not None
    assert not verifier._PROCESS_LOCK.locked()


@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancellation_kill_worker_and_child(monkeypatch, tmp_path, cancel):
    marker = tmp_path / "processes.json"
    code = (
        "import os,subprocess,sys,time,json; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid])); "
        "time.sleep(60)"
    )
    monkeypatch.setattr(verifier, "_worker_command", lambda *_: [sys.executable, "-c", code])
    task = asyncio.create_task(
        verifier.verify_candidate(candidate(), timeout=10 if cancel else 0.5)
    )
    for _ in range(100):
        if marker.exists():
            break
        await asyncio.sleep(0.01)
    assert marker.exists()
    if cancel:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        report = await task
        assert report["errors"][0]["code"] == "verification_timeout"
    for pid in json.loads(marker.read_text()):
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    assert not verifier._PROCESS_LOCK.locked()


async def test_only_one_worker_runs_at_a_time(monkeypatch):
    maximum = active = 0
    real_create = asyncio.create_subprocess_exec
    output = json.dumps(
        {
            "status": "passed",
            "versions": {
                "owlready2": "test",
                "hermit": "test",
                "hermit_jar_sha256": "test",
                "java": "test",
            },
            "errors": [],
            "unsatisfiable_classes": [],
        }
    )
    command = [sys.executable, "-c", f"import time; time.sleep(0.05); print({output!r})"]
    monkeypatch.setattr(verifier, "_worker_command", lambda *_: command)

    async def create(*args, **kwargs):
        nonlocal active, maximum
        process = await real_create(*args, **kwargs)
        original = process.communicate
        active += 1
        maximum = max(maximum, active)

        async def communicate(*args, **kwargs):
            nonlocal active
            try:
                return await original(*args, **kwargs)
            finally:
                active -= 1

        process.communicate = communicate
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    reports = await asyncio.gather(*(verifier.verify_candidate(candidate()) for _ in range(3)))
    assert all(report["status"] == "passed" for report in reports)
    assert maximum == 1
