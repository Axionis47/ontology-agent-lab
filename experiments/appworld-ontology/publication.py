"""Publication-only projections. Never calls a model or modifies a source ledger."""
import copy
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from comparison import build

NOTICE='Detail is retained in the encrypted, sanitized trace bundle. No new model call.'
AUTH_KEYS={'access_token','refresh_token','password','api_key','client_secret','authorization','cookie','secret_key'}
AUTH_PATTERN=re.compile(r'''(?ix)["']?(?:[a-z_]*password|access_token|refresh_token|api_key|client_secret|authorization)["']?\s*[:=]\s*["']([^"'\r\n]+)["']''')
JWT=re.compile(r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b')


def sha(value):
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def load_events(path):
    db=sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        return [{**dict(row),'payload':json.loads(row['payload'])} for row in db.execute('SELECT * FROM events ORDER BY seq')]
    finally:
        db.close()


def secret_values(events):
    found=set()
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k.lower() in AUTH_KEYS and isinstance(v,str) and len(v)>5:
                    found.add(v)
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
        elif isinstance(x,str):
            found.update(m[1] for m in AUTH_PATTERN.finditer(x) if len(m[1])>5)
            found.update(JWT.findall(x))
            try:
                parsed=json.loads(x)
                if isinstance(parsed,(dict,list)):walk(parsed)
            except (ValueError,TypeError):pass
    walk(events)
    # These describe schemas or variables rather than credentials.
    return {v for v in found if v.lower() not in {'string','password','access_token','refresh_token','bearer','fixture-token','software-probe'} and not any(c in v for c in ['\n','(',')'])}


def sanitize(events):
    secrets=secret_values(events)
    changes=Counter()
    def clean(x,key=''):
        if isinstance(x,dict):
            return {k:('[REDACTED_AUTH]' if k.lower() in AUTH_KEYS and isinstance(v,(str,int)) else clean(v,k)) for k,v in x.items()}
        if isinstance(x,list):return [clean(v,key) for v in x]
        if not isinstance(x,str):return x
        out=x
        for token in sorted(secrets,key=len,reverse=True):
            if token in out:
                out=out.replace(token,'[REDACTED_AUTH]');changes['authentication_value_occurrences']+=1
        out=JWT.sub('[REDACTED_AUTH]',out)
        out=AUTH_PATTERN.sub(lambda m:m[0].replace(m[1],'[REDACTED_AUTH]'),out)
        newer=re.sub(r'/(?:Users|home)/[^/\s\"\']+', '[LOCAL_HOME]', out)
        newer=re.sub(r'/(?:private/)?tmp/', '[LOCAL_TMP]/', newer)
        if newer!=out:changes['local_configuration_occurrences']+=1
        out=newer
        return out
    out=clean(copy.deepcopy(events))
    for e in out:
        p=e['payload'];kind=e['kind']
        if kind=='official_evaluation':
            g=p['grade'];p['grade']={**{k:g[k] for k in ['success','num_tests']},
                'passes':[{'label':'official-check','requirement':'Passed official check; private evaluator details withheld.'} for _ in g['passes']],
                'failures':[{'label':'official-check','requirement':'Failed official check; private evaluator details withheld.'} for _ in g['failures']]}
            changes['private_grader_payloads_withheld']+=1
        if kind in {'model_requested','model_completed'} and p.get('purpose','') in {'feedback-review-v1','post-v2-review'}:
            p.pop('messages',None);p.pop('output',None);p['publication_note']='Post-task reviewer content withheld because historical v1 review saw private assertions.'
            changes['post_task_reviewer_payloads_withheld']+=1
        if kind=='repair_proposed':
            p['proposal']={'publication_note':'Historical model repair text withheld with post-task private-grader context; proposal was not activated.'}
            changes['post_task_reviewer_payloads_withheld']+=1
    serialized=json.dumps(out,ensure_ascii=False)
    assert all(t not in serialized for t in secrets if len(t)>8)
    assert not JWT.search(serialized)
    assert not re.search(r'/(?:Users|home)/[a-zA-Z0-9]',serialized)
    report={'classification':'not-a-model','source_events':len(events),'sanitized_events':len(out),
        'source_events_sha256':sha(events),'sanitized_events_sha256':sha(out),
        'redactions':dict(changes),'note':'Event identities and order retained. Authentication values and local configuration removed. Private grader details and potentially contaminated post-task reviewer payloads withheld. Detailed task-derived content remains encrypted for redistribution.'}
    return out,report


def projection(events):
    """Readable original-code/measurement metadata; no task records or trajectory text."""
    out=[]
    literal={'session_started','session_finished','construction_resumed','candidate_checks','candidate_rejected','composition_rejected','runtime_manifest','candidate_activated','world_started','functions_installed','provider_ready','software_verification','interface_variant','inconclusive_resume','attempt_reclassified','final_source_audit','enforcement_audit'}
    def obligations(rows):
        return [{'description':f'Recorded obligation {i+1}. Detailed source text is encrypted.','status':x.get('status','unknown'),'sources':[]} for i,x in enumerate(rows or [])]
    for e in events:
        p=e['payload'];k=e['kind'];q={'publication_note':NOTICE,'model_output':p.get('model_output','not-a-model')}
        q.update({x:p[x] for x in ['step','candidate_id','call_id','version','origin'] if x in p})
        if k in literal:
            q=copy.deepcopy(p)
            for field in ['error','reason','native_output']:
                if field in q:q[field]=NOTICE
        elif k=='task':q.update(task_id=p['task_id'],instruction='Reconcile a shared expense and request outstanding amounts. Benchmark task text is encrypted.',datetime='[BENCHMARK_TIME_ENCRYPTED]')
        elif k in {'model_requested','model_completed'}:
            q.update({x:p[x] for x in ['call_id','purpose','model_output','provider','requested_model','resolved_model_version','prompt_version','settings','usage','duration_s','finish_reasons','response_id','status'] if x in p})
        elif k=='candidate':q={**copy.deepcopy(p)}
        elif k in {'revision_proposed','composition_proposed'}:
            q.update({x:p[x] for x in ['round','bundle','plan'] if x in p})
        elif k=='revision_diff':q=copy.deepcopy(p)
        elif k=='action_observation':q.update(step=p['step'],duration_s=p['duration_s'],inputs=[NOTICE for _ in p['inputs']],outputs=[NOTICE for _ in p['outputs']])
        elif k=='graph_selected':
            q.update(facts=[],edges=[],gaps=[],obligations=obligations(p.get('obligations')),
                selection={**{x:p.get('selection',{}).get(x,[]) for x in ['entity_types','function_names']},'reason':'Recorded concept selection; protected task facts remain encrypted.'},
                protected_fact_count=len(p.get('facts',[])))
        elif k=='context_delivered':
            c=p['context'];q.update({x:p[x] for x in ['size_characters','selection_source','sha256'] if x in p})
            q['context']={'obligations':obligations(c.get('obligations')),'publication_note':NOTICE}
        elif k=='function_called':
            q.update(name=p['name'],capture=p.get('capture'),code_sha256=p.get('code_sha256'),args=[{'publication_note':NOTICE}],kwargs={},result={'row_count':len(p['result']) if isinstance(p.get('result'),list) else None,'publication_note':NOTICE},
                arguments_sha256=sha(p.get('args')),result_sha256=sha(p.get('result')))
        elif k=='official_evaluation':q={key:copy.deepcopy(value) for key,value in p.items() if key!='application_hashes'}
        elif k=='native_evidence':q.update(app=p['app'],api=p['api'],arguments={'page_index':p['arguments'].get('page_index')},result={'publication_note':NOTICE},result_sha256=sha(p.get('result')))
        elif k=='native_api_calls':q.update(sha256=p['sha256'],call_count=len(p['calls']))
        elif k=='gate_denied':
            reason=p.get('reason','')
            q['reason']='Raw writes blocked; exact ontology receipt chain required.' if reason.startswith('Raw payment') else 'Evidence, proposal, receipt or execution contract denied. Exact diagnostic is encrypted.'
        elif k=='gate_probe':q.update(injected_by='software, not the model',denied_before_native_request=p['denied_before_native_request'],native_state_unchanged=p['native_state_unchanged'])
        elif k=='gate_receipt':q.update(receipt_id=p['receipt_id'],kind=p['kind'],row_count=len(p['data']),data={'publication_note':NOTICE},source_event_ids=p['source_event_ids'],data_sha256=sha(p['data']))
        elif k=='reconciliation_evidence_verified':q.update({x:p[x] for x in ['source_ids','share_count','history_complete']});q['matched_payment_count']=len(p.get('matched_payment_ids',[]))
        elif k in {'gate_allowed','effect_committed'}:
            q.update({x:p[x] for x in ['plan_receipt','app','api'] if x in p});q['arguments']={'sha256':sha(p['arguments']),'publication_note':NOTICE}
            if k=='effect_committed':q['native_receipt']={'observed':True,'publication_note':NOTICE}
        elif k in {'plan_commit_started','plan_committed'}:q.update({x:p[x] for x in ['plan_receipt','effect_count'] if x in p})
        elif k=='grounding_review':q.update(judge_status='Historical grounding review, task details encrypted',review={'unsupported_claims':[{'publication_note':NOTICE} for _ in p['review']['unsupported_claims']]})
        elif k=='repair_proposed':q.update(active_version=p['active_version'],status=p['status'],proposal=p['proposal'])
        # Every event remains present, including withheld reviewer/extraction content.
        out.append({**{x:e[x] for x in ['seq','id','session','kind','created']},'payload':q})
    # Projection must preserve the measured comparison, not silently alter outcomes.
    a,b=build(events),build(out)
    assert a['counts']==b['counts']
    for x,y in zip(a['runs'],b['runs']):
        for field in ['session','version','success','checks_passed','checks_failed','steps','state_reconciled','function_returns_retained','gate_denials','committed_effects']:
            assert x[field]==y[field],field
    return out


def render(events,template,public=False):
    groups={}
    for e in events:
        if e['session'].startswith('preflight-'):continue
        row=groups.setdefault(e['session'],{'id':e['session'],'status':'running'})
        if e['kind'] in {'session_started','construction_resumed'}:row['status']='running'
        if e['kind'] in {'session_finished','attempt_reclassified'}:row.update(e['payload'])
    if not public:
        template=template.replace('Published historical evidence. The public view preserves measurement metadata and ontology definitions. Protected task facts, actor messages and detailed receipts are withheld here. Use scripts/open_detailed_evidence.py to inspect the encrypted sanitized traces locally. No new model calls occur when viewing.', 'Locally decrypted historical evidence. Authentication, private paths and private grader content were redacted. Do not publish this decrypted HTML or task-data screenshots. Viewing does not run a model.')
    data={'sessions':list(reversed(list(groups.values()))),'events':events,'comparison':build(events),'read_only':True,'public_projection':public}
    script='<script>window.OWB_EVIDENCE='+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+';</script>'
    return template.replace('<script>',script+'\n<script>',1)
