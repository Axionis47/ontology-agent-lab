"""Local declaration and payload checks, with no runtime dispatch or admission proof."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
Profile = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_./@-]{0,127}$")]
Version = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]


class Declaration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Bounds(Declaration):
    max_decisions: int = Field(gt=0)
    max_seconds: int = Field(gt=0)


class ToolRef(Declaration):
    tool_id: Identifier
    tool_version: Version


class NativeToolContract(ToolRef):
    binding_key: Identifier
    input_profile: Profile
    output_profile: Profile
    effect: Literal["read"]


class FunctionContract(Declaration):
    function_id: Identifier
    function_version: Version
    binding_key: Identifier
    input_profile: Profile
    result_profile: Profile
    effect: Literal["read"]


class AgentLoopDefinition(Declaration):
    definition_id: Identifier
    version: Version
    loop_profile: Literal["sequential_readonly/1"]
    attachment: Literal["managed"]
    driver: Literal["scripted_fixture"]
    native_tools: tuple[NativeToolContract, ...] = Field(min_length=1)
    bounds: Bounds
    observation_hook: Literal["c4_after_call"]
    finalization_hook: Literal["c4_finalize"]
    parallel_actions: Literal[False]
    cross_run_memory: Literal["disabled"]
    scope_requirement: Literal["project_agent_run"]
    action_kinds: tuple[Literal["native"], Literal["function"], Literal["finalize"]]

    @field_validator("parallel_actions", mode="before")
    @classmethod
    def exact_false(cls, value):
        if value is not False:
            raise ValueError("parallel_actions_requires_false_boolean")
        return value

    @model_validator(mode="after")
    def unique_tools(self):
        if len({t.tool_id for t in self.native_tools}) != len(self.native_tools):
            raise ValueError("duplicate_tool_id")
        if len({t.binding_key for t in self.native_tools}) != len(self.native_tools):
            raise ValueError("duplicate_binding_key")
        return self


class TaskDefinition(Declaration):
    task_id: Identifier
    version: Version
    input_profile: Profile
    result_profile: Profile
    required_native_tools: tuple[ToolRef, ...]
    functions: tuple[FunctionContract, ...]
    mapping_id: Identifier
    evaluator_id: Identifier
    suite_id: Identifier

    @model_validator(mode="after")
    def unique_requirements(self):
        if len({t.tool_id for t in self.required_native_tools}) != len(self.required_native_tools):
            raise ValueError("duplicate_required_tool")
        if len({f.function_id for f in self.functions}) != len(self.functions):
            raise ValueError("duplicate_function_id")
        return self


class NativeAction(ToolRef):
    kind: Literal["native"]
    arguments: dict[str, Any]


class FunctionAction(Declaration):
    kind: Literal["function"]
    function_id: Identifier
    function_version: Version
    arguments: dict[str, Any]


class FinalAction(Declaration):
    kind: Literal["finalize"]
    task_id: Identifier
    task_version: Version
    result: dict[str, Any]


Action = Annotated[NativeAction | FunctionAction | FinalAction, Field(discriminator="kind")]
ACTION_ADAPTER = TypeAdapter(Action)


@dataclass(frozen=True, init=False)
class TaskBinding:
    """Resolve registered declarations and validate payloads, never invoke a binding.

    Required native tools form the exact permitted subset, not a mandatory call
    sequence. Registration here is local metadata, not a callable capability probe.
    Resource IDs are names in a server-owned registry, not artifact hashes or paths.
    """

    loop: AgentLoopDefinition
    task: TaskDefinition
    _adapters: Mapping[str, TypeAdapter]
    _tools: Mapping[tuple[str, str], NativeToolContract]
    _functions: Mapping[tuple[str, str], FunctionContract]

    def __init__(
        self,
        loop: AgentLoopDefinition,
        task: TaskDefinition,
        *,
        models: Mapping[str, type[BaseModel]],
        native_registry: Mapping[tuple[str, str], NativeToolContract],
        function_registry: Mapping[tuple[str, str], FunctionContract],
        resources: Mapping[str, set[str]],
    ):
        object.__setattr__(self, "loop", loop)
        object.__setattr__(self, "task", task)
        catalog = {(t.tool_id, t.tool_version): t for t in loop.native_tools}
        for key, tool in catalog.items():
            if native_registry.get(key) != tool:
                raise ValueError("native_contract_unregistered_or_incompatible")
        required = {(t.tool_id, t.tool_version) for t in task.required_native_tools}
        if not required <= catalog.keys():
            raise ValueError("required_native_tool_unavailable")
        functions = {(f.function_id, f.function_version): f for f in task.functions}
        for key, function in functions.items():
            if function_registry.get(key) != function:
                raise ValueError("function_contract_unregistered_or_incompatible")
        for kind in ("mapping", "evaluator", "suite"):
            if getattr(task, f"{kind}_id") not in resources.get(kind, set()):
                raise ValueError(f"{kind}_unregistered")
        profiles = {task.input_profile, task.result_profile}
        for tool in catalog.values():
            profiles.update((tool.input_profile, tool.output_profile))
        for function in functions.values():
            profiles.update((function.input_profile, function.result_profile))
        adapters = {}
        for profile in profiles:
            model = models.get(profile)
            if model is None:
                raise ValueError(f"model_profile_unregistered:{profile}")
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                raise TypeError(f"model_profile_requires_pydantic_model:{profile}")
            if model.model_config.get("extra") != "forbid":
                raise ValueError(f"model_must_forbid_unknown_fields:{profile}")
            adapters[profile] = TypeAdapter(model)
        object.__setattr__(self, "_adapters", MappingProxyType(adapters))
        object.__setattr__(
            self, "_tools", MappingProxyType({key: catalog[key] for key in required})
        )
        object.__setattr__(self, "_functions", MappingProxyType(functions))

    def _validate(self, profile: str, payload: Any) -> BaseModel:
        return self._adapters[profile].validate_python(payload, strict=True, extra="forbid")

    def validate_task_input(self, payload: Any) -> BaseModel:
        return self._validate(self.task.input_profile, payload)

    def validate_native_result(self, tool_id: str, version: str, payload: Any) -> BaseModel:
        tool = self._lookup(self._tools, (tool_id, version), "native_tool_not_permitted")
        return self._validate(tool.output_profile, payload)

    def validate_function_result(self, function_id: str, version: str, payload: Any) -> BaseModel:
        function = self._lookup(self._functions, (function_id, version), "function_not_permitted")
        return self._validate(function.result_profile, payload)

    @staticmethod
    def _lookup(registry, key, error):
        if key not in registry:
            raise ValueError(error)
        return registry[key]

    def validate_action(self, payload: Any) -> NativeAction | FunctionAction | FinalAction:
        action = ACTION_ADAPTER.validate_python(payload, strict=True)
        if isinstance(action, NativeAction):
            tool = self._lookup(
                self._tools, (action.tool_id, action.tool_version), "native_tool_not_permitted"
            )
            self._validate(tool.input_profile, action.arguments)
        elif isinstance(action, FunctionAction):
            function = self._lookup(
                self._functions,
                (action.function_id, action.function_version),
                "function_not_permitted",
            )
            self._validate(function.input_profile, action.arguments)
        else:
            if (action.task_id, action.task_version) != (self.task.task_id, self.task.version):
                raise ValueError("final_result_task_mismatch")
            self._validate(self.task.result_profile, action.result)
        return action
