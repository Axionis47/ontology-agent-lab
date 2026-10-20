"""Export existing private evidence. This is not an experiment or a model call."""
import argparse,json,sys,tempfile,hashlib
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXP=REPO/'experiments/appworld-ontology'
sys.path.insert(0,str(EXP))
from publication import load_events,sanitize,projection,render,sha
from comparison import build


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source_sqlite',type=Path)
    p.add_argument('--bundle',action='store_true',help='Requires the configured AppWorld runtime; retains protected details only in encrypted form')
    args=p.parse_args()
    original=load_events(args.source_sqlite)
    detailed,report=sanitize(original)
    public=projection(detailed)
    template=(EXP/'index.html').read_text()
    (EXP/'public-events.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
    (EXP/'evidence.html').write_text(render(public,template,public=True))
    (REPO/'evidence/comparison.json').write_text(json.dumps(build(public),ensure_ascii=False,indent=2)+'\n')
    report.update(public_events_sha256=sha(public),public_events=len(public),projection='Protected task/trajectory content withheld from plaintext. Detailed sanitized content encrypted. Event IDs and order preserved.')
    if args.bundle:
        from appworld.common.crypto import pack_bundle
        from appworld.common.constants import PASSWORD,SALT
        with tempfile.TemporaryDirectory(prefix='oal-sanitized-') as folder:
            root=Path(folder);dest=root/'detailed';dest.mkdir()
            (dest/'events.json').write_text(json.dumps(detailed,ensure_ascii=False,indent=2))
            (dest/'evidence.html').write_text(render(detailed,template))
            (dest/'comparison.json').write_text(json.dumps(build(detailed),ensure_ascii=False,indent=2))
            (dest/'sanitization.json').write_text(json.dumps(report,indent=2))
            target=REPO/'evidence/sanitized-traces.bundle'
            files=pack_bundle(str(target),str(root),['detailed'],password=PASSWORD,salt=SALT)
            report.update(encrypted_bundle_sha256=sha(target.read_bytes()),encrypted_bundle_files=files)
    (REPO/'evidence/sanitization-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'events':len(public),'comparison':build(public)['counts'],'detailed_bundle':args.bundle,'redactions':report['redactions']}))

if __name__=='__main__':main()
