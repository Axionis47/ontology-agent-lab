"""NOT-A-MODEL mechanics. Hand-authored functions/evidence/effect stub are unit fixtures only."""
import copy
import json
import pytest
import core
from contracts import Candidate
from enforcement import ReconciliationGate,GateDenied,check_actor_code,install_boundary,native_day
from gated_run import BRIDGE


def fixture_candidate():
    functions=[{'name':'onto_reconcile','description':'Hand-authored unit fixture, not model output',
     'code':"def onto_reconcile(facts):\n    return [{'email':s.get('email'),'share_amount':s.get('amount'),'paid_amount':round(sum(p.get('amount') for p in op_entities(facts,'Payment') if p.get('email')==s.get('email')),2),'outstanding':round(max(0,s.get('amount')-sum(p.get('amount') for p in op_entities(facts,'Payment') if p.get('email')==s.get('email'))),2)} for s in op_entities(facts,'Share')]"},
     {'name':'onto_outstanding_shares','description':'Hand-authored unit fixture',
      'code':"def onto_outstanding_shares(facts):\n    return [r for r in op_entities(facts,'ReconciledShare') if r.get('outstanding')>0]"},
     {'name':'onto_request_plan','description':'Hand-authored unit fixture',
      'code':"def onto_request_plan(facts,description):\n    return [{'user_email':r.get('email'),'amount':r.get('outstanding'),'description':description} for r in op_entities(facts,'OutstandingShare')]"}]
    return Candidate.model_validate({'name':'software-fixture','entities':[{'name':n,'description':'Unit fixture',
        'primary_key':c['primary_key'],'properties':[{'name':k,'type':v,'required':True,'description':'Unit fixture'} for k,v in c['properties'].items()]} for n,c in BRIDGE.items()],
        'relations':[{'name':'has_payment','from_type':'Share','to_type':'Payment','description':'Unit fixture'}],
        'competency_questions':[],'functions':functions})


@pytest.fixture
def gate(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    records=core.Records()
    gate=ReconciliationGate(records,'mechanics-only',fixture_candidate(),'not-a-model','owner@example.invalid','Fixture dinner')
    gate.origin='software-fixture'
    yield gate
    records.db.close()


def evidence(gate,complete=True):
    gate.observe('phone','get_current_date_and_time',{}, {'date':'2031-02-04','time':'12:00:00'})
    gate.observe('simple_note','show_note',{'note_id':1},{'note_id':1,'title':'Dinner at Fixture Cafe',
        'content':'# Fixture shares\n- Avery => $30\n- Blair => $45\n- Casey => $12'})
    contacts=[{'first_name':n,'last_name':'Fixture','email':e} for n,e in
              [('Avery','a@example.invalid'),('Blair','b@example.invalid'),('Casey','c@example.invalid')]]
    for app,api in [('phone','search_contacts'),('venmo','search_users')]:
        gate.observe(app,api,{'page_index':0,'query':''},contacts)
        gate.observe(app,api,{'page_index':1,'query':''},[])
    tx=[{'transaction_id':101,'sender':{'email':'a@example.invalid'},'receiver':{'email':'owner@example.invalid'},
         'amount':10,'description':'Fixture Cafe dinner','created_at':'2031-02-03T20:00:00'},
        {'transaction_id':102,'sender':{'email':'b@example.invalid'},'receiver':{'email':'owner@example.invalid'},
         'amount':50,'description':'Fixture Cafe dinner','created_at':'2031-02-03T21:00:00'}]
    args={'direction':'received','min_created_at':'2031-02-03','max_created_at':'2031-02-03','page_index':0}
    gate.observe('venmo','show_transactions',args,tx)
    if complete:
        gate.observe('venmo','show_transactions',{**args,'page_index':1},[])
    return {'note_id':1,'event_day':'2031-02-03','event_label':'Fixture Cafe','transaction_ids':[101,102],
            'shares':[{'name':n,'email':e,'amount':a,'line_quote':q} for n,e,a,q in
            [('Avery','a@example.invalid',30,'- Avery => $30'),('Blair','b@example.invalid',45,'- Blair => $45'),('Casey','c@example.invalid',12,'- Casey => $12')]]}


def plan(gate,proposal):
    r=gate.onto_reconcile(proposal)
    o=gate.onto_outstanding_shares(r['receipt_id'])
    return gate.onto_request_plan(o['receipt_id'])


def test_native_evidence_and_required_functions_yield_only_outstanding(gate):
    p=plan(gate,evidence(gate))
    assert p['result']==[{'user_email':'a@example.invalid','amount':20,'description':'Fixture dinner'},
                         {'user_email':'c@example.invalid','amount':12,'description':'Fixture dinner'}]
    assert [e['payload']['name'] for e in gate.records.events('mechanics-only') if e['kind']=='function_called']==[
        'onto_reconcile','onto_outstanding_shares','onto_request_plan']


def test_native_date_adapter_accepts_actual_human_readable_and_iso_formats():
    assert str(native_day('Thursday, July 4, 2030'))=='2030-07-04'
    assert str(native_day('2030-07-04'))=='2030-07-04'
    with pytest.raises(GateDenied,match='Unsupported native current-date'):
        native_day('unrecognized fixture date')


def test_no_proof_and_raw_writes_are_denied(gate):
    with pytest.raises(GateDenied,match='Raw payment'):
        gate.before('venmo','create_payment_request',{'user_email':'a@example.invalid','amount':30},'POST')
    with pytest.raises(GateDenied,match='Missing required'):
        gate.onto_request_plan('invented-receipt')


def test_incomplete_history_cannot_be_declared_reconciled(gate):
    with pytest.raises(GateDenied,match='received-transaction search'):
        gate.onto_reconcile(evidence(gate,complete=False))


@pytest.mark.parametrize('field,value',[('min_created_at','2031-02-03T12:00:00'),('max_created_at','2031-02-03T12:00:00')])
def test_partial_day_search_cannot_support_full_reconciliation(gate,field,value):
    p=evidence(gate)
    for o in gate.observations:
        if o['api']=='show_transactions':
            o['arguments'][field]=value
    with pytest.raises(GateDenied,match='whole event day'):
        gate.onto_reconcile(p)


def test_ambiguous_coworker_payment_fails_closed(gate):
    p=evidence(gate)
    for o in gate.observations:
        if o['api']=='show_transactions' and o['result']:
            o['result'][0]['description']='Another unrelated meal'
    with pytest.raises(GateDenied,match='Ambiguous payment'):
        gate.onto_reconcile(p)


def test_omitted_already_paid_transaction_blocks(gate):
    p=evidence(gate);p['transaction_ids']=[101]
    with pytest.raises(GateDenied,match='every observed eligible'):
        gate.onto_reconcile(p)


@pytest.mark.parametrize('change,expected',[
    (lambda p:p.update(event_day='2031-02-02'),'yesterday'),
    (lambda p:p['shares'][0].update(email='forged@example.invalid'),'phone contact'),
    (lambda p:p['shares'][0].update(amount=29),'actual note row'),
    (lambda p:p['shares'].pop(),'currency row'),
    (lambda p:p.update(event_label='Unknown Cafe'),'note title')])
def test_evidence_mutations_fail_closed(gate,change,expected):
    p=evidence(gate);change(p)
    with pytest.raises(GateDenied,match=expected):
        gate.onto_reconcile(p)


def test_early_success_is_denied_but_abstention_is_available(gate):
    with pytest.raises(GateDenied,match='fully committed'):
        gate.before('supervisor','complete_task',{},'POST')
    gate.before('supervisor','complete_task',{'status':'fail'},'POST')


def test_plan_is_host_owned_and_duplicate_effects_are_denied(gate):
    p=plan(gate,evidence(gate));p['result'][0]['amount']=999
    effects=[]
    def unit_effect(app,api,**args):
        gate.before(app,api,args,'POST');effects.append(args)
        return {'payment_request_id':len(effects)}
    gate.native=unit_effect
    assert gate.commit(p['receipt_id'],'fixture-token')['committed'] is True
    assert effects[0]['amount']==20
    with pytest.raises(GateDenied,match='already been committed'):
        gate.commit(p['receipt_id'],'fixture-token')
    assert len(effects)==2


def test_new_evidence_invalidates_plan(gate):
    p=plan(gate,evidence(gate))
    gate.observe('phone','get_current_date_and_time',{}, {'date':'2031-02-04','time':'12:01:00'})
    with pytest.raises(GateDenied,match='Evidence changed'):
        gate.commit(p['receipt_id'],'fixture-token')


def test_new_envelope_interface_uses_host_receipts_without_bypassing_functions(gate):
    gate.accept_receipt_envelope=True
    r=gate.onto_reconcile(evidence(gate))
    o=gate.onto_outstanding_shares(r)
    p=gate.onto_request_plan(o)
    assert len(p['result'])==2
    calls=[]
    def unit_effect(app,api,**args):
        gate.before(app,api,args,'POST');calls.append(args)
        return {'payment_request_id':len(calls)}
    gate.native=unit_effect
    assert gate.commit(p,'fixture')['committed'] is True
    assert len(calls)==2


def test_new_envelope_interface_rejects_modified_or_raw_data(gate):
    gate.accept_receipt_envelope=True
    r=gate.onto_reconcile(evidence(gate))
    tampered=copy.deepcopy(r);tampered['result'][0]['outstanding']=999
    with pytest.raises(GateDenied,match='modified'):
        gate.onto_outstanding_shares(tampered)
    with pytest.raises(GateDenied,match='receipt_id string'):
        gate.onto_outstanding_shares(r['result'])


def test_partial_effect_exception_cannot_duplicate_prior_rows(gate):
    p=plan(gate,evidence(gate));calls=[]
    def unit_effect(app,api,**args):
        gate.before(app,api,args,'POST');calls.append(args)
        if len(calls)==2:
            raise RuntimeError('Unit transport fault, not a live failure')
        return {'payment_request_id':1}
    gate.native=unit_effect
    with pytest.raises(RuntimeError):
        gate.commit(p['receipt_id'],'fixture-token')
    with pytest.raises(GateDenied):
        gate.commit(p['receipt_id'],'fixture-token')
    assert len(calls)==2


@pytest.mark.parametrize('code',["requester._request('venmo','create_payment_request')",
    'import requests',"getattr(apis,'requester')",'ontology._gate.permit = {}',
    'def onto_reconcile(facts):\n    return []'])
def test_supported_repl_surface_blocks_known_bypasses(code):
    with pytest.raises(GateDenied):
        check_actor_code(code)


@pytest.mark.native
def test_actual_native_transport_blocks_alias_before_effect(gate):
    # Real AppWorld mechanics only. No actor/model or real-account access.
    core.configure_world()
    from appworld import AppWorld
    from grading import application_hashes
    docs={app:json.loads((core.SOURCE_DATA/'api_docs/standard'/f'{app}.json').read_text())
          for app in ['venmo','supervisor','api_docs','phone']}
    with AppWorld.initializer(update_defaults=True,experiment_name='OWB03/gate-mechanics',load_ground_truth=False,random_seed=0):
        with AppWorld(task_id='22cc237_1') as world:
            before=core.digest(application_hashes(world.models))
            install_boundary(world,gate,docs)
            count=len(world.requester.request_tracker.requests)
            result=world.execute("send = apis.venmo.create_payment_request\nsend(user_email='fixture@example.invalid',amount=1,access_token='fixture',description='fixture')")
            assert 'RECONCILIATION GATE' in result
            assert len(world.requester.request_tracker.requests)==count
            assert core.digest(application_hashes(world.models))==before
            current=world.execute("print(apis.phone.get_current_date_and_time())")
            observed=next(o for o in reversed(gate.observations) if o['api']=='get_current_date_and_time')
            assert native_day(observed['result']['date'])==world.task.datetime.date()
