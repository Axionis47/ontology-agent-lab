"""Typed declarations for generated graph operations. No generated code is evaluated."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,47}$")]


class Declaration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Expression(Declaration):
    op: Literal["field", "input", "constant", "add", "multiply"]
    name: str | None = None
    value: Literal[0, 1] | None = None
    args: tuple["Expression", ...] = Field(default=(), max_length=2)


class Traversal(Declaration):
    source_alias: Name
    relation: Name
    target_alias: Name


class Predicate(Declaration):
    left: Expression
    compare: Literal["eq", "le", "ge"]
    right: Expression


class Program(Declaration):
    root_type: Name
    root_alias: Name
    traversals: tuple[Traversal, ...] = Field(max_length=4)
    filters: tuple[Predicate, ...] = Field(max_length=10)
    total_cents: Expression


def expression_type(expression, aliases, fields, inputs, depth=0):
    if depth > 6:
        raise ValueError("An expression exceeds the maximum depth of six.")
    if expression.op in {"field", "input"}:
        if not expression.name or expression.args or expression.value is not None:
            raise ValueError("A field or input expression requires only a name.")
        if expression.op == "input":
            if expression.name not in inputs:
                raise ValueError(f"Unknown request field: {expression.name}")
            return inputs[expression.name]
        parts = expression.name.split(".")
        if len(parts) != 2 or parts[0] not in aliases:
            raise ValueError(f"Unknown field reference: {expression.name}")
        entity_fields = fields[aliases[parts[0]]]
        if parts[1] not in entity_fields:
            raise ValueError(f"Unknown source field: {expression.name}")
        return entity_fields[parts[1]]
    if expression.op == "constant":
        if expression.value is None or expression.name is not None or expression.args:
            raise ValueError("A constant requires only value 0 or 1.")
        return "integer"
    if expression.name is not None or expression.value is not None or len(expression.args) != 2:
        raise ValueError("Arithmetic requires exactly two argument expressions.")
    for item in expression.args:
        if expression_type(item, aliases, fields, inputs, depth + 1) != "integer":
            raise ValueError("Arithmetic operands must be integers.")
    return "integer"


def validate_program(program, relations, fields, inputs):
    if program.root_type not in fields:
        raise ValueError("The root type is not declared by the source contract.")
    aliases = {program.root_alias: program.root_type}
    for traversal in program.traversals:
        relation = relations.get(traversal.relation)
        if relation is None or aliases.get(traversal.source_alias) != relation.source:
            raise ValueError("A traversal must start at its relation's declared source type.")
        if traversal.target_alias in aliases:
            raise ValueError("A traversal must introduce a new alias.")
        aliases[traversal.target_alias] = relation.target
    for predicate in program.filters:
        left = expression_type(predicate.left, aliases, fields, inputs)
        right = expression_type(predicate.right, aliases, fields, inputs)
        if left != right or (predicate.compare != "eq" and left != "integer"):
            raise ValueError("A comparison must use compatible types.")
    if expression_type(program.total_cents, aliases, fields, inputs) != "integer":
        raise ValueError("The total cost must have integer type.")


def calculate(expression, row, request):
    if expression.op == "field":
        alias, field = expression.name.split(".")
        return row[alias][field]
    if expression.op == "input":
        return request[expression.name]
    if expression.op == "constant":
        return expression.value
    left, right = (calculate(arg, row, request) for arg in expression.args)
    return left + right if expression.op == "add" else left * right


def matches(predicate, row, request):
    left = calculate(predicate.left, row, request)
    right = calculate(predicate.right, row, request)
    if predicate.compare == "eq":
        return left == right
    return left <= right if predicate.compare == "le" else left >= right
