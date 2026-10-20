"""Local-only OWB01 viewer and serialized worker launcher."""
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from core import ROOT, DATA, Records

app = FastAPI(title='Ontology Workbench', docs_url=None, redoc_url=None)
from public_records import PublishedRecords
records = Records() if os.environ.get('OWB_ENABLE_LIVE') == '1' else PublishedRecords()
lock = threading.Lock()
worker = None


@app.middleware('http')
async def local_boundary(request, call_next):
    # Loopback only, no CORS. Reject cross-site writes and DNS-rebinding hostnames.
    host = request.headers.get('host', '').split(':')[0]
    if host not in {'localhost','127.0.0.1'}:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Loopback host required'}, status_code=403)
    if request.method not in {'GET','HEAD'}:
        origin = request.headers.get('origin')
        if origin and origin not in {'http://'+request.headers['host']}:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Same-origin request required'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/')
def index():
    if not getattr(records,'read_only',False):
        text=(ROOT/'index.html').read_text().replace('<script>', '<script>window.OWB_ALLOW_LIVE=true;</script><script>',1)
        return HTMLResponse(text)
    return FileResponse(ROOT/'index.html')


@app.get('/api/sessions')
def sessions():
    groups = {}
    for event in records.events():
        if event['session'].startswith('preflight-'):
            continue
        row = groups.setdefault(event['session'], {'id':event['session'],'created':event['created'],
                                                    'status':'running','success':None})
        if event['kind'] in {'session_started','construction_resumed'}:
            row['status']='running'
        if event['kind'] == 'session_finished':
            row.update(event['payload'])
        if event['kind']=='attempt_reclassified':
            row.update(event['payload'])
    return list(reversed(list(groups.values())))


@app.get('/api/events')
def events(session: str, after: int = 0):
    return [e for e in records.events(session) if e['seq'] > after]


@app.get('/api/status')
def status():
    return {'provider':'Vertex', 'model':'gemini-2.5-flash', 'task':'22cc237_1',
            'owl_reasoner':'unavailable', 'cost_usd':None,
            'worker_running':worker is not None and worker.poll() is None,
            'runtime_exists':Path(sys.executable).exists()}


@app.get('/api/comparison')
def comparison():
    from comparison import build
    return build(records.events())


@app.post('/api/run')
def start():
    global worker
    with lock:
        if getattr(records, 'read_only', False):
            raise HTTPException(403, 'Published evidence is read-only. Set OWB_ENABLE_LIVE=1 and configure an isolated records directory for explicit live work.')
        if worker is not None and worker.poll() is None:
            raise HTTPException(409, 'A worker is already running')
        history = sessions()
        if any(s['status'] == 'conclusive' for s in history):
            raise HTTPException(409, 'This training attempt is conclusive. Review its evidence. A new protocol or candidate is required for a new comparison.')
        if any(s['status'] == 'running' for s in history):
            raise HTTPException(409, 'An existing session is still running. Inspect it before starting another worker.')
        ident = 'run-'+uuid.uuid4().hex[:12]
        log = open(DATA/(ident+'.log'), 'w')
        worker = subprocess.Popen([sys.executable,str(ROOT/'engine.py'),ident], cwd=ROOT,
                                  stdout=log, stderr=subprocess.STDOUT)
        log.close()
        return {'session':ident}


class Guidance(BaseModel):
    session: str
    target: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=5000)
    evidence_event_id: str | None = None


@app.post('/api/guidance')
def guidance(item: Guidance):
    if getattr(records, 'read_only', False):
        raise HTTPException(403, 'Published evidence is read-only')
    history = records.events(item.session)
    if not history:
        raise HTTPException(404, 'Unknown session')
    if item.evidence_event_id and item.evidence_event_id not in {e['id'] for e in history}:
        raise HTTPException(400, 'Evidence event does not belong to this session')
    active = [e['payload']['candidate_id'] for e in history if e['kind']=='candidate_activated']
    ident = records.add(item.session, 'human_guidance', {**item.model_dump(),
        'target_candidate_id':active[-1] if active else None,
        'scope':'next candidate proposal only', 'status':'recorded, not activated',
        'active_version_changed':False, 'model_output':'not-a-model'})
    return {'id':ident,'status':'recorded, not activated'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('OWB_PORT','8766')))
