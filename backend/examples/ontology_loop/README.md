# Small operational ontology experiment

This example uses one hotel task surface and an existing Gemini ReAct loop.
It uses two unchanged, free Model Context Protocol (MCP) packages:

- `mcp-server-sqlite==2025.4.25` reads records and writes local reservations.
- `@modelcontextprotocol/server-filesystem@1.0.0` writes the answer file.

The records are fictional. A reservation is a local database row.
The example does not book a real room or use a paid MCP service.
The SQLite reference package is archived. This experiment is not a deployment recommendation.

## Mechanism

```text
Task rules + granted source contracts + sampled training worlds
                              |
                   Gemini generates a kernel
                              |
          OWL schema checks + typed function execution
                              |
           Scores and observable trajectories -> judge
                              |
                    Repair, validate, freeze

New request -> Gemini's native MCP client -> existing SQLite server
            -> raw records and a generated named SQL query
            -> proposal -> agent-side action check
            -> existing Filesystem and SQLite servers perform local writes
```

The kernel contains declared relations and a typed function program.
The model generates relation mappings, traversals, predicates, and arithmetic.
The source record vocabulary and primitive operations are developer code.
The experiment tests relation and function generation. It does not test discovery of new record classes.
No generated Python or shell code is executed.

The compiler maps the function to the `eligible_stays` SQL view.
The function arguments are bound to the validated request before an episode starts.
The view computes from current records. It is not a stored expected answer.
Its rows contain source identifiers and relation paths.
New episodes replace the records. They do not change the frozen kernel.

Web Ontology Language (OWL) and HermiT check schema consistency and unsatisfiable classes.
Tests also cover disjoint classes, property domains, and cardinality restrictions.
Separate code checks missing links, conflicting identities, and numerical task rules.
OWL consistency does not prove that the ontology fits the task or that source records are true.

## Execution and writes

Gemini discovers and calls the existing servers through its native MCP client.
The inference runner does not parse text into tool calls.
The construction adapter uses structured JSON because it generates artifacts, not task actions.

The agent hook accepts only granted source reads, the answer path, and a reservation insertion.
It binds accepted results to the original request and source snapshot.
It prevents competing reservations and permits retries of the same reservation.
It records proposals before it checks them.
Each episode has an isolated database with no external writer.
The hook check and MCP write are separate operations.
A shared production database would need a transactional check at the write boundary.

The baseline and schema-only conditions can compose ordinary read-only SQL over source tables.
Strict ontology inference uses declared source reads and the generated function view.
An accepted strict answer must match that function.
All conditions use the same local action contract.
The first proposed answer and action are scored separately from accepted writes.
Thus, the shared action check cannot create a measured reasoning improvement.

Gemini CLI 0.67.0 requires three local fixes for this experiment.
One fix omits an empty tool catalog in model-only construction calls.
The second makes the required task hook fail closed on errors or missing approval.
The second fix is active only with `OAK_REQUIRE_TASK_GUARD=1`.
The third preserves an empty JSON array as MCP text content.
The original client incorrectly converts that array to object-only structured content.
The scripts preserve bundle backups. They do not change either MCP server.

## Local setup

Run these commands from `backend`:

```sh
uv sync --extra ontology-demo
npm install --prefix .local/gemini-cli @google/gemini-cli@0.67.0
npm install --prefix .local/real-mcp @modelcontextprotocol/server-filesystem@1.0.0
uv venv .local/real-mcp/sqlite-venv
uv pip install --python .local/real-mcp/sqlite-venv/bin/python 'mcp-server-sqlite==2025.4.25' 'mcp==1.30.0'
python scripts/patch_gemini_empty_tools.py
python scripts/patch_gemini_hook_fail_closed.py
python scripts/patch_gemini_mcp_json_content.py
```

Gemini uses the existing Vertex AI credentials.
The optional `.local/gemini-auth.json` profile contains `auth_type`, `project`, `location`, and `model`.
Use `vertex-ai` for `auth_type`. Do not put credential values in the profile or repository.
Set `OAK_GEMINI_PROFILE` to select another profile file.
Set `OAK_GEMINI_CLI` to select another CLI executable.
The experiment pins `gemini-3.8-flash`.
Set `OAK_JAVA` if Java is not available. Homebrew Java 21 is also detected.

## Reproduce checks and inspect results

```sh
.venv/bin/python -m pytest examples/ontology_loop -q
.venv/bin/python -m examples.ontology_loop.report
```

The current evidence is in `.local/ontology-experiments`.
Open `report.html` for the visual report.
The directory contains all construction prompts, model responses, OWL files, hashes,
MCP trajectories, reference worlds, scores, failed attempts, and the budget ledger.
These local artifacts are ignored by Git.

To resume the recorded paired pilot, use its original output directory, count, and seed.
The runner rejects changed code or kernels under an existing manifest.
The manifest checks the suite, hook, SQL compiler, native runner, and generated kernel files.
It does not hash the installed CLI or server packages.
The runner records a failure for a model error or an incomplete action.
Expected answers never enter the agent workspace or MCP responses.

```sh
.venv/bin/python -m examples.ontology_loop.experiments --output .local/ontology-experiments/pilot-v3 --count 10 --seed 915 --parallel 3
```

This command makes paid Gemini requests for missing episodes.
The recorded pilot stopped at 38 of 60 episodes because its remaining budget could not fund a new reservation.
The existing budget gate prevents more calls under the same allowance.
All runs in this experiment share the append-only USD 40 budget ledger.
The ledger counts cached tokens at full input rates and includes reasoning tokens.
It retains a conservative charge when usage data is missing.
For verified session logs, it counts completed responses and retains an additional retry allowance.
Those logs do not establish the cost of unfinished requests.
It is an estimate, not a provider invoice.

## Evidence limits

Four independent live constructions converge on one equivalent reasoning procedure.
They do not establish that one wording or sample method is better.
Explicit schema and function mutations test repair. They are not natural drafting failures.
One repaired native episode completed its answer and reservation, then hit the old eight-turn limit.
That limitation remains in the repair record. The final pilot uses twelve turns for every condition.

The 10,000 generated cases per kernel check the executor. They are not live LLM episodes.
The small paired pilot does not replace the planned 240-world repeated evaluation.
The first two pilots remain in the audit log as integration diagnostics.
They are excluded from the comparison because the execution protocol changed.
The third pilot uses fresh worlds and frozen execution code.
Keep the formal victory result `not_demonstrated` unless every condition in
[the victory criteria](../../../docs/ontology-victory.md) passes.

This is a bounded representation of paper Sections 3.1 to 3.3.
Structured records replace the paper's text extraction stage.
Named SQL views implement the typed computation catalog through an existing MCP server.
The agent hook is the integration point for action control.
It does not provide automatic onboarding for arbitrary tools or agents.
Each episode starts with a fresh prompt and MCP configuration. Existing agent memory is not imported.
No model weights or multi-agent coordination are trained here.

Sources: [project paper](../../../docs/paper/source/oak-2608.22974v1.pdf),
[OWL primer](https://www.w3.org/TR/owl-primer/),
[SQLite MCP package](https://pypi.org/project/mcp-server-sqlite/),
[Filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem),
and [Gemini CLI hooks](https://geminicli.com/docs/hooks/reference/).
