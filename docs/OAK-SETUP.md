# OaK development setup

We are implementing OaK with observable construction, refinement, and inference loops. External APIs keep their existing contracts. Our local ontology-aware functions can wrap and compose their supported operations. Neo4j stores task facts and relationships; OWL/HermiT checks the ontology schema separately. The [product design](oak/DESIGN.md) selects a sequential read-only loop and an offer-selection engineering fixture. The live benchmark/API, model, and evaluation budget remain unselected.

## Installed and verified

Checked November 1, 2026 on this Apple Silicon Mac, using the isolated root `.venv`. Exact Python dependency resolution is recorded in [uv.lock](../uv.lock); direct dependencies are declared in [pyproject.toml](../pyproject.toml).

| Component | Installed version | Purpose and verification |
| --- | --- | --- |
| Python | 3.12.8 | Project interpreter |
| uv | 0.12.0 | Environment and lockfile management; installed-package compatibility check passed |
| LangGraph | 1.2.19 | Deterministic workflow, interrupt/resume, and checkpoint recovery passed |
| SQLite checkpointer | 3.1.3 | A checkpoint was reopened from a new connection |
| Pydantic | 2.14.2 | Valid input accepted; wrong type and invalid value rejected |
| Neo4j Community | 5.26.28 | Running in Docker; parameterized relationship query passed; probe transaction rolled back |
| Neo4j Python driver | 6.4.1 | Connectivity and server-version query passed |
| Owlready2 | 0.51 | Python interface to its bundled HermiT reasoner |
| OpenJDK | 21.0.12.1 | HermiT inferred a class and detected a deliberate contradiction |
| LangSmith SDK | 0.14.17 | Installed; hosted connection still requires your API key |
| LangGraph CLI | 0.4.40 | CLI and `dev` command available; Studio session awaits an application graph and account configuration |

Docker Desktop is installed and running, with Docker Engine 27.5.1 and Compose 2.32.4. The [Compose configuration](../infra/compose.yaml) pins the Neo4j image by digest and uses project-specific named data and log volumes. HTTP and Bolt ports are bound to `127.0.0.1`.

The repeatable [installation probe](../scripts/check_oak_stack.py) passed all four checks: contracts, workflow, Neo4j, and HermiT. Its local receipt is `.runtime/setup-check.json`. These are infrastructure checks, not task-level agent results. No model calls or hosted trace uploads were made.

## Run locally

Run these commands from the repository root:

```sh
uv sync --locked --cache-dir .cache/uv
docker compose --env-file .env -f infra/compose.yaml up -d
.venv/bin/python scripts/check_oak_stack.py
```

This machine already has an ignored `.env` with a generated local Neo4j password and file permissions `0600`. Do not overwrite it with the example. For another checkout, copy [.env.example](../.env.example) to `.env`, set a strong password, and configure `JAVA_HOME` before starting Neo4j. The current Java home is `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`; the probe reads it directly, so no global Java symlink or shell configuration is required.

Open [Neo4j Browser](http://localhost:7474/browser/) to inspect the graph. Connect to `bolt://localhost:7687`, with username `neo4j` and the password in your local `.env`. There is no domain dataset yet, and the probe leaves no fixture nodes behind.

Stop the service with:

```sh
docker compose --env-file .env -f infra/compose.yaml down
```

This preserves the named data volumes. Do not add `--volumes` when you want to keep the database.

## Observability and implementation work

Add your own LangSmith API key to the ignored `.env` and confirm the intended `LANGSMITH_PROJECT` before enabling `LANGSMITH_TRACING=true` for the application. The setup probe always disables hosted tracing. Installation does not verify hosted access, and no Studio application session is running yet. The CLI supplies the local development server that Studio can inspect once the application graph exists.

As the algorithm is implemented, expose LangGraph state transitions and checkpoints, nested LangSmith spans, local JSONL events, immutable artifacts, and source provenance. Instrument the actual operations inside wrappers so one agent-visible call does not conceal several API or Cypher operations. Record checks, failures, retries, timing, tokens, and cost without requesting hidden reasoning text.

Keep the workflow graph, domain graph, schema checks, task validation, and evaluation distinct. Neo4j query success does not establish OWL consistency or task correctness. HermiT inference does not validate missing API fields, calculate all task constraints, or prove a completed plan is correct. The installed reasoner is the distribution bundled with Owlready2 0.51, not a claim of binary equivalence with the paper's setup.

The [project instructions](../AGENTS.md) define the working agreement. The [research narrative](oak/STATUS.md) records the implementation choices and the evidence required before claiming task-level gains.
