# Private deployment

[Documentation index](README.md)

The repository configures a private preview with a Vercel frontend and a Render backend.
Supabase PostgreSQL stores application data.
Supabase Vault stores production credentials.
The current preview uses demo identities behind a shared access gate.

## Resource check

Keep deployment disabled until the resource check passes on native Linux AMD64.
An emulated result from another host architecture does not satisfy this condition.
No passing native result is recorded in [Tests](tests.md#recorded-validation).
The earlier emulated run exceeded the verifier's 30-second deadline at maximum schema size.

Execute this command from `backend` on the necessary host:

```sh
.venv/bin/python -m scripts.check_reasoner_resources
```

The command builds the service image and creates temporary service and database containers.
It limits the complete service container to 512 MiB and 0.1 CPU.
It sends API requests during formal schema verification at the supported declaration limits.
It removes its temporary containers and network after the check.
A passing report returns exit code zero.

API means application programming interface.
The verifier uses a 128 MiB Java heap and a 30-second deadline.
The backend permits one formal verification process at a time.

## Provider setup

The configuration sources are [render.yaml](../render.yaml), [vercel.json](../frontend/vercel.json), and the [release workflow](../.github/workflows/deploy.yml).
Use project names `oak`, `oak-api`, and `oak-web` for Supabase, Render, and Vercel.

1. Create the Supabase project.
2. Obtain its direct or session-pooler database address with Transport Layer Security (TLS).
3. Create the Render service from `render.yaml`.
4. Set `OAK_DATABASE_URL` and `OAK_FRONTEND_URL` on Render.
5. Keep one service instance and one backend worker.
6. Keep automatic Render deployment off.
7. Create the Vercel project with `frontend` as its root directory.
8. Select Node.js 24 for the Vercel project.
9. Set the frontend variables below.
10. Keep Git-triggered Vercel deployment off.
11. Configure model credentials on the backend host.

The backend image supplies Python 3.12 and Java 21.
Startup applies migrations before it starts the API worker.
Render supplies the public callback address through `RENDER_EXTERNAL_URL`.
Use `OAK_PUBLIC_API_URL` only when the necessary public address differs.

Local Application Default Credentials (ADC) do not configure the hosted backend.
Configure provider model access and credentials separately on the hosted backend.
See [Settings](settings.md) for the model policy.

| Vercel variable | Value |
| --- | --- |
| `OAK_API_URL` | Public backend HTTPS URL without a trailing slash |
| `OAK_API_KEY` | Same private key as the backend |
| `OAK_PREVIEW_USER` | Shared preview login name |
| `OAK_PREVIEW_PASSWORD` | Random password with a minimum of 16 characters |
| `OAK_LOCAL_PREVIEW` | `false` |

HTTP means Hypertext Transfer Protocol.
HTTPS means HTTP over TLS.
Keep provider credentials in provider settings and GitHub secrets.
Do not put them in source files or issue text.

## GitHub release setup

1. Keep the repository private.
2. Create the `private-preview` GitHub environment.
3. Add its secrets and variables from the tables below.
4. Configure the necessary CI checks where repository protection permits them.
5. Enable provider database backups.
6. Keep the previous provider deployment artifacts.
7. Confirm that all necessary checks pass for the intended release commit.
8. After setup and the resource check pass, set `OAK_DEPLOY_ENABLED=true`.

CI means continuous integration.
The repository includes a [branch protection configuration](../.github/branch-protection.json).
Do not assume that the presence of this file enables provider enforcement.

| Environment secret | Purpose |
| --- | --- |
| `RENDER_API_KEY` | Backend deployment access |
| `VERCEL_TOKEN` | Frontend deployment access |
| `OAK_PREVIEW_USER` | Smoke test login name |
| `OAK_PREVIEW_PASSWORD` | Smoke test password |
| `OAK_VERCEL_PROTECTION_BYPASS` | Optional provider protection bypass for the smoke test |

| Environment variable | Purpose |
| --- | --- |
| `RENDER_SERVICE_ID` | Backend service identifier |
| `VERCEL_ORG_ID` | Frontend organization identifier |
| `VERCEL_PROJECT_ID` | Frontend project identifier |
| `OAK_API_URL` | Public backend address |
| `OAK_FRONTEND_URL` | Canonical production frontend address |

`OAK_DEPLOY_ENABLED` is the repository release switch.
The release workflow starts only after successful CI from a push to `main` in the same repository.
The commit that passed CI must also remain at `origin/main`.
It deploys the backend first and validates its health and release identifier.
It then deploys the frontend and does the private access smoke test.

The `release-<commit>` artifact contains `release.json` and `release-url.txt`.
These files record deployment results and available rollback targets.

## Rollback

1. Set `OAK_DEPLOY_ENABLED=false`.
2. Find the last passing release artifact.
3. Read the previous deployment identifiers in `release.json`.
4. Restore the previous Vercel production deployment.
5. Restore the previous Render deployment.
6. Repeat the deployed smoke checks.

The first release has no previous deployment.
Provider artifact retention determines which rollback targets remain available.

Add new database migrations for schema changes.
Do not edit migrations that a database already applied.
Keep each migration compatible with the previous application release.
Application rollback does not reverse a database migration automatically.
