"""OWL checks and a bounded catalog of typed reasoning operators."""

import hashlib
import json
import os
import types
from pathlib import Path
from typing import Annotated, Literal

import owlready2 as owl
from pydantic import BaseModel, ConfigDict, Field

from .program import Name, Program, calculate, matches, validate_program

EntityType = Literal["Hotel", "RoomOffer", "ChildPolicy"]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Count = Annotated[int, Field(ge=0, le=100000000)]
TASK = (
    "Find all eligible room offers for two or more guests, including one child. "
    "Use the requested city, nights, adults, child age, and total budget in USD cents. "
    "Each offer belongs to one hotel. Each hotel has one child policy. "
    "Capacity must cover adults plus one child. The child must meet the minimum age. "
    "Total cost is nightly_cents multiplied by nights, plus fee_cents once. "
    "Every offer must link to a hotel and that hotel to a policy. "
    "If any such link is absent, or any source ID has conflicting records, return "
    "incomplete for the whole snapshot with no eligible offers. This includes distractors. "
    "Identical duplicate records are allowed. Do not invent facts."
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Query(Record):
    city: Annotated[str, Field(min_length=1, max_length=80)]
    nights: Annotated[int, Field(ge=1, le=30)]
    adults: Annotated[int, Field(ge=1, le=20)]
    child_age: Annotated[int, Field(ge=0, le=17)]
    budget_cents: Count


class Hotel(Record):
    id: Identifier
    city: str
    policy_id: Identifier | None


class Offer(Record):
    id: Identifier
    hotel_id: Identifier
    capacity: Annotated[int, Field(ge=1, le=100)]
    nightly_cents: Count
    fee_cents: Count


class Policy(Record):
    id: Identifier
    minimum_child_age: Annotated[int, Field(ge=0, le=18)]


class Inventory(Record):
    hotels: tuple[Hotel, ...]
    offers: tuple[Offer, ...]


class Policies(Record):
    policies: tuple[Policy, ...]


FIELDS = {
    "Hotel": {"id": "string", "city": "string", "policy_id": "string"},
    "RoomOffer": {
        "id": "string",
        "hotel_id": "string",
        "capacity": "integer",
        "nightly_cents": "integer",
        "fee_cents": "integer",
    },
    "ChildPolicy": {"id": "string", "minimum_child_age": "integer"},
}
INPUTS = {name: field["type"] for name, field in Query.model_json_schema()["properties"].items()}


class Match(Record):
    offer_id: Identifier
    total_cents: Count
    evidence: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]


class OperatorTrace(Record):
    operator: str
    remaining: tuple[Identifier, ...]


class Eligibility(Record):
    status: Literal["complete", "incomplete"]
    eligible: tuple[Match, ...]
    missing_links_for: tuple[Identifier, ...] = ()
    operator_trace: tuple[OperatorTrace, ...] = ()
    owl: Literal["schema_validated", "not_checked"] = "not_checked"


class FunctionOutput(Eligibility):
    receipt: str


class AcceptedAnswer(Eligibility):
    kernel: str
    graph_revision: int
    query: Query


class Relation(Record):
    name: Name
    source: EntityType
    target: EntityType
    source_field: Name
    minimum: Annotated[int, Field(ge=0, le=2)]
    maximum: Annotated[int, Field(ge=0, le=2)]


class Candidate(Record):
    """Source types are fixed. Relations and computations are generated."""

    disjoint: tuple[tuple[EntityType, EntityType], ...] = Field(max_length=3)
    relations: tuple[Relation, ...] = Field(min_length=2, max_length=2)
    program: Program

    @property
    def fingerprint(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


def create_world(candidate: Candidate):
    world = owl.World()
    ontology = world.get_ontology("https://oak.example/hotel#")
    with ontology:
        for name in ("Hotel", "RoomOffer", "ChildPolicy"):
            types.new_class(name, (owl.Thing,))
        for left, right in candidate.disjoint:
            owl.AllDisjoint([ontology[left], ontology[right]])
        for relation in candidate.relations:
            prop = types.new_class(relation.name, (owl.ObjectProperty,))
            prop.domain = [ontology[relation.source]]
            prop.range = [ontology[relation.target]]
            source = ontology[relation.source]
            target = ontology[relation.target]
            source.is_a.extend(
                [
                    prop.min(relation.minimum, target),
                    prop.max(relation.maximum, target),
                    prop.only(target),
                ]
            )
        for name, domain, value_type in (
            ("city", "Hotel", str),
            ("capacity", "RoomOffer", int),
            ("nightly_cents", "RoomOffer", int),
            ("fee_cents", "RoomOffer", int),
            ("minimum_child_age", "ChildPolicy", int),
        ):
            prop = types.new_class(name, (owl.DataProperty, owl.FunctionalProperty))
            prop.domain = [ontology[domain]]
            prop.range = [value_type]
    return world, ontology


def check_owl(world):
    """Run HermiT. Check both global consistency and unsatisfiable classes."""
    if os.environ.get("OAK_JAVA"):
        owl.JAVA_EXE = os.environ["OAK_JAVA"]
    elif Path("/opt/homebrew/opt/openjdk@21/bin/java").is_file():
        owl.JAVA_EXE = "/opt/homebrew/opt/openjdk@21/bin/java"
    try:
        owl.sync_reasoner(world, debug=0)
    except owl.OwlReadyInconsistentOntologyError as exc:
        raise ValueError("OWL global consistency failed.") from exc
    except owl.OwlReadyJavaError as exc:
        raise RuntimeError("HermiT failed. Check Java and OAK_JAVA.") from exc
    invalid = [c.name for c in world.inconsistent_classes() if c != owl.Nothing]
    if invalid:
        raise ValueError(f"OWL unsatisfiable classes: {sorted(invalid)}")


def validate_candidate(candidate: Candidate, owl_path: Path | None = None):
    names = [relation.name for relation in candidate.relations]
    reserved = set(FIELDS) | {field for fields in FIELDS.values() for field in fields}
    reserved |= {"Thing", "Nothing", "ObjectProperty", "DataProperty", "type"}
    if len(set(names)) != len(names):
        raise ValueError("Relation names must be unique.")
    if set(names) & reserved:
        raise ValueError("Relation names must not replace source types or fields.")
    if candidate.program.root_type != "RoomOffer":
        raise ValueError("The function output contract requires RoomOffer as the root type.")
    world, ontology = create_world(candidate)
    try:
        check_owl(world)
        # These are adapter requirements. They are not OWL completeness checks.
        relations = {relation.name: relation for relation in candidate.relations}
        if len(relations) != len(candidate.relations):
            raise ValueError("Relation names must be unique.")
        for relation in candidate.relations:
            if FIELDS[relation.source].get(relation.source_field) != "string":
                raise ValueError("A relation must refer to a string source key.")
        pairs = {frozenset(p) for p in candidate.disjoint}
        if pairs != {
            frozenset(("Hotel", "RoomOffer")),
            frozenset(("Hotel", "ChildPolicy")),
            frozenset(("RoomOffer", "ChildPolicy")),
        }:
            raise ValueError("The three source record types must be pairwise disjoint.")
        validate_program(candidate.program, relations, FIELDS, INPUTS)
        if owl_path:
            ontology.save(file=str(owl_path), format="rdfxml")
    finally:
        world.close()


def unique(records):
    result = {}
    for record in records:
        if record.id in result and result[record.id] != record:
            raise ValueError(f"Conflicting source records for {record.id}.")
        result[record.id] = record
    return result


def reason(candidate: Candidate, query: Query, inventory: Inventory, policies: Policies):
    """Instantiate a typed graph and execute the generated function plan."""
    try:
        collections = {
            "Hotel": unique(inventory.hotels),
            "RoomOffer": unique(inventory.offers),
            "ChildPolicy": unique(policies.policies),
        }
    except ValueError:
        return {"status": "incomplete", "eligible": [], "missing_links_for": []}
    nodes = {
        kind: {key: value.model_dump() for key, value in records.items()}
        for kind, records in collections.items()
    }
    relations = {relation.name: relation for relation in candidate.relations}
    program, request = candidate.program, query.model_dump()
    validate_program(program, relations, FIELDS, INPUTS)
    rows = [{program.root_alias: node} for node in nodes[program.root_type].values()]
    trace = [{"operator": "lookup", "remaining": [r[program.root_alias]["id"] for r in rows]}]
    aliases = {program.root_alias: program.root_type}
    for traversal in program.traversals:
        relation = relations[traversal.relation]
        aliases[traversal.target_alias] = relation.target
        missing = []
        for row in rows:
            source = row[traversal.source_alias]
            target = nodes[relation.target].get(source.get(relation.source_field))
            if target is None:
                missing.append(row[program.root_alias]["id"])
            else:
                row[traversal.target_alias] = target
        if missing:
            return {"status": "incomplete", "missing_links_for": sorted(missing), "eligible": []}
        trace.append(
            {
                "operator": f"traverse:{traversal.relation}",
                "remaining": [r[program.root_alias]["id"] for r in rows],
            }
        )
    for index, predicate in enumerate(program.filters):
        rows = [row for row in rows if matches(predicate, row, request)]
        trace.append(
            {
                "operator": f"filter:{index}",
                "remaining": [r[program.root_alias]["id"] for r in rows],
            }
        )
    sources = {
        "Hotel": "inventory.read_inventory",
        "RoomOffer": "inventory.read_inventory",
        "ChildPolicy": "policies.read_policies",
    }
    eligible = []
    for row in rows:
        eligible.append(
            {
                "offer_id": row[program.root_alias]["id"],
                "total_cents": calculate(program.total_cents, row, request),
                "evidence": [
                    f"{sources[kind]}:{kind}/{row[alias]['id']}" for alias, kind in aliases.items()
                ],
                "relations": [
                    [row[t.source_alias]["id"], t.relation, row[t.target_alias]["id"]]
                    for t in program.traversals
                ],
            }
        )
    return {
        "status": "complete",
        "eligible": sorted(eligible, key=lambda r: r["offer_id"]),
        "operator_trace": trace,
        "owl": "schema_validated",
    }


def load_cases():
    return json.loads(Path(__file__).with_name("cases.json").read_text())


def evaluate(candidate: Candidate, cases: list[dict]):
    failures = []
    for case in cases:
        result = reason(
            candidate,
            Query.model_validate_json(json.dumps(case["query"])),
            Inventory.model_validate_json(json.dumps(case["inventory"])),
            Policies.model_validate_json(json.dumps(case["policies"])),
        )
        actual = {r["offer_id"]: r["total_cents"] for r in result["eligible"]}
        if result["status"] != "complete" or actual != case["expected"]:
            failures.append(
                {
                    "case": case["name"],
                    "expected": case["expected"],
                    "actual": actual,
                    "status": result["status"],
                }
            )
    return failures
