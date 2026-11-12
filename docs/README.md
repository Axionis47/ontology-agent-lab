# Project documentation

This index is the entry point for the Oak documentation.
The guides describe the current implementation and the agreed project scope.
The documentation describes current product behavior and verified implementation details.
Planning records are maintained separately.

## Reading order

| Order | Document | Use |
| --- | --- | --- |
| 1 | [Overview](overview.md) | Purpose, scope, and success conditions |
| 2 | [Terms](terms.md) | Project terms and abbreviations |
| 3 | [Setup](setup.md) | Local installation and startup |
| 4 | [User guide](use.md) | Task setup, discovery, training, and inference |
| 5 | [System](system.md) | Components, execution, and stored data |
| 6 | [Settings](settings.md) | Environment variables and run limits |
| 7 | [API](api.md) | Application programming interface (API) routes and request rules |
| 8 | [Tests](tests.md) | Local checks and continuous integration (CI) |
| 9 | [Deployment](deploy.md) | Private deployment, release, and rollback |
| 10 | [Writing](writing.md) | Language reference and document review |

For a first local demonstration, read Overview, Setup, and User guide.
For a code change, also read System, API, and Tests.
The [operator rationale](system.md#why-the-nine-operator-capabilities-matter) explains the nine paper capabilities and their implementation.
The [technical walkthroughs](system.md#technical-walkthroughs) give examples, execution steps, results, and boundaries for all twelve engineering areas.
The [boundary table](system.md#operating-boundaries-and-failure-points) states the enforced limits and remaining failure points.
The [test map](tests.md#mechanism-test-map) connects each engineering area to controlled evidence.
For a release, read Tests before Deployment.

## Document authority

The [project instructions](../AGENTS.md) define the agreed scope and access boundaries.
The current user decisions take precedence over earlier requirements.
An implementation difference does not silently change an agreed requirement.
Record the difference before a code or requirement change.

The current guides describe implemented behavior.
They do not make the earlier benchmark proposals active product requirements.

## Reference documents

| Reference | Status |
| --- | --- |
| [Source paper](paper/source/oak-2608.22974v1.pdf) | Research basis. Preserve the source file. |
| [First experiment criteria](ontology-victory.md) | Earlier experiment criteria and recorded limits |
| [Ontology example](../backend/examples/ontology_loop/README.md) | Separate local experiment |
| [Behavior stress example](../backend/examples/behavior_stress/README.md) | Separate runtime comparison tool |

## Update the documentation

1. Change the guide that owns the information.
2. Keep exact code identifiers and interface labels.
3. Update links if a file location changes.
4. Update Tests when new evidence changes a result.
5. Do the review in [Writing](writing.md).

Keep requirements, implementation descriptions, and measured results distinct.
Do not use a planned feature as evidence of an implemented feature.
