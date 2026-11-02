"""Load the existing, published fixture without changing its historical files."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .models import Package, Scope, SelectionRequest, ToolObservation

ROOT = Path(__file__).resolve().parents[1]


def implementation_manifest(kind: str) -> dict:
    return {
        "kind": kind,
        "implementation": "fixed-selection-harness-v1",
        "selection_sha256": hashlib.sha256(
            (ROOT / "oak_contracts/selection.py").read_bytes()
        ).hexdigest(),
    }


def package_fixture(store, scope: Scope, mode="optional_functions") -> tuple[str, Package]:
    refs = {
        kind: store.put_artifact("owner", scope.project_id, kind, implementation_manifest(kind))
        for kind in ("schema", "functions", "extractor", "operators")
    }
    package = Package(**refs, functions_schema_hash=refs["schema"].sha256, execution_mode=mode)
    return store.save_package("owner", scope, package), package


def input_fixture():
    directory = ROOT / "docs/oak/examples"
    case = json.loads((directory / "development-cases.jsonl").read_text().splitlines()[0])
    context = dict(case["context"])
    context["budget_minor"] = context.pop("budget_total") * 100
    request = SelectionRequest.model_validate_json(
        json.dumps({"case_id": case["case_id"], **context})
    )
    observations = tuple(
        ToolObservation.model_validate_json(line)
        for line in (directory / "observations.jsonl").read_text().splitlines()
    )
    return request, observations, datetime(2027, 3, 1, 10, 1, tzinfo=UTC)
