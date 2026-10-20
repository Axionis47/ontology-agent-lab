"""Not-a-model derivation checks. Fixture grades are software inputs, not AppWorld evidence."""
from comparison import build,V1


def fixture(session,success=None,status='conclusive',initial='same'):
    rows=[{'session':session,'kind':'session_started','payload':{}},
          {'session':session,'kind':'world_started','payload':{'initial_state_hash':initial}}]
    if success is not None:
        passed=4 if success else 1
        rows.append({'session':session,'kind':'official_evaluation','payload':{
            'matches_executed_state':True,'grade':{'success':success,'num_tests':4,
            'passes':[{}]*passed,'failures':[{}]*(4-passed)}}})
    rows.append({'session':session,'kind':'session_finished','payload':{'status':status,'error':None}})
    return rows


def test_missing_v2_is_not_reported_as_failure_or_improvement():
    c=build(fixture(V1,False))
    assert c['observed_task_improvement'] is None
    assert c['counts']['missing']==1


def test_observed_gain_requires_official_result_and_same_reset():
    c=build(fixture(V1,False)+fixture('run-dinner-v2-001',True))
    assert c['observed_task_improvement'] is True
    assert c['check_pass_delta']==3


def test_no_overall_gain_when_v2_also_fails():
    c=build(fixture(V1,False)+fixture('run-dinner-v2-001',False))
    assert c['observed_task_improvement'] is False


def test_inconclusive_attempt_is_visible_and_latest_attempt_is_selected():
    c=build(fixture(V1,False)+fixture('run-dinner-v2-001',None,'inconclusive')+
            fixture('run-dinner-v2-002',True))
    assert c['counts']['inconclusive']==1 and c['counts']['excluded']==1
    assert c['counts']['native_attempts']==3
    assert c['runs'][1]['session']=='run-dinner-v2-002'
    assert len(c['attempt_history'])==3


def test_changed_inputs_cannot_establish_an_improvement():
    c=build(fixture(V1,False)+fixture('run-dinner-v2-001',True,initial='different'))
    assert c['same_initial_state'] is False
    assert c['observed_task_improvement'] is None
    assert 'not comparable' in c['result']


def test_v3_is_a_separate_version_with_adjacent_artifact_comparisons():
    c=build(fixture(V1,False)+fixture('run-dinner-v2-002',False)+fixture('run-dinner-v3-001',True))
    assert len(c['runs'])==3
    assert c['counts']['planned']==3
    assert c['observed_task_improvement'] is True
    assert c['diff_pair']=={'before':2,'after':3}
    assert [(p['before'],p['after']) for p in c['comparisons']]==[(1,2),(2,3)]


def test_controller_fault_exclusion_preserves_raw_official_grade():
    events=fixture(V1,False)+fixture('run-dinner-v2-002',False)+fixture('run-dinner-v3-001',False)
    events.append({'session':'run-dinner-v3-001','kind':'attempt_reclassified','payload':{
        'status':'inconclusive','excluded':True,'reason':'mechanics fixture controller defect'}})
    c=build(events)
    assert c['runs'][-1]['success'] is False
    assert c['runs'][-1]['evaluation_eligible'] is False
    assert c['runs'][-1]['status']=='inconclusive'
    assert c['counts']['excluded']==1
    assert c['observed_task_improvement'] is None


def test_receipt_interface_variant_keeps_the_conclusive_v3_failure_visible():
    events=fixture(V1,False)+fixture('run-dinner-v2-002',False)+fixture('run-dinner-v3-002',False)+fixture('run-dinner-v3p1-001',True)
    c=build(events)
    assert [r['version'] for r in c['runs']]==[1,2,3,3.1]
    assert c['runs'][2]['success'] is False and c['runs'][3]['success'] is True
    assert c['counts']['planned']==4
    assert c['diff_pair']=={'before':3,'after':3.1}
