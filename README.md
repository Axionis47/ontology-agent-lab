# Ontology Agent Lab

Papers, a small teaching example, and an inspectable AppWorld experiment about making domain relationships explicit for agents.

**Current result:** the final v3.1 workflow passed 4/4 official checks on one previously seen AppWorld training task. It executed all three generated ontology functions and committed three verified requests. Earlier failures remain part of the evidence. This is a development demonstration, not a reproduction of OaK or proof that ontologies generally improve agents.

## Start here

1. Read the [paper collection](papers/README.md) and [mechanism notes](papers/notes/README.md).
2. Read the [ontology and harness guide](guides/ontology-and-agent-harness.docx).
3. Run `python3 examples/ontology_walkthrough.py` to see a hand-authored schema correction and explicit checks. It makes no model calls.
4. Download and open [the standalone evidence viewer](experiments/appworld-ontology/evidence.html). GitHub displays HTML source; save the file locally to use the interactive UI.
5. Read the [AppWorld experiment](experiments/appworld-ontology/README.md), [publication evidence policy](evidence/README.md) and [next-study limits](experiments/appworld-ontology/NEXT-STUDY.md).

## What happened

| Version | Official checks passed | Overall result | Generated functions captured | Gate-committed requests |
| --- | --- | --- | --- | --- |
| v1 | 1/4 | Failed | 1 retained stdout record, incomplete capture | No gate |
| v2 | 3/4 | Failed | 0 | No gate |
| v3 | 1/4 | Failed | 1 | 0 |
| v3.1 | 4/4 | Passed | 3 | 3 |

Four version cells required six native attempts. Two attempts are separately classified inconclusive/excluded, including a controller date-format defect. The original official failure for that defect remains visible. V3's conclusive receipt-interface failure was preserved; v3.1 was a distinct interface treatment with the same frozen ontology/functions. Counts use different historical capture mechanisms and are not an ontology-quality score.

The versions changed schemas, context, functions, evidence verification and enforcement. This does not isolate an ontology effect. There is no held-out success rate, formal OWL/HermiT proof, adversarial sandbox guarantee, latency advantage or established dollar-cost saving.

## View locally, without credentials

Use Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -c constraints-native.txt -r requirements.txt
cd experiments/appworld-ontology
../../.venv/bin/python server.py
```

Open <http://127.0.0.1:8766>. The default server is read-only and uses published JSON. It does not instantiate a provider, create a raw evidence database, or launch tasks. Alternatively, the standalone HTML needs no server or Python.

The public UI shows ontology definitions and measurement metadata. AppWorld requires protected data and derivatives to be redistributed encrypted. Detailed sanitized traces are in [an encrypted bundle](evidence/sanitized-traces.bundle), with [explicit local decryption instructions](evidence/README.md). No authentication values, private grader answers, raw SQLite database or upstream task database are included.

## Software checks

```sh
.venv/bin/python -m pytest -q
```

Default checks require no model, cloud credentials or AppWorld data. Two separately marked native mechanics checks require the native runtime and official downloaded data. See [SETUP.md](SETUP.md). These software fixtures are not live-model evidence.

## Explicit new live work

[SETUP.md](SETUP.md) describes pinned native setup, Vertex ADC, configuration and an explicit new-run command. A new run records fresh evidence and never overwrites the published study. Historical v2/v3 revision entry points depend on prior local records; they are retained for inspection, not advertised as one-command reproductions of the past.

This publication adds no new AppWorld or model experiment results. The proposed ontology consolidation study remains unrun. The broader six-method memory comparison and unrelated projects are outside this repository.

No new license has been applied to the original code. Papers and the AppWorld adapter retain their [individual third-party terms](third-party/README.md).
