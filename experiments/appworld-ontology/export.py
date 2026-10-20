"""Regenerate only the public metadata viewer. No private ledger or model calls."""
from core import ROOT,digest,encode
from public_records import PublishedRecords
from publication import render

def export():
    events=PublishedRecords().events()
    output=ROOT/'evidence.html'
    output.write_text(render(events,(ROOT/'index.html').read_text(),public=True))
    print(output)

if __name__=='__main__':export()
