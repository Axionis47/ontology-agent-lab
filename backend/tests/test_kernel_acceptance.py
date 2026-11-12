"""Check the shared eligibility gate against saved acceptance records."""

from copy import deepcopy
from uuid import UUID

import pytest

from oak.discovery_validation import digest
from oak.kernel_acceptance import inference_eligibility
from oak.kernel_execution import VERSIONS
from oak.ontology_verification import formal_schema_digest
from oak.repair_patch import candidate_digest
from oak.repair_schemas import CandidateV3
from tests.kernel_fixtures import READ_ID, WRITE_ID, candidate_data


def accepted_records(data=None):
    raw = candidate_data() if data is None else data
    raw["version"] = "oak.candidate.v3"
    for binding in raw["operation_bindings"]:
        binding["source_access"] = {
            "kind": "data" if binding["tool_id"] == READ_ID else "action",
            "mapping_ids": [m["id"] for m in raw["mappings"] if m["tool_id"] == binding["tool_id"]],
            "support": {"source": "input", "id": "surface", "path": "/tools/0/description"},
        }
    candidate = CandidateV3.model_validate(raw)
    row = {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "payload": candidate.model_dump(mode="json"),
        "input_digest": candidate.original_input_digest,
        "digest": candidate_digest(candidate),
        "status": "accepted",
        "decision": {"validation": {"versions": deepcopy(VERSIONS)}},
    }
    events = []
    for index, kind in enumerate(("formal", "coverage", "counterexamples"), start=2):
        event_id = UUID(f"00000000-0000-0000-0000-{index:012d}")
        report = {"status": "passed"}
        if kind == "formal":
            report["schema_digest"] = formal_schema_digest(candidate)
            report["versions"] = {"encoder": VERSIONS["encoder"]}
        events.append(
            {
                "id": event_id,
                "data": {
                    "candidate_id": str(row["id"]),
                    "candidate_digest": row["digest"],
                    "validation_kind": kind,
                    "report": report,
                },
            }
        )
        row["decision"]["validation"][kind + "_event_id"] = str(event_id)
    return row, events


def eligibility(row, events=(), *, input_digest=None, grants=None):
    return inference_eligibility(
        row,
        input_digest or "a" * 64,
        [READ_ID, WRITE_ID] if grants is None else grants,
        events,
    )


def test_accepted_kernel_is_ready_with_matching_reports_and_grants():
    row, events = accepted_records()
    before = deepcopy((row, events))
    result = eligibility(row, events)
    assert result["inference_ready"]
    assert result["inference_tool_ids"] == sorted([READ_ID, WRITE_ID])
    assert (row, events) == before


@pytest.mark.parametrize("status", ["provisional", "rejected", "failed"])
def test_unaccepted_status_cannot_enable_inference(status):
    row, events = accepted_records()
    row["status"] = status
    assert not eligibility(row, events)["inference_ready"]


@pytest.mark.parametrize("version", ["oak.candidate.v1", "oak.candidate.v2"])
def test_missing_and_legacy_candidates_require_reconstruction(version):
    assert not eligibility(None)["inference_ready"]
    row, events = accepted_records()
    row["payload"]["version"] = version
    assert not eligibility(row, events)["inference_ready"]


def test_stale_task_digest_or_removed_grant_disables_inference():
    row, events = accepted_records()
    assert not eligibility(row, events, input_digest="b" * 64)["inference_ready"]
    assert not eligibility(row, events, grants=[READ_ID])["inference_ready"]


def test_candidate_must_preserve_the_same_original_input_digest():
    data = candidate_data()
    data["original_input_digest"] = "b" * 64
    row, events = accepted_records(data)
    row["input_digest"] = "a" * 64
    assert not eligibility(row, events)["inference_ready"]


@pytest.mark.parametrize("version", list(VERSIONS))
def test_stale_runtime_versions_require_revalidation(version):
    row, events = accepted_records()
    row["decision"]["validation"]["versions"][version] = "old"
    result = eligibility(row, events)
    assert not result["inference_ready"]
    assert "versions changed" in result["inference_message"]


def test_missing_version_manifest_requires_revalidation():
    row, events = accepted_records()
    row["decision"]["validation"].pop("versions")
    assert not eligibility(row, events)["inference_ready"]


def test_changed_candidate_declarations_cannot_reuse_an_accepted_digest():
    row, events = accepted_records()
    row["payload"]["request_fields"][0]["description"] = "Changed meaning."
    assert not eligibility(row, events)["inference_ready"]


@pytest.mark.parametrize("kind", ["formal", "coverage", "counterexamples"])
@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "failed",
        "infrastructure_error",
        "wrong_candidate",
        "wrong_digest",
        "wrong_kind",
        "malformed",
    ],
)
def test_missing_or_tampered_report_disables_inference(kind, defect):
    row, events = accepted_records()
    event = next(event for event in events if event["data"]["validation_kind"] == kind)
    if defect == "missing":
        events.remove(event)
    elif defect in {"failed", "infrastructure_error"}:
        event["data"]["report"]["status"] = defect
    elif defect == "wrong_candidate":
        event["data"]["candidate_id"] = "another-candidate"
    elif defect == "wrong_digest":
        event["data"]["candidate_digest"] = "b" * 64
    elif defect == "wrong_kind":
        event["data"]["validation_kind"] = "another-validation"
    else:
        event["data"]["report"] = None
    result = eligibility(row, events)
    assert not result["inference_ready"]
    assert result["inference_tool_ids"] == []


def test_one_formal_report_cannot_replace_the_other_acceptance_gates():
    row, events = accepted_records()
    validation = row["decision"]["validation"]
    validation["coverage_event_id"] = validation["formal_event_id"]
    validation["counterexamples_event_id"] = validation["formal_event_id"]
    assert not eligibility(row, events)["inference_ready"]


def test_formal_report_must_match_the_exact_schema_projection():
    row, events = accepted_records()
    events[0]["data"]["report"]["schema_digest"] = "b" * 64
    assert not eligibility(row, events)["inference_ready"]


@pytest.mark.parametrize("versions", [None, {}, {"encoder": "old"}])
def test_formal_report_must_match_the_current_encoder(versions):
    row, events = accepted_records()
    events[0]["data"]["report"]["versions"] = versions
    assert not eligibility(row, events)["inference_ready"]


@pytest.mark.parametrize("location", ["payload", "decision", "validation", "event_data"])
def test_malformed_saved_records_fail_closed(location):
    row, events = accepted_records()
    if location in {"payload", "decision"}:
        row[location] = None
    elif location == "validation":
        row["decision"]["validation"] = []
    else:
        events[0]["data"] = None
    assert not eligibility(row, events)["inference_ready"]


def test_unicode_candidate_uses_the_persisted_canonical_digest():
    data = candidate_data()
    data["request_fields"][0]["description"] = "Requested guests for Montréal, 日本語."
    row, events = accepted_records(data)
    assert row["digest"] != digest(row["payload"])
    assert eligibility(row, events)["inference_ready"]
    row["digest"] = digest(row["payload"])
    assert not eligibility(row, events)["inference_ready"]
