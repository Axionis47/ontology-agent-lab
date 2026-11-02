"""Run the offline contract suite and preserve machine-readable receipts."""

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oak_contracts.evaluator import evaluate_fixture
from oak_contracts.fixture import input_fixture, package_fixture
from oak_contracts.models import (
    REQUIRED_GATES,
    RepairProposal,
    Scope,
    Trial,
    digest,
    repair_invalidation,
)
from oak_contracts.store import SQLiteHarness


def demo(output: Path) -> dict:
    """A scripted observation-enrichment loop, not schema generation or repair."""
    store = SQLiteHarness(output / "demo.sqlite")
    try:
        scope = Scope(project_id="synthetic-project", agent_id="offer-selection-v1")
        store.bootstrap(scope.project_id, "owner", "recorded-verifier")
        store.create_agent("owner", scope)
        package_hash, package = package_fixture(store, scope)
        inputs = (digest("published-dev-001-fixture"),)
        report = store.issue_report(
            "recorded-verifier",
            scope,
            package_hash,
            dict.fromkeys(REQUIRED_GATES, "passed"),
            inputs,
        )
        store.activate("owner", scope, package_hash, report, 0, inputs)
        request, observations, as_of = input_fixture()
        store.start_run("owner", scope, "scripted-development-1", 1000.0, 4, "development")
        store.create_context("owner", scope, "query-1", package_hash, request, as_of)
        results = []
        for index, observation in enumerate(observations):
            operation = f"native-{index}"
            decision = store.reserve_call(
                "owner",
                scope,
                "scripted-development-1",
                operation,
                {"tool_id": observation.tool_id, "arguments": observation.arguments},
                900.0 + index,
            )
            if decision != "dispatch":
                raise RuntimeError("unexpected_replay_admission")
            receipt = store.ingest("owner", scope, "query-1", observation, index)
            store.complete_call("owner", scope, "scripted-development-1", operation)
            function_operation = f"function-{index}"
            store.reserve_call(
                "owner",
                scope,
                "scripted-development-1",
                function_operation,
                {"function": "select_eligible_offers", "revision": receipt.revision},
                900.0 + index,
            )
            result = store.select(
                "owner",
                scope,
                "query-1",
                receipt.revision,
                (observation.observation_id,),
                package_hash,
            )
            store.complete_call("owner", scope, "scripted-development-1", function_operation)
            results.append(result.model_dump(mode="json"))
        eligible = [
            offer["offer_id"] for offer in results[-1]["offers"] if offer["status"] == "eligible"
        ]
        trial = Trial(
            assignment_id="scripted-dev-001",
            selected_offer_id=eligible[0],
            claim="observed_eligible_offer",
            evidence_ids=("obs-search-001", "obs-detail-001"),
        )
        proposal = RepairProposal(
            target_hash=package.schema_ref.sha256,
            kind="schema",
            changed_semantic_ids=("Offer.minimum_stay",),
            evidence_ids=("synthetic-diagnostic",),
        )
        return {
            "classification": "offline_scripted_contract_fixture",
            "package_hash": package_hash,
            "verification_receipt_kind": "recorded_test_substitute",
            "model_calls": 0,
            "external_provider_calls": 0,
            "scripted_agent_visible_calls": 4,
            "native_replay_operations": 2,
            "function_operations": 2,
            "graph_commit_operations": 2,
            "states": results,
            "assessment": evaluate_fixture(("scripted-dev-001",), (trial,)),
            "repair_routing_only": repair_invalidation(
                proposal, package.schema_ref.sha256, "development"
            ),
            "schema_repair_executed": False,
            "note": "Observed improvement comes from new detail evidence. Schema and functions are unchanged.",
        }
    finally:
        store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory for receipts; must not exist")
    arguments = parser.parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = arguments.output or ROOT / ".runtime/oak-contracts" / run_id
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    junit = output / "tests.xml"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/oak_contracts", "-q", f"--junitxml={junit}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "pytest-output.txt").write_text(completed.stdout + completed.stderr)
    test_cases = []
    if junit.exists():
        for case in ET.parse(junit).iter("testcase"):
            status = (
                "failed"
                if case.find("failure") is not None or case.find("error") is not None
                else "skipped"
                if case.find("skipped") is not None
                else "passed"
            )
            test_cases.append(
                {
                    "name": case.attrib["name"],
                    "suite": case.attrib.get("classname", "unknown"),
                    "status": status,
                    "seconds": float(case.attrib.get("time", "0")),
                }
            )
    sources = (
        list((ROOT / "oak_contracts").glob("*.py"))
        + list((ROOT / "tests/oak_contracts").glob("*.py"))
        + list((ROOT / "docs/oak/implementation/examples").glob("agent-starting-shape*.json"))
        + [
            ROOT / "docs/oak/examples" / name
            for name in ("development-cases.jsonl", "observations.jsonl")
        ]
        + [Path(__file__).resolve()]
    )
    receipt = {
        "contract_version": "oak-contract-harness/1",
        "run_id": run_id,
        "python": sys.version,
        "test_exit_code": completed.returncode,
        "assigned": len(test_cases),
        "passed": sum(case["status"] == "passed" for case in test_cases),
        "cases": test_cases,
        "source_hashes": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(sources)
        },
        "scope": "offline SQLite substitute and starting-shape declaration; no production runtime or agent benefit claim",
    }
    if completed.returncode == 0:
        (output / "demo.json").write_text(json.dumps(demo(output), indent=2) + "\n")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": receipt["passed"],
                "assigned": receipt["assigned"],
                "exit_code": completed.returncode,
                "receipt": str(output / "receipt.json"),
                "demo": str(output / "demo.json") if completed.returncode == 0 else None,
            },
            indent=2,
        )
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
