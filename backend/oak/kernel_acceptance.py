"""Use one acceptance contract for inspection, launch, and pinned inference."""

from oak.acquisition import validate_access
from oak.kernel_execution import VERSIONS
from oak.ontology_verification import formal_schema_digest
from oak.repair_executor import validate_candidate
from oak.repair_patch import candidate_digest
from oak.repair_schemas import Candidate


def inference_eligibility(row, input_digest, granted_tool_ids, validation_events=()):
    def no(message):
        return {"inference_ready": False, "inference_message": message, "inference_tool_ids": []}

    if not row:
        return no("Train an accepted kernel before inference.")
    raw = row.get("payload", {})
    if not isinstance(raw, dict) or raw.get("version") != "oak.candidate.v3":
        return no("Train a version 3 kernel from the saved cases before inference.")
    if row.get("status") != "accepted" or row.get("input_digest") != input_digest:
        return no("The accepted kernel does not match the current task and grants.")
    try:
        candidate = Candidate.model_validate(raw)
        validate_access(candidate, required=True)
        if candidate.original_input_digest != input_digest:
            return no("The kernel does not preserve the original task and grants.")
        if candidate_digest(candidate) != row.get("digest"):
            return no("The accepted kernel digest does not match its declarations.")
        errors = validate_candidate(
            candidate, set(granted_tool_ids), {r.id for r in candidate.requirements.requirements}
        )
        if errors:
            return no("The accepted kernel is incompatible: " + errors[0])
        decision = row.get("decision")
        validation = decision.get("validation", {}) if isinstance(decision, dict) else {}
        if not isinstance(validation, dict):
            return no("The kernel acceptance record is invalid.")
        if validation.get("versions") != VERSIONS:
            return no("Runtime versions changed. Validate and accept the kernel before inference.")
        by_id = {str(e["id"]): e for e in validation_events}
        for kind in ("formal", "coverage", "counterexamples"):
            event = by_id.get(validation.get(kind + "_event_id"))
            data = event.get("data", {}) if event else {}
            if not isinstance(data, dict):
                return no("The kernel acceptance report is invalid.")
            report = data.get("report")
            if (
                not event
                or data.get("candidate_id") != str(row.get("id"))
                or data.get("validation_kind") != kind
                or data.get("candidate_digest") != row["digest"]
                or not isinstance(report, dict)
                or report.get("status") != "passed"
            ):
                return no("An acceptance report is unavailable or does not match the kernel.")
            if kind == "formal" and report.get("schema_digest") != formal_schema_digest(candidate):
                return no("The formal report does not match the schema.")
            if kind == "formal":
                versions = report.get("versions")
                if not isinstance(versions, dict) or versions.get("encoder") != VERSIONS["encoder"]:
                    return no("The formal encoder changed. Revalidate the kernel before inference.")
        enabled = sorted(b.tool_id for b in candidate.operation_bindings)
        if not set(enabled) <= set(granted_tool_ids):
            return no("An enabled operation is no longer granted.")
        return {
            "inference_ready": True,
            "inference_message": "Accepted kernel is ready.",
            "inference_tool_ids": enabled,
        }
    except (ValueError, TypeError, KeyError):
        return no("The accepted kernel requires reconstruction or revalidation.")
