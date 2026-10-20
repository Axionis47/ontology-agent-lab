"""Capture actual runtime and source identities, with explicit capture timing."""
import importlib.metadata
import platform
import subprocess
from core import ROOT, UPSTREAM, SOURCE_DATA, Records, digest


def capture(records, session, timing='before construction'):
    packages=['appworld','appworld-agents','google-genai','pydantic','jsonschema','fastapi','uvicorn','SQLAlchemy']
    payload={'capture_timing':timing,'python':platform.python_version(),
        'packages':{p:importlib.metadata.version(p) for p in packages},
        'upstream_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=UPSTREAM,text=True).strip(),
        'upstream_files':{p:digest((UPSTREAM/p).read_bytes()) for p in [
            'experiments/code/simplified/agent.py','experiments/code/simplified/react_code_agent.py',
            'experiments/prompts/react_code_agent/instructions.txt']},
        'local_files':{p.name:digest(p.read_bytes()) for p in ROOT.iterdir() if p.suffix=='.py'},
        'input_spec_sha256':digest((SOURCE_DATA/'tasks/22cc237_1/specs.json').read_bytes()),
        'model_output':'not-a-model'}
    records.add(session,'runtime_manifest',payload)
    return payload


if __name__=='__main__':
    capture(Records(),'run-dinner-002','after demonstration; development revisions occurred during this run, not a frozen comparison')
