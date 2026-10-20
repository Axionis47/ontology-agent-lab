# Publication evidence

The original private SQLite ledger is unchanged and is not distributed. `sanitization-report.json` records source and derivative hashes, event coverage and redaction counts. Every original event ID and sequence position is retained in the public projection and the sanitized encrypted trace. `comparison.json` is derived from those records, not a new experiment.

## Two views of the same history

- **Readable metadata:** `experiments/appworld-ontology/public-events.json` and its standalone HTML retain scores, attempts, exclusions, generated definitions/code, function counts, selected concept names, receipt identities, argument hashes, denials and effect counts. Protected task facts, raw actor messages and native receipt values are withheld explicitly. Unknown payload kinds default to withheld.
- **Encrypted sanitized detail:** `sanitized-traces.bundle` retains source-linked observations, actor code/context, facts and actual receipt arguments after authentication and private-path redaction. Private grader assertions/answers and the historical post-task reviewer payloads that may contain them are withheld. No raw database is included.

AppWorld's protected data and derivatives require encrypted public redistribution. The bundle uses its own native pack/unpack functions. After native setup, `python scripts/open_detailed_evidence.py` extracts the detailed HTML locally. No credentials or model calls are required for decryption, but an installed AppWorld runtime is needed. Never commit the decrypted outputs.

Scores are historical real-model results. The UI, projection, redaction, event-order audit and unit fixtures are not-a-model software operations. Loading historical output is not a new live call. The v3.1 pass does not establish general ontology improvement.
