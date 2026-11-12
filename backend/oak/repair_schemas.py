"""Typed declarations for a candidate and one targeted repair."""

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

from oak.discovery_schemas import (
    EntityProposal,
    EvidenceRef,
    OperationProposal,
    RelationProposal,
    RequirementsProposal,
    SchemaProposal,
    SourceBinding,
)

Identifier = Annotated[str, Field(min_length=1, max_length=200)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ScalarType = Literal["string", "integer", "boolean"]
ValueType = Literal["string", "integer", "boolean", "decimal", "array"]
ElementType = Literal["string", "integer", "boolean", "decimal"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldExpression(Frozen):
    kind: Literal["field"] = "field"
    name: Identifier


class ArgumentExpression(Frozen):
    kind: Literal["argument"] = "argument"
    name: Identifier


class RequestExpression(Frozen):
    kind: Literal["request"] = "request"
    name: Identifier


class LiteralExpression(Frozen):
    kind: Literal["literal"] = "literal"
    value: StrictStr | StrictInt | StrictBool
    unit: str | None = None


class TypedLiteralExpression(Frozen):
    kind: Literal["typed_literal"] = "typed_literal"
    type: ValueType
    value: StrictStr | StrictInt | StrictBool | list[StrictStr | StrictInt | StrictBool]
    item_type: ElementType | None = None
    unit: str | None = None


class ResultExpression(Frozen):
    kind: Literal["result"] = "result"
    step_id: Identifier
    field: Identifier = "value"


class AddExpression(Frozen):
    kind: Literal["add"] = "add"
    left: "Expression"
    right: "Expression"


class MultiplyExpression(Frozen):
    kind: Literal["multiply"] = "multiply"
    left: "Expression"
    right: "Expression"


class ConvertExpression(Frozen):
    kind: Literal["convert"] = "convert"
    value: "Expression"
    unit: str


Expression = Annotated[
    FieldExpression
    | ArgumentExpression
    | RequestExpression
    | LiteralExpression
    | AddExpression
    | MultiplyExpression
    | ConvertExpression
    | TypedLiteralExpression
    | ResultExpression,
    Field(discriminator="kind"),
]


class Comparison(Frozen):
    operator: Literal["eq", "ne", "lt", "le", "gt", "ge"]
    left: Expression
    right: Expression


class MembershipPredicate(Frozen):
    operator: Literal["in", "not_in", "overlap_any", "overlap_all", "overlap_min"]
    left: Expression
    right: Expression
    minimum: Expression | None = None


class EntityAnchor(Frozen):
    entity_id: Identifier
    identity: dict[str, Expression] = Field(min_length=1, max_length=3)
    context: dict[str, Expression] = Field(default_factory=dict, max_length=20)


class ConnectedPredicate(Frozen):
    operator: Literal["connected"] = "connected"
    relation_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=200)
    anchors: tuple[EntityAnchor, ...] = Field(min_length=1, max_length=1000)
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
    max_hops: StrictInt = Field(default=1, ge=1, le=4)
    contexts: dict[str, dict[str, Expression]] = Field(default_factory=dict, max_length=100)


Predicate = Annotated[
    Comparison | MembershipPredicate | ConnectedPredicate, Field(discriminator="operator")
]


class Constraint(Frozen):
    id: Identifier
    entity_id: Identifier | None = None
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)
    predicate: Predicate


class FieldMapping(Frozen):
    property: Identifier
    path: str = Field(pattern=r"^(|/.*)$", max_length=2000)


class MappingScope(Frozen):
    name: Identifier
    path: str = Field(pattern=r"^(|/.*)$", max_length=2000)
    source: Literal["arguments", "data"] = "arguments"


class CoverageContract(Frozen):
    kind: Literal["complete_response", "flag"]
    path: str = ""
    support: EvidenceRef


class RecordMapping(Frozen):
    id: Identifier
    entity_id: Identifier
    tool_id: Identifier
    collection_path: str = Field(pattern=r"^(|/.*)$", max_length=2000)
    fields: tuple[FieldMapping, ...] = Field(min_length=1, max_length=100)
    scope: tuple[MappingScope, ...] = Field(default=(), max_length=20)
    update_mode: Literal["replacement", "partial"] = "replacement"
    update_support: EvidenceRef | None = None
    coverage: CoverageContract | None = None


class Parameter(Frozen):
    name: Identifier
    type: ValueType
    nullable: StrictBool = False
    unit: str | None = None
    item_type: ElementType | None = Field(default=None, exclude_if=lambda value: value is None)


class RequestField(Parameter):
    id: Identifier
    description: str = Field(min_length=1, max_length=2000)
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)


class InputStep(Frozen):
    op: Literal["input"] = "input"
    id: Identifier


class OutputField(Parameter):
    pass


class RowsOutput(Frozen):
    kind: Literal["rows"] = "rows"
    fields: tuple[OutputField, ...] = Field(min_length=1, max_length=100)


class ScalarOutput(Frozen):
    kind: Literal["scalar"] = "scalar"
    type: ElementType
    nullable: StrictBool = False
    unit: str | None = None


class LookupStep(Frozen):
    op: Literal["lookup"] = "lookup"
    id: Identifier
    entity_id: Identifier | None = Field(default=None, exclude_if=lambda value: value is None)
    identity: dict[str, Expression] = Field(default_factory=dict, max_length=3)
    context: dict[str, Expression] = Field(default_factory=dict, max_length=20)
    entity_types: tuple[Identifier, ...] = Field(
        default=(), max_length=100, exclude_if=lambda v: not v
    )
    identifiers: Expression | None = Field(default=None, exclude_if=lambda v: v is None)
    property_filters: dict[str, Expression] = Field(
        default_factory=dict, max_length=100, exclude_if=lambda v: not v
    )
    contexts: dict[str, dict[str, Expression]] = Field(
        default_factory=dict, max_length=100, exclude_if=lambda v: not v
    )
    name_query: Expression | None = Field(default=None, exclude_if=lambda v: v is None)
    text_query: Expression | None = Field(default=None, exclude_if=lambda v: v is None)
    name_fields: tuple[Identifier, ...] = Field(
        default=(), max_length=100, exclude_if=lambda v: not v
    )
    text_fields: tuple[Identifier, ...] = Field(
        default=(), max_length=100, exclude_if=lambda v: not v
    )
    fuzzy: StrictBool = Field(default=True, exclude_if=lambda v: v is True)
    min_score: str = Field(default="0", exclude_if=lambda v: v == "0")
    top_k: StrictInt | None = Field(default=None, ge=1, le=10000, exclude_if=lambda v: v is None)
    population: StrictBool = Field(default=False, exclude_if=lambda v: not v)


class TraverseStep(Frozen):
    op: Literal["traverse"] = "traverse"
    id: Identifier
    input: Identifier
    relation_id: Identifier | None = Field(default=None, exclude_if=lambda v: v is None)
    direction: Literal["forward", "reverse", "outgoing", "incoming", "both"] = "forward"
    context: dict[str, Expression] = Field(default_factory=dict, max_length=20)
    relation_ids: tuple[Identifier, ...] = Field(
        default=(), max_length=200, exclude_if=lambda v: not v
    )
    contexts: dict[str, dict[str, Expression]] = Field(
        default_factory=dict, max_length=100, exclude_if=lambda v: not v
    )
    max_hops: StrictInt = Field(default=1, ge=1, le=4, exclude_if=lambda v: v == 1)
    include_starting_entities: StrictBool | None = Field(
        default=None, exclude_if=lambda v: v is None
    )


class SelectTypesStep(Frozen):
    op: Literal["select_types"] = "select_types"
    id: Identifier
    input: Identifier
    entity_types: tuple[Identifier, ...] = Field(min_length=1, max_length=100)


class SelectGroupStep(Frozen):
    op: Literal["select_group"] = "select_group"
    id: Identifier
    input: Identifier
    key: Expression


class AssertStep(Frozen):
    op: Literal["assert"] = "assert"
    id: Identifier
    input: Identifier
    constraint_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)


class DecisionStep(Frozen):
    op: Literal["decision"] = "decision"
    id: Identifier
    inputs: tuple[Identifier, ...] = Field(min_length=1, max_length=30)


class DecisionOutput(Frozen):
    kind: Literal["decision"] = "decision"


class FilterStep(Frozen):
    op: Literal["filter"] = "filter"
    id: Identifier
    input: Identifier
    constraint_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=10)


class Projection(Frozen):
    name: Identifier
    expression: Expression
    missing_value: Expression | None = Field(default=None, exclude_if=lambda v: v is None)
    nullable: StrictBool = Field(default=False, exclude_if=lambda v: not v)


class ProjectStep(Frozen):
    op: Literal["project"] = "project"
    id: Identifier
    input: Identifier
    fields: tuple[Projection, ...] = Field(min_length=1, max_length=100)


class AggregateStep(Frozen):
    op: Literal["aggregate"] = "aggregate"
    id: Identifier
    input: Identifier
    operation: Literal["count", "sum", "min", "max", "average"]
    expression: Expression | None = None
    group_by: Identifier | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def check_expression(self):
        if (self.operation == "count") != (self.expression is None):
            raise ValueError("Only count omits its expression.")
        return self


class SelectMinStep(Frozen):
    op: Literal["select_min"] = "select_min"
    id: Identifier
    input: Identifier
    order_by: tuple[Expression, ...] = Field(min_length=1, max_length=10)


PlanStep = Annotated[
    InputStep
    | LookupStep
    | TraverseStep
    | FilterStep
    | ProjectStep
    | AggregateStep
    | SelectMinStep
    | AssertStep
    | DecisionStep
    | SelectTypesStep
    | SelectGroupStep,
    Field(discriminator="op"),
]


class EntitiesOutput(Frozen):
    kind: Literal["entities"] = "entities"
    entity_types: tuple[Identifier, ...] = Field(min_length=1, max_length=100)


class Function(Frozen):
    id: Identifier
    entity_id: Identifier | None = None
    parameters: tuple[Parameter, ...] = Field(default=(), max_length=100)
    required_constraint_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    steps: tuple[PlanStep, ...] = Field(min_length=1, max_length=100)
    return_step: Identifier
    output: Annotated[
        RowsOutput | ScalarOutput | DecisionOutput | EntitiesOutput, Field(discriminator="kind")
    ]


class CheckBinding(Frozen):
    function_id: Identifier
    arguments: dict[str, str] = Field(default_factory=dict, max_length=100)


class AccessFilter(Frozen):
    path: str = Field(pattern=r"^/", max_length=2000)
    value: Expression
    support: EvidenceRef


class PageAccess(Frozen):
    cursor_path: str = Field(pattern=r"^/", max_length=2000)
    next_cursor_path: str = Field(pattern=r"^/", max_length=2000)
    size_path: str | None = None
    max_size: StrictInt = Field(default=100, ge=1, le=1000)
    initial_cursor: StrictStr | StrictInt | None = None
    support: EvidenceRef


class SourceAccess(Frozen):
    kind: Literal["data", "action"]
    mapping_ids: tuple[Identifier, ...] = Field(default=(), max_length=300)
    filters: tuple[AccessFilter, ...] = Field(default=(), max_length=100)
    projection_path: str | None = None
    projection_fields: dict[str, str] = Field(default_factory=dict, max_length=300)
    pagination: PageAccess | None = None
    fixed_arguments: dict[str, JsonValue] = Field(default_factory=dict, max_length=100)
    unsupported: tuple[
        Literal["identity", "filters", "projection", "pagination", "ordering", "completeness"], ...
    ] = ()
    support: EvidenceRef


class OperationBinding(Frozen):
    id: Identifier
    tool_id: Identifier
    checks: tuple[CheckBinding, ...] = Field(min_length=1, max_length=30)
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)
    credential_paths: tuple[str, ...] = Field(default=(), max_length=20)
    source_access: SourceAccess | None = Field(default=None, exclude_if=lambda v: v is None)


class RequirementCoverage(Frozen):
    id: Identifier
    requirement_id: Identifier
    request_field_ids: tuple[Identifier, ...] = ()
    constraint_ids: tuple[Identifier, ...] = ()
    binding_ids: tuple[Identifier, ...] = Field(min_length=1)


class FormalAxiom(Frozen):
    id: Identifier
    kind: Literal[
        "subclass", "disjoint", "restriction", "functional", "inverse_functional", "inverse"
    ]
    entity_id: Identifier | None = None
    target_entity_id: Identifier | None = None
    relation_id: Identifier | None = None
    inverse_relation_id: Identifier | None = None
    restriction: Literal["some", "only", "min", "max", "exactly"] | None = None
    cardinality: int | None = Field(default=None, ge=0, le=1000)
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)


class Candidate(Frozen):
    model_config = ConfigDict(extra="forbid", frozen=True, serialize_by_alias=True)

    version: Literal["oak.candidate.v1", "oak.candidate.v2", "oak.candidate.v3"] = (
        "oak.candidate.v1"
    )
    original_input_digest: Digest
    requirements: RequirementsProposal
    schema_data: SchemaProposal = Field(alias="schema")
    mappings: tuple[RecordMapping, ...] = Field(default=(), max_length=300)
    constraints: tuple[Constraint, ...] = Field(default=(), max_length=100)
    functions: tuple[Function, ...] = Field(default=(), max_length=100)
    request_fields: tuple[RequestField, ...] = Field(default=(), max_length=100)
    operation_bindings: tuple[OperationBinding, ...] = Field(default=(), max_length=100)
    requirement_coverage: tuple[RequirementCoverage, ...] = Field(default=(), max_length=200)
    formal_axioms: tuple[FormalAxiom, ...] = Field(default=(), max_length=200)

    @property
    def schema(self) -> SchemaProposal:
        return self.schema_data

    @model_validator(mode="after")
    def copy_discovery_records(self):
        # Discovery models are mutable. Keep a separate copy in this candidate.
        object.__setattr__(self, "requirements", self.requirements.model_copy(deep=True))
        object.__setattr__(self, "schema_data", self.schema.model_copy(deep=True))
        return self


class CandidateV2(Candidate):
    version: Literal["oak.candidate.v2"] = "oak.candidate.v2"


class CandidateV3(Candidate):
    version: Literal["oak.candidate.v3"] = "oak.candidate.v3"


Value = TypeVar("Value", bound=BaseModel)


class Change(Frozen, Generic[Value]):
    op: Literal["add", "replace", "remove"]
    id: Identifier
    expected_digest: Digest | None = None
    value: Value | None = None

    @model_validator(mode="after")
    def check_operation(self):
        if self.op == "add" and self.expected_digest is not None:
            raise ValueError("An add operation cannot have an old-value digest.")
        if self.op != "add" and self.expected_digest is None:
            raise ValueError("Replacement and removal require an old-value digest.")
        if (self.op == "remove") != (self.value is None):
            raise ValueError("Only removal omits its value.")
        if self.value is not None and self.value.id != self.id:
            raise ValueError("The value ID must match the target ID.")
        return self


class EntityChange(Change[EntityProposal]):
    collection: Literal["entities"] = "entities"


class RelationChange(Change[RelationProposal]):
    collection: Literal["relations"] = "relations"


class BindingChange(Change[SourceBinding]):
    collection: Literal["bindings"] = "bindings"


class OperationChange(Change[OperationProposal]):
    collection: Literal["operations"] = "operations"


class MappingChange(Change[RecordMapping]):
    collection: Literal["mappings"] = "mappings"


class ConstraintChange(Change[Constraint]):
    collection: Literal["constraints"] = "constraints"


class FunctionChange(Change[Function]):
    collection: Literal["functions"] = "functions"


class RequestFieldChange(Change[RequestField]):
    collection: Literal["request_fields"] = "request_fields"


class OperationBindingChange(Change[OperationBinding]):
    collection: Literal["operation_bindings"] = "operation_bindings"


class RequirementCoverageChange(Change[RequirementCoverage]):
    collection: Literal["requirement_coverage"] = "requirement_coverage"


class FormalAxiomChange(Change[FormalAxiom]):
    collection: Literal["formal_axioms"] = "formal_axioms"


PatchChange = Annotated[
    EntityChange
    | RelationChange
    | BindingChange
    | OperationChange
    | MappingChange
    | ConstraintChange
    | FunctionChange
    | RequestFieldChange
    | OperationBindingChange
    | RequirementCoverageChange
    | FormalAxiomChange,
    Field(discriminator="collection"),
]


class DiagnosedFault(Frozen):
    id: Identifier
    sample_id: Identifier | None = None
    validation_event_id: Identifier | None = None
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def has_fault_source(self):
        if not self.sample_id and not self.validation_event_id:
            raise ValueError("A fault needs a failed sample or an immutable validation event.")
        return self


class TargetedPatch(Frozen):
    version: Literal["oak.patch.v1"] = "oak.patch.v1"
    id: Identifier
    base_digest: Digest
    original_input_digest: Digest
    fault: DiagnosedFault
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=100)
    changes: tuple[PatchChange, ...] = Field(min_length=1, max_length=100)

    @property
    def failed_requirement_ids(self):
        return self.fault.requirement_ids

    @model_validator(mode="after")
    def unique_targets(self):
        targets = [(change.collection, change.id) for change in self.changes]
        if len(targets) != len(set(targets)):
            raise ValueError("A patch cannot change the same target twice.")
        return self


class PatchReceipt(Frozen):
    patch_id: Identifier
    patch_digest: Digest
    base_digest: Digest
    result_digest: Digest


class PatchApplication(Frozen):
    candidate: Candidate
    receipt: PatchReceipt
    already_applied: bool = False


AddExpression.model_rebuild()
MultiplyExpression.model_rebuild()
ConvertExpression.model_rebuild()

Patch = TargetedPatch
