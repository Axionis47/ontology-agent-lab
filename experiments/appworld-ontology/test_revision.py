"""Not-a-model checks of OWB02 partial facts and evidence filtering. No provider substitutes."""
import pytest
from contracts import Candidate,Citation
from revision_contracts import RevisedExtraction,GroundingReview,check_revised,withhold_claims


def candidate():
    return Candidate.model_validate({'name':'mechanics-only','entities':[{'name':'Share','description':'fixture',
        'primary_key':'id','properties':[{'name':'id','type':'string','required':True,'description':'identity'},
        {'name':'paid','type':'boolean','required':True,'description':'completion requirement, not invented evidence'}]}],
        'relations':[],'competency_questions':[],'functions':[{'name':'onto_rows','description':'fixture',
        'code':'def onto_rows(facts):\n    return op_entities(facts, "Share")'}]})


def extraction():
    source=[{'source_id':'obs','quote':'fixture-one'}]
    return RevisedExtraction.model_validate({'facts':[{'id':'share1','type':'Share','properties':{'id':'fixture-one'},
        'sources':source,'property_sources':{'id':source}}],'edges':[],
        'selection':{'entity_types':['Share'],'function_names':['onto_rows'],'reason':'mechanics fixture'},
        'gaps':['paid unknown'],'obligations':[{'description':'Check payment evidence','status':'unresolved','sources':[]}]})


def test_partial_fact_is_kept_without_inventing_required_status():
    raw=extraction()
    result=check_revised(raw,candidate(),{'obs':'fixture-one'})
    assert result['partial_observations']=='retained'
    assert 'paid' not in raw.facts[0].properties


def test_each_asserted_property_requires_own_source():
    raw=extraction();raw.facts[0].properties['paid']=False
    with pytest.raises(ValueError,match='Every asserted property'):
        check_revised(raw,candidate(),{'obs':'fixture-one'})


def test_unsupported_status_can_be_withheld_without_losing_identity():
    raw=extraction();raw.facts[0].properties['paid']=False
    raw.facts[0].property_sources['paid']=raw.facts[0].sources
    critique=GroundingReview.model_validate({'unsupported_claims':[{'fact_id':'share1','property':'paid',
        'reason':'Fixture identity does not establish payment status'}],'reopened_obligations':['Payment status unknown'],
        'summary':'Software mechanics fixture, not a model judge result'})
    admitted=withhold_claims(raw,critique,candidate())
    assert admitted.facts[0].properties=={'id':'fixture-one'}
    check_revised(admitted,candidate(),{'obs':'fixture-one'})


def test_reviewer_cannot_remove_a_property_that_does_not_exist():
    critique=GroundingReview.model_validate({'unsupported_claims':[{'fact_id':'share1','property':'missing',
        'reason':'invalid fixture reference'}],'reopened_obligations':[],'summary':'mechanics'})
    with pytest.raises(ValueError,match='absent property'):
        withhold_claims(extraction(),critique,candidate())


def test_satisfied_obligation_needs_observable_evidence():
    raw=extraction();raw.obligations[0].status='satisfied'
    with pytest.raises(ValueError,match='Satisfied obligation'):
        check_revised(raw,candidate(),{'obs':'fixture-one'})


def test_property_quote_must_exist_in_source():
    raw=extraction();raw.facts[0].property_sources['id']=[Citation(source_id='obs',quote='not observed')]
    # Revalidate assignment into typed citation list because model contracts are validated on entry.
    raw=RevisedExtraction.model_validate(raw.model_dump())
    with pytest.raises(ValueError,match='Property citation'):
        check_revised(raw,candidate(),{'obs':'fixture-one'})
