"""User-authorized feedback repair and ONE v2 native AppWorld attempt."""
import json
import sys
from core import ROOT,SOURCE_DATA,Records,Vertex,Inconclusive,configure_world,digest,encode,elapsed
from contracts import compile_plan,check_candidate,OPERATORS,BUILTINS
from revision_contracts import RepairBundle
from engine import ask,solve,ConstructionRejected,TASK_ID
from manifest import capture

PARENT='run-dinner-002'
SESSION='run-dinner-v2-001'


def sources(records):
    history=records.events(PARENT)
    active=next(e for e in reversed(history) if e['kind']=='candidate_activated')
    candidate=next(e for e in history if e['kind']=='candidate' and e['payload']['candidate_id']==active['payload']['candidate_id'])
    rejection=next(e for e in history if e['kind']=='extraction_rejected' and e['payload']['step']==7)
    observation=next(e for e in history if e['kind']=='action_observation' and e['payload']['step']==12)
    inspection=next(e for e in history if e['kind']=='engineering_review')
    feedback=[{'event_id':rejection['id'],'boundary':'extraction',
        'observation':rejection['payload']['error'].split('\n')[0],
        'diagnosis':'Payment status was unknown before transaction evidence. A required field rejected supported partial shares.'},
        {'event_id':observation['id'],'boundary':'API contract','observation':observation['payload']['outputs'][0],
         'diagnosis':'The actor used an unsupported argument, then gave up instead of finding identity evidence.'},
        {'event_id':inspection['id'],'boundary':'semantic grounding',
         'observation':'A share-amount quote was used to justify paid=false, without a transaction search. The schema had no relationships.',
         'diagnosis':'Preserve unknown status, cite properties individually, track unresolved identity and reconciliation obligations.'}]
    guidance=[{'event_id':e['id'],'target':e['payload']['target'],'text':e['payload']['text']}
              for e in history if e['kind']=='human_guidance']
    docs={}
    wanted={'venmo':['create_payment_request','show_transactions','search_users','show_profile'],
            'phone':['search_contacts','show_contact','get_current_date_and_time'],
            'simple_note':['search_notes','show_note']}
    for app,names in wanted.items():
        raw=json.loads((SOURCE_DATA/'api_docs/standard'/f'{app}.json').read_text())
        docs[app]={n:{k:v for k,v in raw[n].items() if k!='canary_string'} for n in names if n in raw}
    reset=next(e['payload']['initial_state_hash'] for e in history if e['kind']=='world_started')
    return {'parent_session':PARENT,'parent_candidate_id':active['payload']['candidate_id'],
            'parent_candidate':candidate['payload']['candidate'],'failure_evidence':feedback,
            'human_guidance':guidance,'public_api_contracts':docs},reset


def check_bundle(bundle,candidate):
    checks=check_candidate(candidate)
    entities={e.name:e for e in candidate.entities}
    if not candidate.relations:
        raise ValueError('Repair must represent meaningful typed relationships, not only a flat record')
    share=entities[bundle.share_type]
    status=next(p for p in share.properties if p.name==bundle.status_property)
    if status.required or status.type!='string':
        raise ValueError('Payment status must be an optional string property; missing means unknown')
    if bundle.unpaid_value==bundle.paid_value:
        raise ValueError('Paid and unpaid status labels must differ')
    function=next(f for f in candidate.functions if f.name==bundle.outstanding_function)
    # Independent not-a-model mechanics oracle. These are fixture rows, not task data or model substitutes.
    namespace={}
    exec(OPERATORS,namespace)
    exec(function.code,namespace)
    key=share.primary_key
    fixtures=[{'id':'fixture_unknown','type':share.name,'properties':{key:'fixture-unknown'}},
              {'id':'fixture_paid','type':share.name,'properties':{key:'fixture-paid',status.name:bundle.paid_value}},
              {'id':'fixture_unpaid','type':share.name,'properties':{key:'fixture-unpaid',status.name:bundle.unpaid_value}}]
    result=namespace[function.name](fixtures)
    if result!=[fixtures[2]['properties']]:
        raise ValueError('Outstanding-share function must select verified unpaid, excluding missing and paid statuses')
    if namespace[function.name]([])!=[]:
        raise ValueError('No observed shares must return an empty result')
    return {**checks,'unknown_paid_unpaid_mechanics':'passed','empty_graph_mechanics':'passed',
            'fixtures':'not-a-model, independently authored, no native task records',
            'partial_fact_contract':'primary key required; other action requirements remain visible as missing'}


def construct(vertex,records,session,task,source):
    instruction=('Repair the previous failed domain assistance package. Return a complete JSON object matching '
        +encode(RepairBundle.model_json_schema())+
        '\nThe only data here are schema, source-linked failure diagnoses, and public API docs. Do not put actual task answers,'
        ' people, identifiers, amounts, credentials or executable API action plans into the package.'
        ' Represent identities, individual shares and observed payments separately with meaningful typed relationships.'
        ' A share payment-status property must be OPTIONAL STRING. Omitted means unknown, never unpaid.'
        ' Only actual complete transaction reconciliation can establish unpaid. Include properties for stable identity and email.'
        ' Missing required action information must remain visible without rejecting supported partial observations.'
        ' Functions are general pure single expressions over facts. At least one named onto_outstanding_shares(facts)'
        ' returns the property dictionaries of shares explicitly marked with your unpaid_value; it must exclude missing or paid statuses.'
        ' Add useful identity and amount lookup functions if needed. No raw text parsing, API calls, imports or side effects.'
        ' Expression calls only these operators and len,str,float,int,bool,abs,round,min,max,sum,sorted or dict .get.'
        ' Prefer nested operator calls, no generator lambdas. First parameter facts.'
        '\nContext policy must keep unresolved identity, payment reconciliation and API-contract obligations visible.'
        ' Require native API specification lookup before application calls, all pages of relevant searches,'
        ' correct current date and full day boundaries for yesterday, transaction direction and matching event.'
        ' Match coworker names against phone contact identities, corroborate email, and reconcile incoming payments'
        ' before requesting only outstanding shares with the task-specified description. Never infer missing data.'
        ' Include change explanations citing ONLY supplied failure/human guidance event IDs. Do not change the task contract.'
        '\nPure operators:\n'+OPERATORS)
    data={'task':task.instruction,**source}
    records.add(session,'repair_sources',{'source':data,'sha256':digest(data),
        'expected_answers_included':False,'private_ground_truth_loaded':False,'model_output':'not-a-model'})
    allowed={f['event_id'] for f in source['failure_evidence']+source['human_guidance']}
    for round_ in range(1,6):
        raw,call=ask(vertex,'repair-package-v2',instruction,data)
        records.add(session,'revision_proposed',{'round':round_,'call_id':call,'bundle':raw})
        try:
            bundle=RepairBundle.model_validate(raw)
            if any(not set(c.evidence_event_ids)<=allowed for c in bundle.changes):
                raise ValueError('Change cites an unknown failure or guidance event')
            candidate=compile_plan(bundle.kernel)
            checks=check_bundle(bundle,candidate)
        except Exception as exc:
            records.add(session,'revision_rejected',{'round':round_,'error':str(exc)[:1500],'model_output':'not-a-model'})
            data={'task':task.instruction,**source,'rejected_bundle':raw,'validator_error':str(exc)[:1500]}
            continue
        identity=digest({'candidate':candidate.model_dump(),'context_policy':bundle.context_policy.model_dump()})
        records.add(session,'candidate',{'candidate_id':identity,'parent_candidate_id':source['parent_candidate_id'],
            'version':2,'call_id':call,'candidate':candidate.model_dump(),'policy':'feedback-revised-assistance-v2',
            'code_origin':'mechanically compiled live model operator expressions'})
        records.add(session,'candidate_checks',{'candidate_id':identity,'version':2,**checks})
        records.add(session,'revision_diff',{'parent_session':PARENT,'parent_candidate_id':source['parent_candidate_id'],
            'candidate_id':identity,'changes':[c.model_dump() for c in bundle.changes],
            'context_policy':bundle.context_policy.model_dump(),'model_output':'not-a-model'})
        records.add(session,'candidate_activated',{'candidate_id':identity,'parent_candidate_id':source['parent_candidate_id'],
            'version':2,'scope':'ONE user-authorized changed-candidate training attempt',
            'package_sha256':identity,'context_policy_sha256':digest(bundle.context_policy.model_dump()),'model_output':'not-a-model'})
        return candidate,identity,bundle
    raise ConstructionRejected('V2 construction rejected after five recorded rounds; no AppWorld attempt')


def main(resume_inconclusive=False):
    session='run-dinner-v2-002' if resume_inconclusive else SESSION
    configure_world()
    records=Records()
    if records.events(session):
        raise RuntimeError('V2 identity already exists. Inspect it; never silently repeat this registered attempt.')
    prior=records.events(SESSION)
    if resume_inconclusive:
        finish=next(e['payload'] for e in reversed(prior) if e['kind']=='session_finished')
        if finish['status']!='inconclusive' or any(e['kind']=='official_evaluation' for e in prior):
            raise RuntimeError('Resume is allowed only for the missing/inconclusive cell, never a conclusive failure')
    source,reset=sources(records)
    records.add(session,'session_started',{'task_id':TASK_ID,'phase':'feedback-recovery-demonstration','status':'running',
        'protocol':'OWB02-v1','parent_session':PARENT,'package_version':2,'model_output':'not-a-model',
        'measurement_claim':'one seen training task; not a controlled causal comparison'})
    capture(records,session)
    start=elapsed()
    try:
        from appworld.task import Task
        task=Task.load(task_id=TASK_ID,load_ground_truth=False)
        records.add(session,'task',{'task_id':TASK_ID,'instruction':task.instruction,'datetime':str(task.datetime),
            'input_spec_sha256':digest((SOURCE_DATA/'tasks'/TASK_ID/'specs.json').read_bytes()),'model_output':'not-a-model'})
        vertex=Vertex(records,session)
        ready,call=ask(vertex,'preflight-v2','Return only JSON {"ready":true}.',{'check':'live provider readiness'})
        if ready!={'ready':True}:
            raise Inconclusive('Live provider readiness response invalid')
        records.add(session,'provider_ready',{'call_id':call,'model_output':'not-a-model'})
        records.add(session,'requirements',{'requirements':[task.instruction], 'source':'official task unchanged','model_output':'not-a-model'})
        if resume_inconclusive:
            activation=next(e['payload'] for e in reversed(prior) if e['kind']=='candidate_activated')
            stored=next(e['payload'] for e in reversed(prior) if e['kind']=='candidate')
            original_bundle=next(e['payload']['bundle'] for e in reversed(prior) if e['kind']=='revision_proposed')
            bundle=RepairBundle.model_validate(original_bundle)
            candidate=compile_plan(bundle.kernel)
            identity=digest({'candidate':candidate.model_dump(),'context_policy':bundle.context_policy.model_dump()})
            if identity!=activation['candidate_id'] or candidate.model_dump()!=stored['candidate']:
                raise Inconclusive('Frozen package identity changed; cannot resume this cell')
            records.add(session,'inconclusive_resume',{'prior_session':SESSION,'prior_error':finish['error'],
                'candidate_id':identity,'package_changed':False,'model_output':'not-a-model',
                'package_input_classification':'cached-live; unchanged frozen live-generated package',
                'scope':'fresh-state retry of inconclusive cell after context wire-error handling fix'})
            records.add(session,'candidate',{**stored,'model_output':'cached-live'})
            checks=check_bundle(bundle,candidate)
            records.add(session,'candidate_checks',{'candidate_id':identity,'version':2,**checks})
            diff=next(e['payload'] for e in reversed(prior) if e['kind']=='revision_diff')
            records.add(session,'revision_diff',diff)
            records.add(session,'candidate_activated',activation)
        else:
            candidate,identity,bundle=construct(vertex,records,session,task,source)
        evaluation,state=solve(vertex,records,session,task,candidate,identity,bundle.context_policy,reset)
        # Feedback uses public trace and score only, with expected assertion values excluded.
        history=[{'event_id':e['id'],'kind':e['kind'],'payload':e['payload']} for e in records.events(session)
                 if e['kind'] in {'extraction_rejected','grounding_review','action_observation','function_called'}]
        proposal,call=ask(vertex,'post-v2-review',
            'Review the completed training task. Return JSON {"change_needed":boolean,"summary":string,'
            '"changes":[{"target":string,"operation":string,"patch":string,"reason":string,"evidence_event_ids":[string]}],'
            '"regression_checks":[string]}. Use visible sources, not task answers. This is a proposal, not an activated v3.',
            {'candidate':candidate.model_dump(),'context_policy':bundle.context_policy.model_dump(),
             'task_success':evaluation['grade']['success'],'history':history})
        records.add(session,'repair_proposed',{'call_id':call,'candidate_id':identity,'active_version':2,
            'status':'post-v2 proposal, not activated','proposal':proposal})
        records.add(session,'session_finished',{'status':'conclusive','success':evaluation['grade']['success'],
            'package_version':2,'parent_session':PARENT,'steps':state['steps'],'function_calls':state['function_calls'],
            'duration_s':elapsed()-start,'model_output':'not-a-model','cost_usd':None,
            'comparison':'historical v1 vs changed v2 on one seen training task; not causal proof'})
    except Exception as exc:
        records.add(session,'session_finished',{'status':'construction_rejected' if isinstance(exc,ConstructionRejected) else 'inconclusive',
            'success':None,'error_type':type(exc).__name__,'error':str(exc)[:1800],
            'duration_s':elapsed()-start,'model_output':'not-a-model'})
        raise
    print(encode({'session':session,'success':evaluation['grade']['success'],'steps':state['steps']}),flush=True)


if __name__=='__main__':
    main('--resume-inconclusive' in sys.argv)
