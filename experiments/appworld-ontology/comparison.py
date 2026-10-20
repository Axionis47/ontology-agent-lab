"""Read-only derivation of the registered historical version comparisons."""
from core import Records,digest

V1='run-dinner-002'


def summarize(events,session,version):
    rows=[e for e in events if e['session']==session]
    def last(kind):
        matches=[e['payload'] for e in rows if e['kind']==kind]
        return matches[-1] if matches else None
    activation=last('candidate_activated')
    candidate=next((e['payload']['candidate'] for e in reversed(rows) if e['kind']=='candidate'
                    and (not activation or e['payload']['candidate_id']==activation['candidate_id'])),None)
    evaluation=last('official_evaluation')
    grade=evaluation['grade'] if evaluation else None
    finish=last('session_finished')
    reclassification=last('attempt_reclassified')
    world=last('world_started')
    calls=[e['payload'] for e in rows if e['kind']=='model_completed']
    actors=[c for c in calls if c['purpose']=='agent-action-v1']
    contexts=[e['payload']['context'] for e in rows if e['kind']=='context_delivered']
    return {'session':session,'version':version,'status':reclassification['status'] if reclassification else finish['status'] if finish else ('running' if rows else 'not started'),
        'evaluation_eligible':not bool(reclassification and reclassification.get('excluded')),
        'exclusion_reason':reclassification.get('reason') if reclassification else None,
        'success':grade['success'] if grade else None,'checks_passed':len(grade['passes']) if grade else None,
        'checks_failed':len(grade['failures']) if grade else None,'checks_total':grade['num_tests'] if grade else None,
        'state_reconciled':evaluation.get('matches_executed_state') if evaluation else None,
        'initial_state_hash':world['initial_state_hash'] if world else None,
        'steps':sum(e['kind']=='action_observation' for e in rows),'candidate':candidate,
        'candidate_id':activation['candidate_id'] if activation else None,
        'types':len(candidate['entities']) if candidate else None,'relations':len(candidate['relations']) if candidate else None,
        'context_policy':last('revision_diff').get('context_policy') if last('revision_diff') else None,
        'final_context_obligations':contexts[-1].get('obligations') if contexts else None,
        'engineering_review':last('engineering_review'),
        'function_returns_retained':sum(e['kind']=='function_called' for e in rows),
        'function_capture':'stdout only; incomplete on exceptions' if version==1 else 'host-bound frozen function execution' if version>=3 else 'separate native wrapper ledger',
        'gate_denials':sum(e['kind']=='gate_denied' and e['payload'].get('origin')=='model-action' for e in rows) if version>=3 else None,
        'injected_gate_denials':sum(e['kind']=='gate_denied' and e['payload'].get('origin')=='software-native-probe' for e in rows) if version>=3 else None,
        'committed_effects':sum(e['kind']=='effect_committed' for e in rows) if version>=3 else None,
        'plan_committed':any(e['kind']=='plan_committed' for e in rows) if version>=3 else None,
        'required_function_execution_counts':{name:sum(e['kind']=='function_called' and e['payload']['name']==name for e in rows)
            for name in ['onto_reconcile','onto_outstanding_shares','onto_request_plan']} if version>=3 else None,
        'extraction_rejections':sum(e['kind']=='extraction_rejected' for e in rows),
        'unsupported_claims_withheld':sum(len(e['payload']['review']['unsupported_claims']) for e in rows if e['kind']=='grounding_review') if version==2 else None,
        'api_error_steps':sum(e['kind']=='action_observation' and any('Execution failed' in s for s in e['payload']['outputs']) for e in rows),
        'actor_model_versions':sorted({c['resolved_model_version'] for c in actors}),
        'model_calls':len(calls),'model_time_s':sum(c['duration_s'] for c in calls),
        'tool_time_s':sum(e['payload']['duration_s'] for e in rows if e['kind']=='action_observation'),
        'grading_time_s':evaluation.get('duration_s') if evaluation else None,
        'input_tokens':sum(c['usage'].get('prompt_token_count') or 0 for c in calls),
        'output_tokens':sum((c['usage'].get('candidates_token_count') or 0)+(c['usage'].get('thoughts_token_count') or 0) for c in calls),
        'cost_usd':None,'diff':last('revision_diff'),'error':finish.get('error') if finish else None}


def structural_diff(old,new):
    if not old or not new:
        return []
    before={e['name']:e for e in old['entities']};after={e['name']:e for e in new['entities']}
    changes=[]
    for name in sorted(set(before)|set(after)):
        if name not in before:
            changes.append({'target':'type '+name,'change':'added','before':None,'after':after[name]})
        elif name not in after:
            changes.append({'target':'type '+name,'change':'removed','before':before[name],'after':None})
        elif before[name]!=after[name]:
            changes.append({'target':'type '+name,'change':'modified','before':before[name],'after':after[name]})
    for label,key,identity in [('relation','relations','name'),('function','functions','name')]:
        a={i[identity]:i for i in old[key]};b={i[identity]:i for i in new[key]}
        for name in sorted(set(a)|set(b)):
            if a.get(name)!=b.get(name):
                changes.append({'target':label+' '+name,'change':'added' if name not in a else 'removed' if name not in b else 'modified',
                                'before':a.get(name),'after':b.get(name)})
    return changes


def build(events=None):
    events=events if events is not None else Records().events()
    v2_ids=list(dict.fromkeys(e['session'] for e in events if e['session'].startswith('run-dinner-v2-') and e['kind']=='session_started'))
    selected=v2_ids[-1] if v2_ids else 'run-dinner-v2-001'
    runs=[summarize(events,V1,1),summarize(events,selected,2)]
    attempts=[summarize(events,V1,1)]+[summarize(events,ident,2) for ident in v2_ids]
    v3_ids=list(dict.fromkeys(e['session'] for e in events if e['session'].startswith('run-dinner-v3-') and e['kind']=='session_started'))
    if v3_ids:
        runs.append(summarize(events,v3_ids[-1],3))
        attempts.extend(summarize(events,ident,3) for ident in v3_ids)
    v3p1_ids=list(dict.fromkeys(e['session'] for e in events if e['session'].startswith('run-dinner-v3p1-') and e['kind']=='session_started'))
    if v3p1_ids:
        runs.append(summarize(events,v3p1_ids[-1],3.1))
        attempts.extend(summarize(events,ident,3.1) for ident in v3p1_ids)
    old,new=runs[-2:]
    initial_equal=len({r['initial_state_hash'] for r in runs})==1 if all(r['initial_state_hash'] for r in runs) else None
    completed=all(r['evaluation_eligible'] and r['success'] is not None and r['state_reconciled'] for r in runs) and initial_equal is True
    improved=(not old['success'] and new['success']) if completed else None
    checks_delta=new['checks_passed']-old['checks_passed'] if completed else None
    return {'runs':runs,'result':('Initial state mismatch; outcomes are not comparable.' if initial_equal is False else
        f"V{new['version']} passed where v{old['version']} failed on this training case." if improved else
        f"V{new['version']} passed more checks, but overall task success still failed on this training case." if completed and checks_delta>0 else
        f"V{new['version']} did not improve overall task success on this training case." if completed else f"V{new['version']} evaluation pending or inconclusive."),
        'observed_task_improvement':improved,'check_pass_delta':checks_delta,'same_initial_state':initial_equal,
        'structural_changes':structural_diff(old['candidate'],new['candidate']),
        'diff_pair':{'before':old['version'],'after':new['version']},
        'comparisons':[{'before':a['version'],'after':b['version'],'structural_changes':structural_diff(a['candidate'],b['candidate']),
                        'revision':b['diff']} for a,b in zip(runs,runs[1:])],
        'counts':{'planned':len(runs),'native_attempts':sum(r['initial_state_hash'] is not None for r in attempts),
                  'conclusive':sum(r['status']=='conclusive' for r in runs),
                  'inconclusive':sum(r['status']=='inconclusive' for r in attempts),
                  'missing':sum(r['success'] is None for r in runs),
                  'excluded':sum(r['status']=='inconclusive' for r in attempts)},
        'attempt_history':[{k:r[k] for k in ['session','version','status','steps','success','error','model_calls','candidate_id','evaluation_eligible','exclusion_reason']} for r in attempts],
        'v2_package_unchanged_across_attempts':len({r['candidate_id'] for r in attempts if r['version']==2 and r['candidate_id']})<=1,
        'claim_limit':'Historical, sequential comparison on one seen training task. Schema, functions, context and enforcement design change together. No ontology-only causal or general improvement claim.',
        'function_count_limit':'V1 stdout, v2 wrapper-ledger and v3 host-bound execution counts use different capture mechanisms.',
        'model_output':'not-a-model'}


if __name__=='__main__':
    from core import encode
    print(encode(build()))
