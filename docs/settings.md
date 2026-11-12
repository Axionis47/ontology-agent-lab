# Settings

[Documentation index](README.md)

The backend reads environment variables and `backend/.env`.
The local frontend reads `frontend/.env.local`.
Keep private values outside Git.

HTTP means Hypertext Transfer Protocol.
HTTPS means HTTP over Transport Layer Security.
MCP means Model Context Protocol.

The source of backend defaults is [settings.py](../backend/oak/settings.py).
The example files list configuration keys, not working production credentials.
See [Local setup](setup.md) before changes to an existing installation.

## Backend service

| Variable | Default or requirement |
| --- | --- |
| `OAK_ENVIRONMENT` | `production`. Use `local` for local development. |
| `OAK_DATABASE_URL` | Default: `postgresql://localhost:5432/oak`. Set the actual database address. |
| `OAK_API_KEY` | Necessary. At least 32 characters. |
| `OAK_PUBLIC_API_URL` | Default: `http://localhost:8000`. Use HTTPS in production. |
| `OAK_FRONTEND_URL` | Default: `http://localhost:3000`. Use HTTPS in production. |
| `OAK_SECRET_BACKEND` | `vault`. Local development can use `local`. |
| `OAK_LOCAL_SECRET_KEY` | Necessary for local encrypted credential storage. |
| `OAK_ALLOW_LOCAL_MCP` | `false`. Use `false` in production. |
| `OAK_DISCOVERY_TIMEOUT` | `30` seconds for connection discovery. |
| `OAK_OAUTH_TIMEOUT` | `300` seconds for authorization. |
| `OAK_RELEASE_SHA` | Default: `local`. The release workflow supplies the tested commit. |
| `OAK_JAVA` | Optional Java executable path for formal schema verification. |

Render can supply the public address through `RENDER_EXTERNAL_URL`.
It can supply the release identifier through `RENDER_GIT_COMMIT`.
Explicit `OAK_*` values take precedence for those aliases.

## Model connection

| Variable | Default | Allowed values |
| --- | --- | --- |
| `OAK_GEMINI_PROJECT` | Empty | Google Cloud project identifier |
| `OAK_GEMINI_LOCATION` | `global` | Use `global` with the current connection policy. |
| `OAK_GEMINI_MODEL` | `gemini-3.8-flash` | Use this model with the current connection policy. |
| `OAK_GEMINI_TIMEOUT` | `25` | Greater than 0, with a maximum of 30 seconds |
| `OAK_GEMINI_MAX_OUTPUT_TOKENS` | `4096` | 32 through 65536 |
| `OAK_GEMINI_CHECK_BUDGET_USD` | `0` | 0 through 0.10 |

These values describe the implemented configuration policy.
They do not establish provider availability or current provider prices.
Application Default Credentials (ADC) are also necessary on the backend host.

Connection checks have their own saved cost allowance.
A changed project, model, location, timeout, or output limit makes an earlier check outdated.
The runtime reserves estimated cost before each model call.
Unknown usage keeps the reservation.
The estimate is not a provider invoice.

## Backend run ceilings

The backend rejects run limits above these ceilings.
The selected run limit can be lower than its backend ceiling.

| Variable | Default | Configuration range |
| --- | --- | --- |
| `OAK_SURFACE_MAX_COST_USD` | `10` | Greater than 0, with a maximum of 100 |
| `OAK_SURFACE_MAX_MCP_CALLS` | `100` | 12 through 200 |
| `OAK_SURFACE_MAX_MODEL_CALLS` | `100` | 14 through 200 |
| `OAK_SURFACE_MAX_ACTIVE_SECONDS` | `3600` | 600 through 7200 |
| `OAK_SURFACE_MAX_CLARIFICATION_ROUNDS` | `10` | 2 through 20 |

## Model and tool capacity

| Variable | Default | Configuration range |
| --- | --- | --- |
| `OAK_SURFACE_INPUT_TOKENS` | `32768` | 4096 through 131072 |
| `OAK_SURFACE_PROBE_OUTPUT_TOKENS` | `4096` | 512 through 65536 |
| `OAK_SURFACE_PROPOSAL_OUTPUT_TOKENS` | `16384` | 512 through 65536 |
| `OAK_SURFACE_MODEL_TIMEOUT` | `90` | Greater than 0, with a maximum of 180 seconds |
| `OAK_SURFACE_TOOL_TIMEOUT` | `30` | Greater than 0, with a maximum of 120 seconds |

Output limits include reasoning tokens where the model reports them.
The complete request must fit within the model input budget.

## Limits selected for a run

The application validates selected limits separately from backend settings.
See [DiscoveryLimits](../backend/oak/discovery_schemas.py) and [TrainingLimits](../backend/oak/training_schemas.py).

| Limit | Discovery default | Training and inference default |
| --- | --- | --- |
| Cost in USD | Necessary input | 1 |
| Model calls | 14 | 40 |
| MCP calls | 12 | 30 |
| Active seconds | 600 | 600 |
| Clarification rounds | 2 | Not applicable |
| Agent steps | Not applicable | 12 |
| Construction rounds | Not applicable | 3 |

Inference uses the shared limits type but does not execute construction rounds.
Increasing a discovery limit does not reset the run's counters.

## Frontend

| Variable | Requirement |
| --- | --- |
| `OAK_API_URL` | Backend URL without a trailing slash |
| `OAK_API_KEY` | Same private key as the backend |
| `OAK_PREVIEW_USER` | Shared preview login name |
| `OAK_PREVIEW_PASSWORD` | Random password with a minimum of 16 characters |
| `OAK_LOCAL_PREVIEW` | `true` permits a development bypass. Use `false` for deployment. |

The bypass is disabled in production builds and on Vercel.
Do not put the backend key in a public frontend variable.

## Tests and release

`OAK_TEST_DATABASE_URL` must identify a separate database with a name that ends in `_test`.
Tests erase task data in that database.
See [Tests](tests.md) for the commands.

Release variables and provider secrets are listed in [Deployment](deploy.md).
