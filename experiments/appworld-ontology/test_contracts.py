"""Not-a-model tests: contract rejection and mechanical source/identity checks only."""
import pytest
from contracts import Candidate, Extraction, Function, KernelPlan, compile_plan, check_code, check_candidate, check_extraction


def candidate():
    return Candidate.model_validate({'name':'contract-fixture', 'entities':[{
        'name':'Record', 'description':'Unit fixture', 'primary_key':'id',
        'properties':[{'name':'id','type':'string','required':True,'description':'identity'}]}],
        'relations':[], 'competency_questions':[], 'functions':[{'name':'onto_records',
        'description':'select fixture records','code':'def onto_records(facts):\n    return op_entities(facts, "Record")'}]})


@pytest.mark.parametrize('body',[
    'import os\ndef onto_bad(facts):\n    return 1',
    'def onto_bad(facts):\n    return open("secret")',
    'def onto_bad(facts):\n    return apis',
    'def onto_bad(facts):\n    return facts.__class__',
    'def onto_bad(facts):\n    facts[0] = 1\n    return facts',
    'def onto_bad(facts):\n    facts += [1]\n    return facts',
    'def onto_bad(facts):\n    return facts.append(1)',
    'def onto_bad(facts):\n    def hidden():\n        return 1\n    return 1',
    'def onto_bad(facts=open("secret")):\n    return 1',
])
def test_reject_external_capabilities_and_mutation(body):
    with pytest.raises((ValueError,SyntaxError)):
        check_code(Function(name='onto_bad',description='contract fixture',code=body))


def test_compose_pure_operator_and_keep_semantics_unproven():
    checked=check_candidate(candidate())
    assert checked['references']=='passed'
    assert checked['semantic_correctness']=='unproven'
    assert checked['owl_hermit'].startswith('unavailable')


def extraction():
    return {'facts':[{'id':'r1','type':'Record','properties':{'id':'one'},
            'sources':[{'source_id':'obs1','quote':'one'}]}], 'edges':[],
            'selection':{'entity_types':['Record'],'function_names':['onto_records'],'reason':'test fixture'},'gaps':[]}


def test_valid_citation_is_not_semantic_proof():
    check=check_extraction(Extraction.model_validate(extraction()),candidate(),{'obs1':'record one'})
    assert check['citation_substrings']=='passed'
    assert check['truth_of_extraction'].startswith('unproven')


def test_reject_fabricated_citation():
    with pytest.raises(ValueError, match='Citation'):
        check_extraction(Extraction.model_validate(extraction()),candidate(),{'obs1':'different record'})


def test_reject_duplicate_typed_identity():
    raw=extraction(); raw['facts'].append({**raw['facts'][0],'id':'r2'})
    with pytest.raises(ValueError, match='Duplicate typed'):
        check_extraction(Extraction.model_validate(raw),candidate(),{'obs1':'record one'})


def test_reject_unknown_selection():
    raw=extraction();raw['selection']['entity_types']=['unknown']
    with pytest.raises(ValueError, match='Selected unknown'):
        check_extraction(Extraction.model_validate(raw),candidate(),{'obs1':'record one'})


def test_reject_relation_with_unknown_endpoint():
    raw=candidate().model_dump();raw['relations']=[{'name':'links','from_type':'Record','to_type':'Missing','description':'invalid'}]
    with pytest.raises(ValueError, match='Unknown relation'):
        check_candidate(Candidate.model_validate(raw))


def test_expression_compiler_translates_json_literals_without_rewriting_domain_logic():
    raw=candidate().model_dump()
    raw['functions']=[{'name':'records','description':'fixture','parameters':['facts'],
                      'expression':'op_where(op_entities(facts, "Record"), "active", false)'}]
    compiled=compile_plan(KernelPlan.model_validate(raw))
    assert compiled.functions[0].code == 'def onto_records(facts):\n    return op_where(op_entities(facts, \'Record\'), \'active\', False)\n'
