"""Small OWB01 wire contracts and explicit, limited code checks."""
import ast
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Property(Strict):
    name: str
    type: Literal['string', 'number', 'integer', 'boolean', 'array', 'object']
    required: bool
    description: str


class Entity(Strict):
    name: str
    description: str
    primary_key: str
    properties: list[Property]


class Relation(Strict):
    name: str
    from_type: str
    to_type: str
    description: str


class Function(Strict):
    name: str
    description: str
    code: str


class Candidate(Strict):
    name: str
    entities: list[Entity] = Field(min_length=1)
    relations: list[Relation]
    competency_questions: list[str]
    functions: list[Function] = Field(min_length=1)


class FunctionPlan(Strict):
    name: str
    description: str
    parameters: list[str]
    expression: str


class KernelPlan(Strict):
    name: str
    entities: list[Entity] = Field(min_length=1)
    relations: list[Relation]
    competency_questions: list[str]
    functions: list[FunctionPlan] = Field(min_length=1)


def compile_plan(plan):
    functions = []
    for function in plan.functions:
        if not re.fullmatch(r'[a-z][a-z0-9_]*',function.name):
            raise ValueError('Invalid function identifier')
        name = function.name if function.name.startswith('onto_') else 'onto_'+function.name
        if not function.parameters or function.parameters[0] != 'facts':
            raise ValueError('First parameter must be facts')
        if len(set(function.parameters)) != len(function.parameters):
            raise ValueError('Duplicate parameter')
        if not all(re.fullmatch(r'[a-z][a-z0-9_]*',p) for p in function.parameters):
            raise ValueError('Invalid parameter name')
        expression = ast.parse(function.expression,mode='eval')
        class JsonLiterals(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in {'true','false','null'}:
                    return ast.copy_location(ast.Constant({'true':True,'false':False,'null':None}[node.id]),node)
                return node
        expression = ast.fix_missing_locations(JsonLiterals().visit(expression))
        # Expressions only, no invented Python statement rewriting.
        code = 'def '+name+'('+', '.join(function.parameters)+'):\n    return '+ast.unparse(expression)+'\n'
        compiled = Function(name=name,description=function.description,code=code)
        check_code(compiled)
        functions.append(compiled)
    raw = plan.model_dump(exclude={'functions'})
    return Candidate(**raw, functions=functions)


OPS = {'op_entities', 'op_where', 'op_values', 'op_sum', 'op_difference', 'op_lookup'}
BUILTINS = {'len', 'str', 'float', 'int', 'bool', 'abs', 'round', 'min', 'max', 'sum', 'sorted'}


def check_code(function):
    tree = ast.parse(function.code)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('One function definition required')
    definition = tree.body[0]
    if definition.name != function.name or not re.fullmatch(r'onto_[a-z0-9_]+', function.name):
        raise ValueError('Function names must start onto_ and match their definition')
    if definition.decorator_list or definition.returns or any(a.annotation for a in definition.args.args):
        raise ValueError('No decorators or annotations')
    if definition.args.defaults or definition.args.kw_defaults:
        raise ValueError('No argument defaults')
    if not definition.args.args or definition.args.args[0].arg != 'facts':
        raise ValueError('First parameter must be facts')
    if definition.args.vararg or definition.args.kwarg or definition.args.kwonlyargs or definition.args.posonlyargs:
        raise ValueError('Only plain named arguments are allowed')
    local_names = {a.arg for a in definition.args.args} | {
        n.id for n in ast.walk(definition) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    forbidden = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Lambda, ast.Global,
                 ast.Nonlocal, ast.With, ast.Try, ast.While, ast.Delete, ast.Raise,
                 ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom, ast.AugAssign)
    for node in ast.walk(tree):
        if isinstance(node, forbidden):
            raise ValueError('Forbidden syntax: '+type(node).__name__)
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError('Private names forbidden')
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id not in local_names | OPS | BUILTINS:
            raise ValueError('Global name outside pure vocabulary: '+node.id)
        if isinstance(node,ast.FunctionDef) and node is not definition:
            raise ValueError('Nested functions forbidden')
        if isinstance(node,(ast.Subscript,ast.Attribute)) and isinstance(node.ctx,ast.Store):
            raise ValueError('Mutation of argument objects forbidden')
        if isinstance(node, ast.Attribute) and node.attr != 'get':
            raise ValueError('Only dictionary .get attribute is allowed')
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in OPS | BUILTINS:
                    raise ValueError('Call outside pure operator vocabulary: '+node.func.id)
            elif not isinstance(node.func, ast.Attribute) or node.func.attr != 'get':
                raise ValueError('Indirect call forbidden')
    compile(tree, '<generated-ontology-function>', 'exec')


def check_candidate(candidate):
    names = [e.name for e in candidate.entities]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate entity type')
    for entity in candidate.entities:
        properties = [p.name for p in entity.properties]
        if len(properties) != len(set(properties)) or entity.primary_key not in properties:
            raise ValueError('Invalid properties or missing primary key: '+entity.name)
    rels = [r.name for r in candidate.relations]
    if len(rels) != len(set(rels)):
        raise ValueError('Duplicate relation name')
    for rel in candidate.relations:
        if rel.from_type not in names or rel.to_type not in names:
            raise ValueError('Unknown relation endpoint')
    if len({f.name for f in candidate.functions}) != len(candidate.functions):
        raise ValueError('Duplicate function name')
    for function in candidate.functions:
        check_code(function)
    return {'wire_contract': 'passed', 'references': 'passed', 'code_syntax_and_vocabulary': 'passed',
            'semantic_correctness': 'unproven', 'owl_hermit': 'unavailable: Java runtime missing',
            'function_correctness': 'unproven; inspect actual inputs and outputs',
            'model_output': 'not-a-model'}


class Citation(Strict):
    source_id: str
    quote: str = Field(min_length=1)


class Fact(Strict):
    id: str
    type: str
    properties: dict[str, Any]
    sources: list[Citation] = Field(min_length=1)


class Edge(Strict):
    relation: str
    from_id: str
    to_id: str
    sources: list[Citation] = Field(min_length=1)


class Selection(Strict):
    entity_types: list[str]
    function_names: list[str]
    reason: str


class Extraction(Strict):
    facts: list[Fact]
    edges: list[Edge]
    selection: Selection
    gaps: list[str]


def check_extraction(extraction, candidate, sources, allow_partial=False):
    import jsonschema
    entities = {e.name: e for e in candidate.entities}
    if not set(extraction.selection.entity_types) <= set(entities):
        raise ValueError('Selected unknown entity type')
    if not set(extraction.selection.function_names) <= {f.name for f in candidate.functions}:
        raise ValueError('Selected unknown function')
    ids = {}
    identities = set()
    for fact in extraction.facts:
        if fact.id in ids:
            raise ValueError('Duplicate fact identity')
        entity = entities[fact.type]
        schema = {'type':'object', 'properties':{p.name:{'type':p.type} for p in entity.properties},
                  'required':([entity.primary_key] if allow_partial else sorted({p.name for p in entity.properties if p.required} | {entity.primary_key})),
                  'additionalProperties':False}
        jsonschema.validate(fact.properties, schema)
        import json
        identity = (fact.type,json.dumps(fact.properties[entity.primary_key],sort_keys=True))
        if identity in identities:
            raise ValueError('Duplicate typed primary key')
        identities.add(identity)
        ids[fact.id] = fact.type
    relations = {r.name:r for r in candidate.relations}
    for edge in extraction.edges:
        relation = relations[edge.relation]
        if ids.get(edge.from_id) != relation.from_type or ids.get(edge.to_id) != relation.to_type:
            raise ValueError('Fact edge has invalid endpoints')
    for item in [*extraction.facts, *extraction.edges]:
        for citation in item.sources:
            if citation.source_id not in sources or citation.quote not in sources[citation.source_id]:
                raise ValueError('Citation not found in public source')
    return {'shape_check':'passed', 'citation_substrings':'passed',
            'truth_of_extraction':'unproven; source matching does not establish semantic truth',
            'model_output':'not-a-model'}


OPERATORS = '''
def op_entities(facts, entity_type):
    return [f['properties'] for f in facts if f['type'] == entity_type]
def op_where(rows, key, value):
    return [r for r in rows if r.get(key) == value]
def op_values(rows, key):
    return [r.get(key) for r in rows]
def op_sum(values):
    return sum(values)
def op_difference(left, right):
    return left - right
def op_lookup(rows, key, value):
    return next((r for r in rows if r.get(key) == value), None)
'''


def runtime_code(candidate):
    # Trusted wrappers expose real calls in the normal AppWorld observation stream.
    code = 'import json\n_owb_function_calls = []\n' + OPERATORS
    for function in candidate.functions:
        code += '\n'+function.code+'\n'
        code += f'''_original_{function.name} = {function.name}
def {function.name}(*args, **kwargs):
    result = _original_{function.name}(*args, **kwargs)
    _owb_function_calls.append({{'name': {function.name!r}, 'args': args, 'kwargs': kwargs, 'result': result}})
    print('OWB_FUNCTION:' + json.dumps(_owb_function_calls[-1], default=str))
    return result
'''
    return code
