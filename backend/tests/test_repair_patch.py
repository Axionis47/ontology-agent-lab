from copy import deepcopy

import pytest
from pydantic import ValidationError

from oak.repair_patch import (
    PatchRejected,
    apply_patch,
    apply_targeted_patch,
    candidate_digest,
    canonical_digest,
)
from oak.repair_schemas import Candidate, TargetedPatch

GRANTS = {"catalog"}
REQUIREMENTS = {"budget"}


def candidate_data():
    return {
        "original_input_digest": "a" * 64,
        "requirements": {
            "requirements": [
                {
                    "id": "budget",
                    "statement": "Select records with an amount from zero through 100.",
                    "evidence": [{"source": "input", "id": "surface", "path": "/boundaries"}],
                    "tool_ids": ["catalog"],
                }
            ]
        },
        "schema": {
            "entities": [
                {
                    "id": "item",
                    "name": "Item",
                    "properties": [
                        {"name": "id", "type": "string"},
                        {"name": "amount", "type": "integer", "unit": "USD"},
                        {"name": "label", "type": "string"},
                    ],
                    "identity_keys": ["id"],
                    "requirement_ids": ["budget"],
                }
            ],
        },
        "mappings": [
            {
                "id": "items",
                "entity_id": "item",
                "tool_id": "catalog",
                "collection_path": "/items",
                "fields": [
                    {"property": "id", "path": "/id"},
                    {"property": "amount", "path": "/amount"},
                    {"property": "label", "path": "/label"},
                ],
            }
        ],
        "constraints": [
            {
                "id": "maximum",
                "entity_id": "item",
                "requirement_ids": ["budget"],
                "predicate": {
                    "operator": "le",
                    "left": {"kind": "field", "name": "amount"},
                    "right": {"kind": "literal", "value": 100},
                },
            }
        ],
        "functions": [
            {
                "id": "eligible",
                "entity_id": "item",
                "required_constraint_ids": ["maximum"],
                "steps": [
                    {"op": "lookup", "id": "source", "entity_id": "item"},
                    {
                        "op": "filter",
                        "id": "bounded",
                        "input": "source",
                        "constraint_ids": ["maximum"],
                    },
                    {
                        "op": "project",
                        "id": "result",
                        "input": "bounded",
                        "fields": [
                            {"name": "id", "expression": {"kind": "field", "name": "id"}},
                            {"name": "amount", "expression": {"kind": "field", "name": "amount"}},
                            {"name": "label", "expression": {"kind": "field", "name": "label"}},
                        ],
                    },
                ],
                "return_step": "result",
                "output": {
                    "kind": "rows",
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "amount", "type": "integer"},
                        {"name": "label", "type": "string"},
                    ],
                },
            }
        ],
    }


def make_patch(candidate, changes, **overrides):
    return TargetedPatch.model_validate(
        {
            "id": "fix-label",
            "base_digest": candidate_digest(candidate),
            "original_input_digest": candidate.original_input_digest,
            "fault": {
                "id": "wrong-field",
                "sample_id": "case-1",
                "requirement_ids": ["budget"],
                "reason": "The declared field does not match the observed record.",
            },
            "evidence_refs": [{"source": "artifact", "id": "case-1-result", "path": ""}],
            "changes": changes,
            **overrides,
        }
    )


def replace(collection, before, after):
    return {
        "collection": collection,
        "op": "replace",
        "id": before.id,
        "expected_digest": canonical_digest(before),
        "value": after,
    }


def coherent_label_fix(candidate):
    entity = candidate.schema.entities[0].model_dump(mode="json")
    entity["properties"][2]["name"] = "title"
    mapping = candidate.mappings[0].model_dump(mode="json")
    mapping["fields"][2] = {"property": "title", "path": "/title"}
    function = candidate.functions[0].model_dump(mode="json")
    function["steps"][2]["fields"][2] = {
        "name": "title",
        "expression": {"kind": "field", "name": "title"},
    }
    function["output"]["fields"][2]["name"] = "title"
    return [
        replace("entities", candidate.schema.entities[0], entity),
        replace("mappings", candidate.mappings[0], mapping),
        replace("functions", candidate.functions[0], function),
    ]


def test_coherent_patch_is_atomic_and_preserves_untouched_records():
    candidate = Candidate.model_validate(candidate_data())
    before = candidate.model_dump(mode="json")
    changes = coherent_label_fix(candidate)
    with pytest.raises(PatchRejected, match="invalid"):
        apply_patch(candidate, make_patch(candidate, changes[:1]), GRANTS, REQUIREMENTS)
    assert candidate.model_dump(mode="json") == before

    result = apply_patch(candidate, make_patch(candidate, changes), GRANTS, REQUIREMENTS)
    assert result.schema.entities[0].properties[2].name == "title"
    assert result.mappings[0].fields[2].path == "/title"
    assert result.functions[0].output.fields[2].name == "title"
    assert result.constraints == candidate.constraints
    assert result.requirements == candidate.requirements
    assert candidate.model_dump(mode="json") == before
    result.schema.entities[0].name = "Local change"
    assert candidate.schema.entities[0].name == "Item"


def test_repair_can_restore_a_missing_required_filter():
    data = candidate_data()
    data["functions"][0]["steps"].pop(1)
    data["functions"][0]["steps"][1]["input"] = "source"
    broken = Candidate.model_validate(data)
    fixed = candidate_data()["functions"][0]
    patch = make_patch(broken, [replace("functions", broken.functions[0], fixed)])
    repaired = apply_patch(broken, patch, GRANTS, REQUIREMENTS)
    assert repaired.functions[0].steps[1].constraint_ids == ("maximum",)


@pytest.mark.parametrize(
    "bound,operator,accepted",
    [
        (100, "le", True),
        (90, "le", True),
        (101, "lt", True),
        (101, "le", False),
        (102, "lt", False),
        (100, "ge", False),
    ],
)
def test_constraint_replacement_only_accepts_supported_integer_strengthening(
    bound, operator, accepted
):
    candidate = Candidate.model_validate(candidate_data())
    constraint = candidate.constraints[0].model_dump(mode="json")
    constraint["predicate"]["right"]["value"] = bound
    constraint["predicate"]["operator"] = operator
    patch = make_patch(candidate, [replace("constraints", candidate.constraints[0], constraint)])
    if accepted:
        assert (
            apply_patch(candidate, patch, GRANTS, REQUIREMENTS).constraints[0].predicate.operator
            == operator
        )
    else:
        with pytest.raises(PatchRejected, match="Unsupported semantic contract change"):
            apply_patch(candidate, patch, GRANTS, REQUIREMENTS)


def test_add_an_omitted_constraint_and_its_consumer_together():
    candidate = Candidate.model_validate(candidate_data())
    minimum = {
        "id": "minimum",
        "entity_id": "item",
        "requirement_ids": ["budget"],
        "predicate": {
            "operator": "ge",
            "left": {"kind": "field", "name": "amount"},
            "right": {"kind": "literal", "value": 0},
        },
    }
    function = candidate.functions[0].model_dump(mode="json")
    function["required_constraint_ids"].append("minimum")
    function["steps"][1]["constraint_ids"].append("minimum")
    patch = make_patch(
        candidate,
        [
            {"collection": "constraints", "op": "add", "id": "minimum", "value": minimum},
            replace("functions", candidate.functions[0], function),
        ],
    )
    result = apply_patch(candidate, patch, GRANTS, REQUIREMENTS)
    assert {constraint.id for constraint in result.constraints} == {"minimum", "maximum"}
    assert set(result.functions[0].required_constraint_ids) == {"minimum", "maximum"}


@pytest.mark.parametrize("target", ["constraint", "required_reference", "unit"])
def test_constraint_contract_cannot_be_removed_or_reinterpreted(target):
    candidate = Candidate.model_validate(candidate_data())
    if target == "constraint":
        changes = [
            {
                "collection": "constraints",
                "op": "remove",
                "id": "maximum",
                "expected_digest": canonical_digest(candidate.constraints[0]),
            }
        ]
    elif target == "required_reference":
        function = candidate.functions[0].model_dump(mode="json")
        function["required_constraint_ids"] = []
        changes = [replace("functions", candidate.functions[0], function)]
    else:
        entity = candidate.schema.entities[0].model_dump(mode="json")
        entity["properties"][1]["unit"] = "cents"
        changes = [replace("entities", candidate.schema.entities[0], entity)]
    with pytest.raises(PatchRejected):
        apply_patch(candidate, make_patch(candidate, changes), GRANTS, REQUIREMENTS)


@pytest.mark.parametrize("attack", ["base", "old_value", "locked_input", "grant", "requirement"])
def test_patch_preconditions_and_authority(attack):
    candidate = Candidate.model_validate(candidate_data())
    patch = make_patch(candidate, coherent_label_fix(candidate)).model_dump(mode="json")
    if attack == "base":
        patch["base_digest"] = "b" * 64
    elif attack == "old_value":
        patch["changes"][0]["expected_digest"] = "b" * 64
    elif attack == "locked_input":
        patch["original_input_digest"] = "b" * 64
    elif attack == "grant":
        patch["changes"][1]["value"]["tool_id"] = "ungranted"
    else:
        patch["fault"]["requirement_ids"] = ["new-policy"]
    with pytest.raises(PatchRejected):
        apply_patch(candidate, TargetedPatch.model_validate(patch), GRANTS, REQUIREMENTS)


def test_duplicate_patch_is_idempotent_and_changed_content_is_rejected():
    candidate = Candidate.model_validate(candidate_data())
    patch = make_patch(candidate, coherent_label_fix(candidate))
    first = apply_targeted_patch(
        candidate, patch, allowed_tool_ids=GRANTS, requirement_ids=REQUIREMENTS
    )
    repeated = apply_targeted_patch(
        first.candidate,
        patch,
        allowed_tool_ids=GRANTS,
        requirement_ids=REQUIREMENTS,
        applied_patches={patch.id: first.receipt},
    )
    assert repeated.already_applied
    assert candidate_digest(repeated.candidate) == candidate_digest(first.candidate)
    changed = patch.model_dump(mode="json")
    changed["fault"]["reason"] = "Different request under the same patch ID."
    with pytest.raises(PatchRejected, match="different content"):
        apply_targeted_patch(
            first.candidate,
            TargetedPatch.model_validate(changed),
            allowed_tool_ids=GRANTS,
            requirement_ids=REQUIREMENTS,
            applied_patches={patch.id: first.receipt},
        )


def test_finite_schema_rejects_code_and_duplicate_targets():
    data = candidate_data()
    data["functions"][0]["steps"][0] = {"op": "python", "id": "source", "code": "return []"}
    with pytest.raises(ValidationError):
        Candidate.model_validate(data)
    candidate = Candidate.model_validate(candidate_data())
    changes = coherent_label_fix(candidate)
    with pytest.raises(ValidationError, match="same target"):
        make_patch(candidate, [changes[0], changes[0]])
    patch = make_patch(candidate, changes).model_dump(mode="json")
    patch["changes"][0]["collection"] = "requirements"
    with pytest.raises(ValidationError):
        TargetedPatch.model_validate(patch)


def test_candidate_clones_discovery_models():
    first = Candidate.model_validate(candidate_data())
    second = Candidate(
        original_input_digest=first.original_input_digest,
        requirements=first.requirements,
        schema=first.schema,
    )
    before = deepcopy(second.model_dump(mode="json"))
    first.requirements.requirements[0].statement = "Changed outside the candidate."
    first.schema.entities[0].name = "Changed entity"
    assert second.model_dump(mode="json") == before
