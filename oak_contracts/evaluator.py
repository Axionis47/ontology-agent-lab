"""Independent literal oracle for the published synthetic development fixture only.

This module imports no selection, projection, or graph runtime helper.
It is not a general benchmark evaluator or a private-answer access boundary.
"""

from .models import ContractError, Trial


def evaluate_fixture(assignments: tuple[str, ...], trials: tuple[Trial, ...]) -> dict:
    if len(set(assignments)) != len(assignments):
        raise ContractError("duplicate_assignment")
    seen = {}
    for trial in trials:
        if trial.assignment_id not in assignments:
            raise ContractError("unexpected_trial")
        if trial.assignment_id in seen:
            raise ContractError("duplicate_trial")
        seen[trial.assignment_id] = trial
    results = []
    for assignment in assignments:
        trial = seen.get(assignment)
        if trial is None:
            results.append({"assignment_id": assignment, "outcome": "missing", "correct": False})
            continue
        correct = (
            trial.selected_offer_id == "o3"
            and trial.claim == "observed_eligible_offer"
            and "obs-detail-001" in trial.evidence_ids
        )
        results.append(
            {
                "assignment_id": assignment,
                "outcome": "correct" if correct else "incorrect",
                "correct": correct,
            }
        )
    return {
        "assigned": len(assignments),
        "correct": sum(row["correct"] for row in results),
        "outcomes": results,
        "evaluator": "literal-dev-001-v1",
    }
