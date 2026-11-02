"""Executable declaration contract for the first managed agent starting shape.

Parsing proves only that a declaration fits this supported profile. It does not
register callables, verify hook behavior, mount a kernel, or authorize execution.
Contract profile IDs must still resolve in the server's tested runtime registry.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHAPE_VERSION = "oak-agent-shape/1"


class ShapeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SearchBinding(ShapeModel):
    tool_id: Literal["fixture.search_offers"]
    tool_version: Literal["0.1.0"]
    binding_key: Literal["fixture_search"]
    input_profile: Literal["fixture.search_offers.input@0.1.0"]
    output_profile: Literal["fixture.search_offers.output@0.1.0"]
    effect: Literal["read"]


class DetailBinding(ShapeModel):
    tool_id: Literal["fixture.get_offer_details"]
    tool_version: Literal["0.1.0"]
    binding_key: Literal["fixture_detail"]
    input_profile: Literal["fixture.get_offer_details.input@0.1.0"]
    output_profile: Literal["fixture.get_offer_details.output@0.1.0"]
    effect: Literal["read"]


NativeBinding = Annotated[SearchBinding | DetailBinding, Field(discriminator="tool_id")]


class FunctionDeclaration(ShapeModel):
    function_id: Literal["select_eligible_offers"]
    binding_key: Literal["c4_function_dispatch"]
    input_profile: Literal["offer-selection-input/1"]
    result_profile: Literal["offer-selection-result/1"]


class RunBounds(ShapeModel):
    max_decisions: int = Field(ge=1, le=12)
    max_seconds: int = Field(ge=1, le=900)


class AgentStartingShape(ShapeModel):
    """The concrete supported preset shape, independent of any future kernel."""

    contract_version: Literal["oak-agent-shape/1"]
    attachment: Literal["managed"]
    loop_profile: Literal["sequential_readonly/1"]
    task_profile: Literal["offer-selection-v1"]
    driver: Literal["scripted_fixture"]
    task_input_profile: Literal["TaskRequest@0.4.0"]
    # Every native-binding field is a required literal. Equal tool IDs therefore
    # produce equal objects, so uniqueItems also enforces the catalog in JSON Schema.
    native_tools: tuple[NativeBinding, NativeBinding] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    function: FunctionDeclaration
    action_kinds: tuple[Literal["native"], Literal["function"], Literal["finalize"]]
    final_result_profile: Literal["FinalSelection@0.4.0"]
    source_policy: Literal["exact_arg_case_match"]
    cross_run_memory: Literal["disabled"]
    parallel_actions: Literal[False]
    scope_requirement: Literal["project_agent_run"]
    observation_hook: Literal["c4_after_call"]
    finalization_hook: Literal["c4_finalize"]
    execution_mode: Literal["optional_functions", "guarded_requirements"]
    bounds: RunBounds

    @field_validator("parallel_actions", mode="before")
    @classmethod
    def exact_boolean(cls, value):
        # Literal[False] alone can accept 0 under Python equality semantics.
        if type(value) is not bool:
            raise ValueError("parallel_actions_requires_boolean")
        return value

    @model_validator(mode="after")
    def complete_native_catalog(self):
        ids = {tool.tool_id for tool in self.native_tools}
        if ids != {"fixture.search_offers", "fixture.get_offer_details"}:
            raise ValueError("native_catalog_must_contain_search_and_detail_once")
        return self
