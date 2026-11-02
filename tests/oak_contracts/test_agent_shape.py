"""Declaration compatibility checks, not runtime capability-probe evidence."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oak_contracts.agent_shape import AgentStartingShape

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs/oak/implementation/examples"


@pytest.fixture
def starting_shape():
    return json.loads((EXAMPLES / "agent-starting-shape.json").read_text())


def parse(value):
    return AgentStartingShape.model_validate_json(json.dumps(value))


def test_starter_declaration_is_complete_before_any_kernel_exists(starting_shape):
    shape = parse(starting_shape)
    assert shape.loop_profile == "sequential_readonly/1"
    assert shape.task_profile == "offer-selection-v1"
    assert {tool.binding_key for tool in shape.native_tools} == {"fixture_search", "fixture_detail"}
    serialized = shape.model_dump_json()
    for unavailable in ("bundle_ref", "package_ref", "ready", "probe_receipt"):
        assert unavailable not in serialized
    assert parse(json.loads(serialized)) == shape


def test_generated_schema_matches_the_model():
    saved = json.loads((EXAMPLES / "agent-starting-shape.schema.json").read_text())
    assert saved == AgentStartingShape.model_json_schema()
    assert saved["properties"]["native_tools"]["uniqueItems"] is True


@pytest.mark.parametrize("replacement", ["external", "uploaded_python"])
def test_external_attachment_is_not_silently_accepted(starting_shape, replacement):
    starting_shape["attachment"] = replacement
    with pytest.raises(ValidationError):
        parse(starting_shape)


def test_declared_capabilities_cannot_claim_ready_admission(starting_shape):
    starting_shape["capabilities"] = {"native_callbacks": True, "status": "ready"}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        parse(starting_shape)


@pytest.mark.parametrize("duplicate_index", [0, 1])
def test_duplicate_tool_cannot_hide_the_missing_callable(starting_shape, duplicate_index):
    duplicate = copy.deepcopy(starting_shape["native_tools"][duplicate_index])
    starting_shape["native_tools"] = [duplicate, duplicate]
    with pytest.raises(ValidationError, match="native_catalog_must_contain"):
        parse(starting_shape)


def test_tool_identity_cannot_bind_the_other_implementation(starting_shape):
    starting_shape["native_tools"][0]["binding_key"] = "fixture_detail"
    with pytest.raises(ValidationError):
        parse(starting_shape)


@pytest.mark.parametrize("catalog_change", ["missing", "additional", "write"])
def test_native_catalog_does_not_grow_shrink_or_gain_side_effects(starting_shape, catalog_change):
    tools = starting_shape["native_tools"]
    if catalog_change == "missing":
        tools.pop()
    elif catalog_change == "additional":
        tools.append(copy.deepcopy(tools[0]))
    else:
        tools[0]["effect"] = "write"
    with pytest.raises(ValidationError):
        parse(starting_shape)


def test_missing_result_contract_and_changed_result_profile_are_rejected(starting_shape):
    missing = copy.deepcopy(starting_shape)
    del missing["native_tools"][0]["output_profile"]
    with pytest.raises(ValidationError):
        parse(missing)
    starting_shape["native_tools"][0]["output_profile"] = "fixture.get_offer_details.output@0.1.0"
    with pytest.raises(ValidationError):
        parse(starting_shape)


@pytest.mark.parametrize("field", ["endpoint", "import_path", "credential", "executable_body"])
def test_binding_declaration_does_not_accept_executable_or_secret_fields(starting_shape, field):
    starting_shape["native_tools"][0][field] = "untrusted-value"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        parse(starting_shape)


def test_shape_does_not_require_or_accept_a_future_kernel(starting_shape):
    starting_shape["function"]["bundle_ref"] = {"artifact_id": "future-bundle"}
    with pytest.raises(ValidationError, match="extra_forbidden"):
        parse(starting_shape)


def test_unobserved_action_cannot_extend_the_action_vocabulary(starting_shape):
    starting_shape["action_kinds"].append("delegate")
    with pytest.raises(ValidationError):
        parse(starting_shape)


@pytest.mark.parametrize("value", [True, "12", 0, 13])
def test_decision_ceiling_rejects_coercion_or_expansion(starting_shape, value):
    starting_shape["bounds"]["max_decisions"] = value
    with pytest.raises(ValidationError):
        parse(starting_shape)


@pytest.mark.parametrize("value", [0, True])
def test_sequential_profile_rejects_false_coercion_and_parallel_dispatch(starting_shape, value):
    starting_shape["parallel_actions"] = value
    with pytest.raises(ValidationError):
        parse(starting_shape)


def test_mode_and_tighter_bounds_do_not_change_the_supported_loop(starting_shape):
    starting_shape["execution_mode"] = "guarded_requirements"
    starting_shape["bounds"] = {"max_decisions": 5, "max_seconds": 60}
    shape = parse(starting_shape)
    assert shape.execution_mode == "guarded_requirements"
    assert shape.bounds.max_decisions == 5
    with pytest.raises(ValidationError, match="frozen_instance"):
        shape.bounds.max_decisions = 12


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("driver", "fixed_model"),
        ("source_policy", "infer_missing_values"),
        ("cross_run_memory", "shared"),
        ("observation_hook", "skip_ingestion"),
        ("finalization_hook", "return_directly"),
    ],
)
def test_unimplemented_execution_paths_fail_closed(starting_shape, field, value):
    starting_shape[field] = value
    with pytest.raises(ValidationError):
        parse(starting_shape)
