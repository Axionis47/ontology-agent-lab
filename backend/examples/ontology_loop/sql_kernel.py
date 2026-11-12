"""Compile a validated ontology function into live SQLite views.

The database contains source records and a local reservation table.
An existing SQLite MCP server can expose it without a custom MCP server.
"""

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .kernel import Candidate, Inventory, Policies, Query, validate_candidate

TABLES = {"Hotel": "hotel", "RoomOffer": "offer", "ChildPolicy": "policy"}
SOURCE_FIELDS = {
    "hotel": ("id", "city", "policy_id"),
    "offer": ("id", "hotel_id", "capacity", "nightly_cents", "fee_cents"),
    "policy": ("id", "minimum_child_age"),
    "request": ("city", "nights", "adults", "child_age", "budget_cents"),
}

SCHEMA = """
CREATE TABLE hotel (id TEXT NOT NULL, city TEXT NOT NULL, policy_id TEXT);
CREATE TABLE offer (
    id TEXT NOT NULL, hotel_id TEXT NOT NULL, capacity INTEGER NOT NULL,
    nightly_cents INTEGER NOT NULL, fee_cents INTEGER NOT NULL
);
CREATE TABLE policy (id TEXT NOT NULL, minimum_child_age INTEGER NOT NULL);
CREATE TABLE request (
    city TEXT NOT NULL, nights INTEGER NOT NULL, adults INTEGER NOT NULL,
    child_age INTEGER NOT NULL, budget_cents INTEGER NOT NULL
);
CREATE TABLE reservations (
    reservation_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL
);
"""


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("A SQL identifier contains unsupported characters.")
    return f'"{value}"'


def _text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _expression(expression, aliases):
    if expression.op == "input":
        return f"q.{_identifier(expression.name)}"
    if expression.op == "field":
        alias, field = expression.name.split(".")
        return f"{aliases[alias]}.{_identifier(field)}"
    if expression.op == "constant":
        return str(expression.value)
    left, right = (_expression(item, aliases) for item in expression.args)
    operator = {"add": "+", "multiply": "*"}[expression.op]
    return f"({left} {operator} {right})"


@lru_cache(maxsize=32)
def _compile_validated(candidate_json: str) -> str:
    candidate = Candidate.model_validate_json(candidate_json)
    validate_candidate(candidate)
    program = candidate.program
    relations = {item.name: item for item in candidate.relations}
    aliases = {program.root_alias: "n0"}
    types = {program.root_alias: program.root_type}
    joins = []
    missing = []
    relation_evidence = []
    root = f"(SELECT DISTINCT * FROM {_identifier(TABLES[program.root_type])}) AS n0"
    for index, traversal in enumerate(program.traversals, start=1):
        relation = relations[traversal.relation]
        source, target = aliases[traversal.source_alias], f"n{index}"
        aliases[traversal.target_alias] = target
        types[traversal.target_alias] = relation.target
        target_table = _identifier(TABLES[relation.target])
        joins.append(
            f"LEFT JOIN (SELECT DISTINCT * FROM {target_table}) AS {target} "
            f"ON {source}.{_identifier(relation.source_field)} = {target}.id"
        )
        missing.append(f"{target}.id IS NULL")
        relation_evidence.append(
            "json_object("
            f"'source_type', {_text(relation.source)}, 'source', {source}.id, "
            f"'relation', {_text(relation.name)}, "
            f"'target_type', {_text(relation.target)}, 'target', {target}.id)"
        )
    joined = "\n".join([root, *joins])
    conflicts = " OR ".join(
        "EXISTS (SELECT 1 FROM "
        f"(SELECT DISTINCT * FROM {_identifier(table)}) "
        "GROUP BY id HAVING COUNT(*) > 1)"
        for table in TABLES.values()
    )
    absent = f"EXISTS (SELECT 1 FROM {joined} WHERE {' OR '.join(missing)})" if missing else "0"
    conditions = ["(SELECT status FROM snapshot_status) = 'complete'"]
    for predicate in program.filters:
        operator = {"eq": "IS", "le": "<=", "ge": ">="}[predicate.compare]
        conditions.append(
            f"({_expression(predicate.left, aliases)} {operator} "
            f"{_expression(predicate.right, aliases)})"
        )
    evidence = [
        "json_object("
        f"'type', {_text(kind)}, 'id', {aliases[alias]}.id, "
        f"'source_table', {_text(TABLES[kind])})"
        for alias, kind in types.items()
    ]
    cost = _expression(program.total_cents, aliases)
    return (
        "CREATE VIEW snapshot_status AS\n"
        "SELECT CASE WHEN has_conflicting_records OR has_missing_links "
        "THEN 'incomplete' ELSE 'complete' END AS status,\n"
        "has_conflicting_records, has_missing_links\n"
        f"FROM (SELECT ({conflicts}) AS has_conflicting_records,\n"
        f"({absent}) AS has_missing_links);\n"
        "CREATE VIEW eligible_stays AS\n"
        f"SELECT DISTINCT n0.id AS offer_id, {cost} AS total_cents,\n"
        f"json_array({', '.join(evidence)}) AS evidence_json,\n"
        f"json_array({', '.join(relation_evidence)}) AS relations_json\n"
        f"FROM {joined}\nCROSS JOIN request AS q\n"
        f"WHERE {' AND '.join(conditions)};\n"
    )


def compile_views(candidate: Candidate) -> str:
    """Validate OWL and compile only declared relations and typed operations."""
    return _compile_validated(candidate.model_dump_json())


def prepare_database(case: dict, candidate: Candidate | None, path: Path | str) -> dict:
    """Create one database. Preserve duplicate raw records for conflict checks."""
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError(f"The episode database already exists: {path}")
    request = Query.model_validate_json(json.dumps(case["query"]))
    inventory = Inventory.model_validate_json(json.dumps(case["inventory"]))
    policies = Policies.model_validate_json(json.dumps(case["policies"]))
    generated_sql = compile_views(candidate) if candidate is not None else ""
    records = {
        "hotel": [item.model_dump() for item in inventory.hotels],
        "offer": [item.model_dump() for item in inventory.offers],
        "policy": [item.model_dump() for item in policies.policies],
        "request": [request.model_dump()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.executescript(SCHEMA)
            for table, items in records.items():
                fields = SOURCE_FIELDS[table]
                columns = ", ".join(_identifier(field) for field in fields)
                placeholders = ", ".join("?" for _ in fields)
                connection.executemany(
                    f"INSERT INTO {_identifier(table)} ({columns}) VALUES ({placeholders})",
                    [tuple(item[field] for field in fields) for item in items],
                )
            if generated_sql:
                connection.executescript(generated_sql)
    finally:
        connection.close()
    return {
        "path": str(path),
        "tables": [*SOURCE_FIELDS, "reservations"],
        "views": ["snapshot_status", "eligible_stays"] if candidate is not None else [],
        "kernel": candidate.fingerprint if candidate is not None else None,
        "generated_sql": generated_sql,
    }
