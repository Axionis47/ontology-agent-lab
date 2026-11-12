"""Apply bounded changes without replacing the accepted candidate in place."""

import hashlib
import json
from collections.abc import Collection, Mapping

from pydantic import BaseModel

from oak.repair_schemas import (
    Candidate,
    Constraint,
    PatchApplication,
    PatchReceipt,
    TargetedPatch,
)

SCHEMA_COLLECTIONS = frozenset({"entities", "relations", "bindings", "operations"})


class PatchRejected(ValueError):
    pass


def canonical_digest(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def candidate_digest(candidate: Candidate) -> str:
    return canonical_digest(candidate)


def _snapshot(candidate: Candidate) -> Candidate:
    return Candidate.model_validate_json(candidate.model_dump_json())


def _constraint_preserved(before: Constraint, after: Constraint) -> bool:
    if before.id != after.id or before.entity_id != after.entity_id:
        return False
    if not set(before.requirement_ids) <= set(after.requirement_ids):
        return False
    old, new = before.predicate, after.predicate
    if old == new:
        return True
    if old.left != new.left or old.right.kind != "literal" or new.right.kind != "literal":
        return False
    if type(old.right.value) is not int or type(new.right.value) is not int:
        return False
    upper = {"lt", "le"}
    lower = {"gt", "ge"}
    if old.operator in upper and new.operator in upper:
        old_bound = old.right.value - (old.operator == "lt")
        new_bound = new.right.value - (new.operator == "lt")
        return new_bound <= old_bound
    if old.operator in lower and new.operator in lower:
        old_bound = old.right.value + (old.operator == "gt")
        new_bound = new.right.value + (new.operator == "gt")
        return new_bound >= old_bound
    return False


def _field_names(expression) -> set[str]:
    if expression.kind == "field":
        return {expression.name}
    if expression.kind in {"add", "multiply"}:
        return _field_names(expression.left) | _field_names(expression.right)
    return set()


def _check_preserved_contract(before: Candidate, after: Candidate):
    if (
        before.requirements != after.requirements
        or before.original_input_digest != after.original_input_digest
    ):
        raise PatchRejected("A repair cannot change the original requirements.")
    if before.version in {"oak.candidate.v2", "oak.candidate.v3"}:

        def coverage(candidate):
            bindings = {b.id: b.tool_id for b in candidate.operation_bindings}
            return {
                (r.requirement_id, bindings[bid])
                for r in candidate.requirement_coverage
                for bid in r.binding_ids
                if bid in bindings
            }

        if not coverage(before) <= coverage(after):
            raise PatchRejected("A repair cannot remove mandatory operation coverage.")
        # Predicates are generated implementations. Fixed validation cases decide
        # whether a replacement preserves the original source requirement.
        return
    new_constraints = {item.id: item for item in after.constraints}
    old_entities = {item.id: item for item in before.schema.entities}
    new_entities = {item.id: item for item in after.schema.entities}
    for old in before.constraints:
        new = new_constraints.get(old.id)
        if new is None or not _constraint_preserved(old, new):
            raise PatchRejected(f"Unsupported semantic contract change for constraint {old.id}.")
        fields = _field_names(old.predicate.left) | _field_names(old.predicate.right)
        old_entity, new_entity = old_entities.get(old.entity_id), new_entities.get(old.entity_id)
        if old_entity is None or new_entity is None:
            raise PatchRejected(f"Constraint {old.id} has no entity.")
        old_fields = {item.name: item for item in old_entity.properties}
        new_fields = {item.name: item for item in new_entity.properties}
        for field in fields:
            if field not in old_fields or old_fields[field] != new_fields.get(field):
                raise PatchRejected(f"Unsupported type or unit change for constraint {old.id}.")
    new_functions = {item.id: item for item in after.functions}
    for old in before.functions:
        if not old.required_constraint_ids:
            continue
        new = new_functions.get(old.id)
        if new is None or not set(old.required_constraint_ids) <= set(new.required_constraint_ids):
            raise PatchRejected(f"Function {old.id} must retain its required constraints.")


def apply_patch(
    candidate: Candidate,
    patch: TargetedPatch,
    allowed_tool_ids: Collection[str],
    requirement_ids: Collection[str],
) -> Candidate:
    """Return a checked copy. Text meaning remains outside these structural checks."""

    before = _snapshot(candidate)
    patch = TargetedPatch.model_validate_json(patch.model_dump_json())
    if patch.original_input_digest != before.original_input_digest:
        raise PatchRejected("The original input digest does not match.")
    if patch.base_digest != candidate_digest(before):
        raise PatchRejected("The patch base is stale.")
    known_requirements = {item.id for item in before.requirements.requirements}
    if not set(patch.fault.requirement_ids) <= known_requirements & set(requirement_ids):
        raise PatchRejected("The fault refers to an unknown locked requirement.")
    return apply_declaration_changes(before, patch.changes, allowed_tool_ids, requirement_ids)


def apply_declaration_changes(before, changes, allowed_tool_ids, requirement_ids):
    """Apply digest-checked edits during construction or targeted repair."""
    from oak.repair_executor import validate_candidate

    if len({(c.collection, c.id) for c in changes}) != len(changes):
        raise PatchRejected("A revision cannot change a declaration twice.")
    updated = before.model_dump(mode="json")
    for change in changes:
        owner = updated["schema"] if change.collection in SCHEMA_COLLECTIONS else updated
        records = owner[change.collection]
        matches = [i for i, record in enumerate(records) if record["id"] == change.id]
        if change.op == "add":
            if matches:
                raise PatchRejected(f"The target already exists: {change.collection}/{change.id}.")
            records.append(change.value.model_dump(mode="json"))
            continue
        if len(matches) != 1:
            raise PatchRejected(f"The target does not exist: {change.collection}/{change.id}.")
        index = matches[0]
        if canonical_digest(records[index]) != change.expected_digest:
            raise PatchRejected(f"The old-value digest does not match: {change.id}.")
        if change.op == "remove":
            records.pop(index)
        else:
            records[index] = change.value.model_dump(mode="json")

    result = Candidate.model_validate(updated)
    _check_preserved_contract(before, result)
    errors = validate_candidate(result, set(allowed_tool_ids), set(requirement_ids))
    if errors:
        raise PatchRejected(f"The repaired candidate is invalid: {errors[0]}")
    return result


def apply_targeted_patch(
    candidate: Candidate,
    patch: TargetedPatch,
    *,
    allowed_tool_ids: Collection[str],
    requirement_ids: Collection[str],
    applied_patches: Mapping[str, PatchReceipt] | None = None,
) -> PatchApplication:
    """Check a saved receipt before applying a patch again."""
    candidate = _snapshot(candidate)
    patch_hash = canonical_digest(patch)
    previous = (applied_patches or {}).get(patch.id)
    if previous is not None:
        if previous.patch_id != patch.id or previous.patch_digest != patch_hash:
            raise PatchRejected("The patch ID was used for different content.")
        if candidate_digest(candidate) != previous.result_digest:
            raise PatchRejected("The saved patch receipt does not match the candidate.")
        return PatchApplication(candidate=candidate, receipt=previous, already_applied=True)
    result = apply_patch(candidate, patch, allowed_tool_ids, requirement_ids)
    receipt = PatchReceipt(
        patch_id=patch.id,
        patch_digest=patch_hash,
        base_digest=patch.base_digest,
        result_digest=candidate_digest(result),
    )
    return PatchApplication(candidate=result, receipt=receipt)
