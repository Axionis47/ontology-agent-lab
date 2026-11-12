# Tests

[Documentation index](README.md)

## Recorded validation

MCP means Model Context Protocol.
The November 11, 2026 validation recorded these results:

| Check | Recorded result | Evidence limit |
| --- | --- | --- |
| Backend and example tests | 717 passed | Controlled tests, not a model benchmark |
| Python lint and format | Passed | Source checks |
| Frontend type and lint checks | Passed | Static checks |
| Production frontend build | Passed | Build result, not deployment evidence |
| Training and inference browser tests | 9 passed | Controlled model and MCP fixtures |
| Native Linux AMD64 resource check | No passing result recorded | Required before deployment |

The backend result includes `tests`, `examples/ontology_loop`, and `examples/behavior_stress`.
It used a separate UTF-8 PostgreSQL test database and Java 21.
These recorded results do not replace checks of a later code revision.

## Live model evaluation

A complete live demonstration of the current runtime remains necessary.
A matched comparison with basic ReAct is also necessary before a reliability improvement claim.
The earlier two-case Gemini check used prepared discovery inputs.
It does not establish the complete version 3 construction and inference flow.

The November 10 behavior stress run stopped discovery at the input token limit.
Training and all ontology comparison episodes remained blocked.
The baseline episodes included one completed answer, two unknown outcomes, and one failed run.
Provider errors and input capacity affected those results.
The records do not establish an ontology improvement.

The [stress example guide](../backend/examples/behavior_stress/README.md) describes the runner and report format.
Local run records are excluded from Git and are unavailable in a fresh checkout.
The [earlier experiment criteria](ontology-victory.md) retain the incomplete ontology pilot result, `not_demonstrated`.

## Test environment

Use the dependencies from [Local setup](setup.md).
Use Java 21 for formal ontology checks.
Use a separate PostgreSQL database whose name ends in `_test`.
The tests erase task data in that database.

The Docker configuration creates `oak_test` on its first database initialization.
For an existing volume without that database, create the test database explicitly.
Use UTF-8 encoding for a manually created PostgreSQL cluster.

Set the test database variable in the terminal that executes the checks:

```sh
export OAK_TEST_DATABASE_URL=postgresql://oak:oak-local-only@127.0.0.1:55432/oak_test
```

This address uses the repository's Docker credentials.
For another local database, use its separate test connection string.

## Backend checks

Execute these commands from `backend`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

The tests use controlled model responses and local MCP servers.
They cover access boundaries, discovery, evidence, function execution, acceptance, repair, and inference.
The test commands do not start a paid model experiment.

The separate example tests use this command:

```sh
uv run pytest -q examples/ontology_loop examples/behavior_stress
```

Some example integration tests use the documented local MCP packages.
The [ontology example](../backend/examples/ontology_loop/README.md) describes those dependencies.

## Mechanism test map

Each row links an engineering area to tests of its mechanism or failure behavior.
The fixtures use controlled observations and model responses.
Passing these tests does not establish exhaustive coverage or general agent reliability.
See the [technical walkthroughs](system.md#technical-walkthroughs) and [operating boundaries](system.md#operating-boundaries-and-failure-points) for their meaning.

| Area | Evidence in the tests |
| --- | --- |
| Task and tool boundaries | [Dispatcher tests](../backend/tests/test_kernel_dispatcher.py) reject changed tool definitions, invalid arguments, and reused permits. [Training tests](../backend/tests/test_training.py) stop dispatch after a grant change. |
| Request meaning | [Request tests](../backend/tests/test_request_preparation.py) check source values, omitted constraints, negation correction, one retry, and unresolved fields. |
| Live graph updates | [Scoped graph tests](../backend/tests/test_scoped_evidence_graph.py) check identity, separate contexts, replacement, partial updates, coverage, and atomic rejection. |
| Executable definitions | [Execution tests](../backend/tests/test_kernel_execution.py) check units, exact comparisons, missing values, traversal, and aggregation coverage. [Formal tests](../backend/tests/test_ontology_verification.py) distinguish logical faults from verifier failures. |
| Missing observations | [Acquisition tests](../backend/tests/test_acquisition.py) reject incorrect filters and page sequences. [Query tests](../backend/tests/test_graph_query.py) derive acquisition needs without changing the candidate. |
| External actions | [Dispatcher tests](../backend/tests/test_kernel_dispatcher.py) check automatic conditions and each current graph revision. [Training tests](../backend/tests/test_training.py) check write facts, unknown outcomes, and restart without replay. |
| Reuse before additions | [Query tests](../backend/tests/test_graph_query.py) cover lookup without a helper, three- and four-relation routes, intermediate function results, and rejected action steps. |
| Failure diagnosis | [Review tests](../backend/tests/test_repair_review.py) reproduce mapping and relation defects. They also check targeted additions and unchanged decisions for tool failures, limits, and evaluator errors. |
| Controlled changes | [Definition checks](../backend/tests/test_repair_review.py) reject duplicates. [Coverage tests](../backend/tests/test_kernel_validation.py) require a decision and original source for every constant use. [Training validation](../backend/tests/test_training_validation_flow.py) blocks repeated rejected proposals against unchanged evidence. |
| Acceptance | [Training validation](../backend/tests/test_training_validation_flow.py) rejects failed outcomes and missing execution coverage. [Training tests](../backend/tests/test_training.py) preserve passing cases through repair. |
| Resource limits | [Evidence tests](../backend/tests/test_evidence_access.py) check bounded views and incomplete reads. [Model tests](../backend/tests/test_model_runtime.py) reject excessive input before provider calls. |
| Versions and visibility | [Acceptance tests](../backend/tests/test_kernel_acceptance.py) reject stale or altered records. [Browser tests](../frontend/e2e/training.spec.ts) inspect evidence links and history after reload, including older records without reviews. |

Run the local mechanism checks from `backend`:

```sh
uv run pytest -q \
  tests/test_graph_query.py \
  tests/test_kernel_dispatcher.py \
  tests/test_request_preparation.py \
  tests/test_scoped_evidence_graph.py \
  tests/test_kernel_execution.py \
  tests/test_acquisition.py \
  tests/test_repair_review.py \
  tests/test_kernel_validation.py \
  tests/test_training_validation_flow.py \
  tests/test_evidence_access.py \
  tests/test_kernel_acceptance.py \
  -k 'not real_mcp_pages'
```

This selection covers the local walkthrough mechanisms without a database, live provider, or paid model calls.
It includes function rebinding, paged refresh, and constant-review regression cases.
The constant tests control evaluator outputs. They establish enforcement of review decisions, not perfect model interpretation of natural language.
Run the full backend suite for the database, budget, formal-verifier, and local MCP integration checks.
Run the browser command below for the saved catalog and history walkthrough.

## Generated API files

API means application programming interface.
After a route or schema change, execute this command from `backend`:

```sh
uv run python -m scripts.export_openapi
```

Then execute these commands from `frontend`:

```sh
npm run api:generate
npm run typecheck
```

Examine the two generated files before the commit.
Continuous integration (CI) regenerates them and rejects differences from the committed files.
CI also compares the API with the previous contract for breaking changes.

## Frontend and browser checks

Execute these commands from `frontend`:

```sh
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright starts the production frontend, backend, and controlled MCP server.
The test database variable must remain available to this process.
Ports `3047`, `8047`, and `9147` must be available.

The browser suite covers configuration, discovery, schema views, evidence views, training, and inference.
The suite also covers the private access gate and authorization recovery.
Its scripted model results establish application behavior, not general model reliability.

The reuse checks include lookups without helper functions, multi-relation queries, source acquisition, and recorded-input repair.
They also check duplicate definitions, unsupported constants, repeated rejected patches, and candidate reuse.
The ledger browser checks inspect versions, evidence links, proposed causes, and reload behavior.

For the controlled training demonstration, execute this command from `frontend`:

```sh
npm run test:e2e -- e2e/training.spec.ts e2e/kernel-inference.spec.ts
```

## CI and deployment checks

The [CI workflow](../.github/workflows/ci.yml) runs on pull requests and pushes to `main`.
Its `checks` job covers code quality, tests, generated files, API compatibility, migrations, and the production frontend build.
Its `deployment-resources` job evaluates the service container on Linux AMD64.

The resource check uses a 512 MiB memory limit and a 0.1 CPU limit.
It includes the API process and formal schema verification in the same service container.
See [Deployment](deploy.md#resource-check) for the command and release condition.

## Examine results

1. Read the first failure and its saved evidence.
2. Identify whether the cause is code, test setup, provider behavior, or a task outcome.
3. Make the smallest supported correction.
4. Repeat the affected check.
5. Execute the necessary full checks before release.

Preserve failed and inconclusive task records.
A passing code test does not establish an improvement over the baseline agent.
