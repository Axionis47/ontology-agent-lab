"""Read-only publication store. Importing or viewing never opens a provider."""
import json
from core import ROOT

class PublishedRecords:
    read_only = True
    def events(self, session=None):
        rows=json.loads((ROOT/'public-events.json').read_text())
        return [e for e in rows if session is None or e['session']==session]
