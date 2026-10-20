"""Not-a-model tests of local write boundaries, against an isolated temporary SQLite store."""
import pytest
from fastapi.testclient import TestClient
import core
import server


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    store=core.Records()
    monkeypatch.setattr(server,'records',store)
    with TestClient(server.app,base_url='http://127.0.0.1') as client:
        yield client,store
    store.db.close()


def test_guidance_is_bound_to_candidate_and_never_activates_it(client):
    client,store=client
    store.add('mechanics-fixture','session_started',{'model_output':'not-a-model'})
    source=store.add('mechanics-fixture','candidate_activated',{'candidate_id':'fixture-v1','model_output':'not-a-model'})
    response=client.post('/api/guidance',json={'session':'mechanics-fixture','target':'schema',
        'text':'Software-owned endpoint test only','evidence_event_id':source})
    assert response.status_code==200
    saved=store.events('mechanics-fixture')[-1]
    assert saved['kind']=='human_guidance'
    assert saved['payload']['target_candidate_id']=='fixture-v1'
    assert saved['payload']['active_version_changed'] is False
    assert saved['payload']['status']=='recorded, not activated'


def test_guidance_cannot_cite_another_session(client):
    client,store=client
    store.add('a','session_started',{'model_output':'not-a-model'})
    other=store.add('b','session_started',{'model_output':'not-a-model'})
    response=client.post('/api/guidance',json={'session':'a','target':'schema','text':'mechanical fixture','evidence_event_id':other})
    assert response.status_code==400
    assert len(store.events('a'))==1


def test_reject_cross_origin_write(client):
    client,store=client
    assert client.post('/api/run',headers={'Origin':'https://example.org'}).status_code==403
    assert store.events()==[]


def test_completed_attempt_cannot_be_rerolled_from_ui(client):
    client,store=client
    store.add('a','session_finished',{'status':'conclusive','success':False,'model_output':'not-a-model'})
    assert client.post('/api/run').status_code==409


def test_resume_supersedes_earlier_terminal_status_without_erasing_it(client):
    client,store=client
    store.add('a','session_finished',{'status':'construction_rejected','model_output':'not-a-model'})
    store.add('a','construction_resumed',{'model_output':'not-a-model'})
    assert client.get('/api/sessions').json()[0]['status']=='running'
    assert len(store.events('a'))==2


def test_explicit_supporting_fault_exclusion_is_visible_without_deleting_grade(client):
    client,store=client
    store.add('a','session_finished',{'status':'conclusive','success':False,'model_output':'not-a-model'})
    store.add('a','attempt_reclassified',{'status':'inconclusive','excluded':True,'reason':'software adapter defect'})
    row=client.get('/api/sessions').json()[0]
    assert row['status']=='inconclusive' and row['excluded'] is True
    assert row['success'] is False
    assert len(store.events('a'))==2
