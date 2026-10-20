"""Not-a-model publication mechanics, using explicit synthetic fixtures only."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from publication import sanitize,projection,load_events
from public_records import PublishedRecords
import server


def fixture(kind,payload):
    return {'seq':1,'id':'software-fixture','session':'software-fixture','kind':kind,'created':0,'payload':{'model_output':'not-a-model',**payload}}


def test_default_publication_store_is_read_only_and_cannot_dispatch(monkeypatch):
    monkeypatch.setattr(server,'records',PublishedRecords())
    with TestClient(server.app,base_url='http://127.0.0.1') as client:
        assert client.get('/api/sessions').status_code==200
        assert client.post('/api/run').status_code==403
        assert client.post('/api/guidance',json={'session':'software-fixture','target':'schema','text':'fixture'}).status_code==403


def test_publication_preserves_all_registered_outcomes_and_exclusions():
    with TestClient(server.app,base_url='http://127.0.0.1') as client:
        c=client.get('/api/comparison').json()
    assert [r['checks_passed'] for r in c['runs']]==[1,3,1,4]
    assert c['counts']=={'planned':4,'native_attempts':6,'conclusive':4,'inconclusive':2,'missing':0,'excluded':2}
    assert c['runs'][-1]['committed_effects']==3
    assert c['runs'][-1]['required_function_execution_counts']=={'onto_reconcile':1,'onto_outstanding_shares':1,'onto_request_plan':1}


def test_known_authentication_value_removed_across_quoted_code_and_observation():
    # Fake secret in software data, never an actual provider or AppWorld credential.
    sample='synthetic-auth-fixture-72903'
    events=[fixture('native_evidence',{'result':{'access_token':sample},'quoted_code':f"send(access_token='{sample}')"})]
    output,report=sanitize(events)
    assert sample not in json.dumps(output)
    assert 'REDACTED_AUTH' in json.dumps(output)
    assert events[0]['payload']['result']['access_token']==sample


def test_private_grader_fields_are_removed_without_changing_score():
    e=fixture('official_evaluation',{'grade':{'success':False,'num_tests':2,'passes':[{}],
       'failures':[{'expected':'private-answer-fixture','trace':'private-assertion-fixture'}]}})
    out,_=sanitize([e]);g=out[0]['payload']['grade']
    assert (g['success'],g['num_tests'],len(g['passes']),len(g['failures']))==(False,2,1,1)
    assert 'private-answer-fixture' not in json.dumps(out)
    assert 'private-assertion-fixture' not in json.dumps(out)


def test_contaminated_post_task_reviewer_content_is_withheld():
    e=fixture('model_requested',{'purpose':'feedback-review-v1','messages':[{'content':'private-grader-fixture'}]})
    out,_=sanitize([e]);assert 'private-grader-fixture' not in json.dumps(out)


def test_unknown_public_event_content_defaults_to_withheld():
    # No actual protected task text is used in this fixture.
    e=fixture('unrecognized_kind',{'danger':'protected-source-fixture'})
    out=projection([e]);assert 'protected-source-fixture' not in json.dumps(out)
    assert out[0]['id']==e['id'] and out[0]['kind']==e['kind']


def test_native_task_record_is_withheld_from_plaintext_publication():
    e=fixture('task',{'task_id':'fixture_1','instruction':'protected-source-fixture'})
    assert 'protected-source-fixture' not in json.dumps(projection([e]))


def test_actor_messages_are_not_exposed_by_plaintext_projection():
    e=fixture('model_requested',{'purpose':'agent-action','messages':[{'content':'protected-context-fixture'}]})
    assert 'protected-context-fixture' not in json.dumps(projection([e]))


def test_publication_has_no_database_or_decrypted_task_files():
    repo=Path(__file__).resolve().parents[2]
    assert not list((repo/'evidence').glob('*.sqlite'))
    assert not list((repo/'experiments/appworld-ontology').glob('*.sqlite'))


def test_paper_files_match_manifest_and_nonredistributable_papers_are_links():
    repo=Path(__file__).resolve().parents[2]
    import hashlib
    entries=json.loads((repo/'papers/catalog.json').read_text())
    assert len(entries)==11
    for p in entries:
        if p.get('file'):
            assert 'creativecommons.org/licenses/' in p['license_url']
            assert hashlib.sha256((repo/'papers'/p['file']).read_bytes()).hexdigest()==p['sha256']
        elif 'arxiv.org/licenses/nonexclusive' in p.get('license_url',''):
            assert p['distribution'].startswith('official-link-only')
