"""Repository-specific publication checks. No provider calls and no raw secret output."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
from zipfile import ZipFile
REPO=Path(__file__).resolve().parents[1]
IGNORED={'.git','.venv','.vendor','.runtime','.cache','__pycache__','.pytest_cache','private-evidence'}

def files():
    if (REPO/'.git').exists():
        result=subprocess.check_output(['git','ls-files','-z'],cwd=REPO).decode().split('\0')
        return [REPO/p for p in result if p]
    return [p for p in REPO.rglob('*') if p.is_file() and not IGNORED.intersection(p.relative_to(REPO).parts)]


def main():
    problems=[];checked=files()
    for p in checked:
        rel=str(p.relative_to(REPO))
        if IGNORED.intersection(p.relative_to(REPO).parts) or p.suffix in {'.sqlite','.db','.log'} or p.name=='.env':
            problems.append((rel,'forbidden publication path'));continue
        if p.suffix in {'.bundle','.pdf','.png'}:continue
        if p.suffix=='.docx':
            with ZipFile(p) as z:text='\n'.join(z.read(n).decode('utf-8',errors='ignore') for n in z.namelist() if n.endswith('.xml'))
        else:
            try:text=p.read_text()
            except UnicodeDecodeError:problems.append((rel,'unreviewed binary type'));continue
        # Report path and category only, never candidate secret content.
        for label,pat in [('JWT',r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'),
          ('private-home-path',r'/(?:Users|home)/[a-zA-Z0-9][^/\s"\']*/'),
          ('private-key',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          ('provider-key',r'\b(?:AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{25,})\b')]:
            if re.search(pat,text):problems.append((rel,label))
        if p.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',text):
                target=target.split('#')[0].split('?')[0]
                if not target or '://' in target or target.startswith(('mailto:','#')):continue
                if not (p.parent/target).exists():problems.append((rel,'broken-local-link: '+target))
    c=json.loads((REPO/'evidence/comparison.json').read_text())
    assert c['counts']=={'planned':4,'native_attempts':6,'conclusive':4,'inconclusive':2,'missing':0,'excluded':2}
    assert [r['checks_passed'] for r in c['runs']]==[1,3,1,4]
    report=json.loads((REPO/'evidence/sanitization-report.json').read_text())
    assert hashlib.sha256((REPO/'evidence/sanitized-traces.bundle').read_bytes()).hexdigest()==report['encrypted_bundle_sha256']
    if problems:
        print(json.dumps({'checked_files':len(checked),'problems':problems},indent=2));return 1
    print(json.dumps({'checked_files':len(checked),'problems':[],'comparison':'unchanged','bundle_checksum':'verified'}));return 0
if __name__=='__main__':raise SystemExit(main())
