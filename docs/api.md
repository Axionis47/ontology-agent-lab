# API guide

[Documentation index](README.md)

The application programming interface (API) uses FastAPI.
The generated [OpenAPI file](../frontend/openapi.json) defines exact request and response schemas.
The generated [TypeScript types](../frontend/src/lib/api-types.ts) use that contract.
The [route implementation](../backend/oak/main.py) defines runtime behavior.

## Access

For backend routes with the `/api` prefix, the `X-Oak-Key` header is necessary.
The value must match the private backend key.
Task routes also use `X-Oak-User` for the selected demo identity.
The current identities are `demo-alex` and `demo-sam`.
If the user header is absent, the backend selects `demo-alex`.

The frontend proxy adds the private backend key on the server.
The browser sends the selected demo identity through that proxy.
This identity selector is a preview mechanism, not production authentication.

The health route and OAuth routes sit outside `/api`.
The application disables its public interactive API documentation routes.

## Service and configuration routes

Route parameters in braces identify saved records.
IDs use universally unique identifiers (UUIDs), except the fixed demo user identifiers.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Database health and release identifier |
| GET | `/oauth/client-metadata.json` | OAuth client metadata |
| GET | `/oauth/callback` | Authorization callback |
| GET | `/api/users` | Available demo identities |
| GET | `/api/model-runtime` | Model configuration and saved connection result |
| POST | `/api/model-runtime/check` | Start an explicit connection check |
| GET | `/api/tasks` | Tasks available to the selected user |
| POST | `/api/tasks` | Create a task |
| GET | `/api/tasks/{task_id}` | Read a task |
| PATCH | `/api/tasks/{task_id}` | Change a task name with unchanged objective and scope |
| GET | `/api/tasks/{task_id}/agents` | List agent configurations |
| POST | `/api/tasks/{task_id}/agents` | Create an agent with its configuration and optional grants |
| PATCH | `/api/tasks/{task_id}/agents/{agent_id}` | Update an agent configuration |
| PUT | `/api/tasks/{task_id}/agents/{agent_id}/tools` | Replace the selected tool grants |
| GET | `/api/tasks/{task_id}/connections` | List MCP connections |
| POST | `/api/tasks/{task_id}/connections` | Add an MCP connection |
| POST | `/api/tasks/{task_id}/connections/{connection_id}/refresh` | Refresh a tool catalog |
| PUT | `/api/tasks/{task_id}/connections/{connection_id}/token` | Set a connection token |
| DELETE | `/api/tasks/{task_id}/connections/{connection_id}` | Remove a connection |
| GET | `/api/tasks/{task_id}/tools` | List the task's tool catalog |

MCP means Model Context Protocol.
Each granted tool remains one callable operation.
Its declared input schema controls the tool arguments.

## Discovery routes

The discovery prefix is `/api/tasks/{task_id}/agents/{agent_id}/discovery`.
Append each suffix to that prefix.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | Empty | Discovery overview and history |
| POST | `/runs` | Start discovery |
| GET | `/runs/{run_id}` | Run detail |
| GET | `/runs/{run_id}/events` | Recorded events |
| GET | `/runs/{run_id}/artifacts/{artifact_id}` | Saved evidence or proposal |
| POST | `/runs/{run_id}/resume` | Continue with answers or increased limits |
| POST | `/runs/{run_id}/pause` | Request a pause |
| POST | `/runs/{run_id}/stop` | Request a stop |

The overview accepts `offset`.
The event route accepts `after`, which is an event sequence value.
Start requests must contain `request_id`, `environment`, and `limits`.
Resume requests must contain `request_id` and `expected_revision`.
Answers and increased limits are optional resume fields.

The revision prevents a stale page from changing a newer run state.
Duplicate request handling uses saved request identifiers.
Run reads do not start model calls or task tool calls.

## Training and inference routes

The training prefix is `/api/tasks/{task_id}/agents/{agent_id}/training`.
Append each suffix to that prefix.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | Empty | Cases, history, and inference eligibility |
| POST | `/cases` | Save a training case |
| PUT | `/cases/{case_id}` | Replace a training case |
| DELETE | `/cases/{case_id}` | Remove a training case |
| POST | `/runs` | Start training with all saved cases |
| POST | `/inference` | Start inference with an accepted harness |
| GET | `/runs/{run_id}` | Run detail and saved results |
| POST | `/runs/{run_id}/stop` | Request a stop |
| GET | `/runs/{run_id}/events` | Recorded events |
| GET | `/runs/{run_id}/episodes/{episode_id}` | One episode and its evidence |

The existing run detail supplies the definition catalog and change history.
These views use candidate snapshots and events.
`repair_review` events use `oak.repair-review.v1`.
`graph_route` events use `oak.graph-route.v1`.
Historical events can lack these records.
No new REST endpoint or database migration is required.

`query_graph(query_json)` and `run_function(function_id, arguments_json)` are internal model tools.
The catalog in `harness_catalog` publishes the `GraphQuery` schema and complete definitions.
`read_evidence` reads that catalog through the existing evidence interface.

The overview accepts `offset`.
The event route accepts `after`.
Start routes return status `202` with a saved run view.
That response does not establish task completion.

| Request schema | Necessary fields | Other fields |
| --- | --- | --- |
| `TrainingCaseInput` | `query`, `tool_ids`, `task_success` | None |
| `TrainingStart` | `request_id` | `discovery_run_id`, `environment_ref`, `limits` |
| `InferenceStart` | `request_id`, `query`, `tool_ids` | `accepted_candidate_id`, `limits` |

Case queries permit up to 16000 characters.
Task-success descriptions permit up to 8000 characters.
Case tool lists must contain 1 through 100 distinct granted tool IDs.

The `stable` environment reference asserts comparable state for repeated training episodes.
It does not reset the environment.
A configured preparation adapter can supply actual reset behavior.
See the [User guide](use.md#start-training) before this assertion.

A repeated training request ID returns the prior run only when its inputs match.
The backend rejects reuse of that ID with different inputs.
Inference can pin `accepted_candidate_id` to detect an acceptance change before launch.

## States and errors

Discovery states are `running`, `pausing`, `paused`, `completed`, and `stopped`.
Training and inference states are `running`, `stopping`, `completed`, `stopped`, `failed`, and `interrupted`.
A run state describes execution progress.
The candidate decision and task evaluation describe different results.

| Status | Typical cause |
| --- | --- |
| 401 | Missing or incorrect private access key, or invalid demo identity |
| 404 | Requested record is absent or unavailable to the selected user |
| 409 | Stale configuration, conflicting active run, or incompatible acceptance record |
| 422 | Invalid fields, tool grants, or run limits |

Validation errors use a general response that does not repeat private request values.
Client code must examine the error response before another action request.

## Change the API contract

1. Change the backend schemas and routes.
2. Generate `frontend/openapi.json` from the backend.
3. Generate the TypeScript types from that file.
4. Do the compatibility and type checks in [Tests](tests.md).
5. Include the two generated files in the same code change.
