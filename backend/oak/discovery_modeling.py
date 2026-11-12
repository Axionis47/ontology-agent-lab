"""Define discovery drafts without changing executable kernel declarations."""

from typing import Literal

from pydantic import Field, model_validator

from oak.discovery_schemas import (
    EvidenceRef,
    ProbeDecision,
    PropertyProposal,
    QuestionProposal,
    RequirementsProposal,
    SchemaProposal,
    Strict,
)


class ModelingTarget(Strict):
    kind: Literal["requirement", "entity", "property", "relation", "function"]
    id: str = Field(min_length=1)
    property: str | None = None


class ModelingChoice(Strict):
    target: ModelingTarget
    requirement_ids: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=4000)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=20)
    unresolved: list[str] = Field(default_factory=list, max_length=20)
    identity_scope: str | None = None
    connection_rule: str | None = None


class FunctionNeed(Strict):
    id: str = Field(min_length=1)
    parameters: list[PropertyProposal] = Field(default_factory=list, max_length=100)
    output_kind: Literal["rows", "scalar", "decision", "entities"]
    outputs: list[PropertyProposal] = Field(default_factory=list, max_length=100)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    dependencies: list[ModelingTarget] = Field(default_factory=list, max_length=100)
    missing_evidence: str = Field(min_length=1, max_length=2000)


class ProbeQuestion(Strict):
    question: str = Field(min_length=1, max_length=2000)
    requirement_ids: list[str] = Field(min_length=1)
    targets: list[ModelingTarget] = Field(min_length=1, max_length=30)
    expected_information: str = Field(min_length=1, max_length=2000)


class AccessCapability(Strict):
    capability: Literal[
        "identity", "filters", "projection", "pagination", "ordering", "completeness"
    ]
    status: Literal["supported", "unsupported", "unknown"]
    description: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=10)


class ToolAccess(Strict):
    tool_id: str
    capabilities: list[AccessCapability] = Field(min_length=6, max_length=6)


class DiscoveryRound(Strict):
    version: Literal["oak.discovery.v1"] = "oak.discovery.v1"
    summary: str = Field(min_length=1, max_length=4000)
    requirements: RequirementsProposal
    schema_proposal: SchemaProposal
    choices: list[ModelingChoice] = Field(default_factory=list, max_length=1000)
    function_needs: list[FunctionNeed] = Field(default_factory=list, max_length=100)
    tool_access: list[ToolAccess] = Field(default_factory=list, max_length=100)
    action: Literal["call", "questions", "revise", "finish", "finish_gaps", "conflict"]
    probe: ProbeDecision | None = None
    probe_question: ProbeQuestion | None = None
    questions: list[QuestionProposal] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def check_action(self):
        if self.action == "call":
            if self.probe is None or self.probe.action != "call" or self.probe_question is None:
                raise ValueError("A probe requires a call and a modeling question.")
            if not self.probe.tool_id or self.probe.questions or self.probe.conflict:
                raise ValueError(
                    "A probe must select one tool without pending questions or conflicts."
                )
        elif self.probe is not None or self.probe_question is not None:
            raise ValueError("Only a call can contain a probe and its modeling question.")
        pending = self.questions + self.requirements.questions
        if (self.action == "questions") != bool(pending) or len(pending) > 3:
            raise ValueError("A clarification action requires one through three questions.")
        return self


ROUND_INSTRUCTIONS = """Develop requirements and schema together with tool exploration.
Record tool_access for each granted tool. Describe identity lookup, filters,
projection, pagination, ordering, and completeness separately. Cite the native
catalog contract for each capability. Mark unsupported or unknown capabilities
explicitly. A sample response cannot prove a source guarantee. Explain native
argument paths, response continuation paths, and source limitations. Use available
filters and bounded pages for probes when they preserve the task question.
Return one complete DiscoveryRound. The current_draft is the last usable revision.
Use its findings, actual observations, and clarifications to revise the proposal.
Keep identifiers when their meaning is unchanged. Update dependent declarations together.
Cover every inputs.source_sections path with an exact input reference in a requirement or gap.
Do not remove an original requirement merely because evidence is unavailable.

Apply these modeling rules. An entity needs independent identification, connections,
or state tracking for this task. State its identity scope and supported identity fields.
A property describes an entity and does not need separate identity for the task.
A relation connects entities for a task requirement. State the source-supported
connection rule and bind both endpoint fields. Similar names cannot establish identity.
A function need describes a computation or check over typed inputs and evidence.
Declare its output, dependencies, and missing-evidence behavior. Do not generate steps
or executable programs. Training constructs functions after baseline ReAct executions.
Use string, integer, boolean, decimal, and scalar arrays. Identity fields are scalar
strings, integers, or booleans. Relation endpoints have equal scalar types and units.
The runtime supports lookup, traversal, filtering, projection, aggregation, assertions,
and decisions. Record unsupported computations as gaps. Do not invent new operators.

Give every entity, property, relation, and function need one choice with its task
purpose, representation reason, source evidence, and unresolved assumptions.
Property targets use the entity id and property name. Other targets omit property.
Nested response objects do not automatically become entities. Keep the proposal small.
Actual responses supply observed values. Tool declarations support proposed structure.
Do not treat a draft, explanation, user clarification, or computed value as a tool fact.
Each binding cites an actual /data/... observation field or the tool's
/tools/N/output_schema/... declaration. Unsupported bindings must remain gaps.
Provisional entities can lack identity fields. Provisional properties can lack bindings.
Record these missing dependencies explicitly. They prevent readiness, not exploration.

Choose call, questions, revise, finish, finish_gaps, or conflict. A call includes one
ProbeDecision and a probe_question: the unresolved question, affected requirements and
targets, and expected information. Initial probes can target a requirement.
Call only granted tools. Use observed source IDs. Probe writes only when the target
and purpose are clear from the original task. Never repeat a completed write.
Prefer independent reads before asking blocking intent questions. User answers cannot
prove source guarantees. If resume_requires_fresh_reads is true, read before a new write.
For a write confirmation, use confirmation_for with its invocation_id and matching
JSON Pointers into the saved write and read payloads. Read paths start with /data/.
For an acknowledgment-only write, written_source=request selects saved arguments.
Do not claim wider guarantees from matching fields.

Use revise to correct the draft from saved evidence. Finish requests full package checks.
Failed checks return to this loop. Use finish_gaps only when no supported next step can
resolve the remaining gaps; explain this in summary and record blocking gaps.
Resource limits are controlled by the host. Proposals remain untrained at completion.
"""


def target_key(target):
    return target.kind, target.id, target.property


def declaration_targets(proposal):
    targets = {("entity", entity.id, None) for entity in proposal.schema_proposal.entities}
    targets.update(
        ("property", entity.id, prop.name)
        for entity in proposal.schema_proposal.entities
        for prop in entity.properties
    )
    targets.update(("relation", item.id, None) for item in proposal.schema_proposal.relations)
    targets.update(("function", item.id, None) for item in proposal.function_needs)
    return targets


def check_modeling_references(proposal):
    """Reject references to declarations outside the current revision."""
    targets = declaration_targets(proposal)
    reqs = {r.id for r in proposal.requirements.requirements}
    seen = set()
    for choice in proposal.choices:
        key = target_key(choice.target)
        if key not in targets or key in seen:
            raise ValueError("A modeling choice has an unknown or duplicate target.")
        if not set(choice.requirement_ids) <= reqs:
            raise ValueError("A modeling choice has an unknown requirement.")
        seen.add(key)
    if len({f.id for f in proposal.function_needs}) != len(proposal.function_needs):
        raise ValueError("Function need IDs must be unique.")
    for function in proposal.function_needs:
        if any(target_key(t) not in targets or t.kind == "function" for t in function.dependencies):
            raise ValueError("A function need has an unknown evidence dependency.")
    if proposal.probe_question:
        question = proposal.probe_question
        available = targets | {("requirement", r, None) for r in reqs}
        if not set(question.requirement_ids) <= reqs or any(
            target_key(t) not in available for t in question.targets
        ):
            raise ValueError("A probe question has an unknown requirement or modeling target.")


def value_errors(field, label):
    errors = []
    scalar = {"string", "integer", "boolean", "decimal"}
    if field.type not in scalar | {"array"}:
        errors.append(f"{label} has an unsupported type.")
    if (field.type == "array") != (field.item_type in scalar):
        errors.append(f"{label} requires an element type only for an array.")
    if field.unit and (field.item_type if field.type == "array" else field.type) not in {
        "integer",
        "decimal",
    }:
        errors.append(f"{label} has units on a nonnumeric type.")
    return errors


def modeling_errors(proposal):
    """Check readiness without treating semantic explanations as proof."""
    errors = []
    schema = proposal.schema_proposal
    choices = {target_key(c.target): c for c in proposal.choices}
    for key in sorted(declaration_targets(proposal)):
        choice = choices.get(key)
        label = ".".join(str(v) for v in key if v is not None)
        if choice is None:
            errors.append(f"{label} has no modeling explanation.")
        elif choice.unresolved:
            errors.append(f"{label} has unresolved assumptions: {'; '.join(choice.unresolved)}")
    bound = {(b.entity_id, b.property) for b in schema.bindings}
    entities = {e.id: e for e in schema.entities}
    for entity in schema.entities:
        choice = choices.get(("entity", entity.id, None))
        if not entity.identity_keys or not choice or not (choice.identity_scope or "").strip():
            errors.append(f"Entity {entity.id} requires identity fields and a source scope.")
        for prop in entity.properties:
            errors.extend(value_errors(prop, f"Property {entity.id}.{prop.name}"))
            if (entity.id, prop.name) not in bound:
                errors.append(f"Property {entity.id}.{prop.name} has no supported source binding.")
            if prop.name in entity.identity_keys and prop.type not in {
                "string",
                "integer",
                "boolean",
            }:
                errors.append(
                    f"Identity {entity.id}.{prop.name} must have a supported scalar type."
                )
    for relation in schema.relations:
        choice = choices.get(("relation", relation.id, None))
        if not choice or not (choice.connection_rule or "").strip():
            errors.append(f"Relation {relation.id} requires a source-supported connection rule.")
        endpoints = []
        for entity_id, name in (
            (relation.from_entity, relation.from_property),
            (relation.to_entity, relation.to_property),
        ):
            entity = entities.get(entity_id)
            field = next((p for p in entity.properties if p.name == name), None) if entity else None
            if field:
                endpoints.append((field.type, field.unit))
        if len(endpoints) == 2 and (endpoints[0] != endpoints[1] or endpoints[0][0] == "array"):
            errors.append(
                f"Relation {relation.id} requires matching scalar endpoint types and units."
            )
    for function in proposal.function_needs:
        for group in (function.parameters, function.outputs):
            if len({p.name for p in group}) != len(group):
                errors.append(f"Function need {function.id} has duplicate field names.")
            for field in group:
                errors.extend(value_errors(field, f"Function need {function.id}.{field.name}"))
        if function.output_kind in {"rows", "scalar"} and not function.outputs:
            errors.append(f"Function need {function.id} requires typed output fields.")
        if function.output_kind == "scalar" and len(function.outputs) != 1:
            errors.append(f"Function need {function.id} requires one scalar output.")
        if function.output_kind == "entities" and not function.entity_ids:
            errors.append(f"Function need {function.id} requires output entity types.")
        if not set(function.entity_ids) <= entities.keys():
            errors.append(f"Function need {function.id} has an unknown output entity type.")
    return errors
