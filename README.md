# Oak

**Improve agent reliability by making implicit task relationships explicit.**

This version configures tasks, agents, MCP connections, and each agent's tool access.
The hierarchy is **Task → Agents → Each agent's task surface**.
Inference and ontology construction are later work.

## Stack

| Component | Technology |
| --- | --- |
| Interface | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| API | Python 3.12, FastAPI |
| MCP client | Official Python MCP SDK |
| Production storage | Supabase Postgres and Vault |
| Hosting | Vercel frontend and Render backend |
| Checks and release | GitHub Actions, pytest, Playwright, oasdiff |

MCP means Model Context Protocol. It is the tool interface for this project.
Dependencies are pinned in `backend/uv.lock` and `frontend/package-lock.json`.

## Run locally

Install Python 3.12, Node.js 24, uv 0.12.0, and Docker.
Run these commands from the repository root:

```sh
docker compose up -d
uv sync --project backend --locked
npm ci --prefix frontend
backend/.venv/bin/python backend/scripts/configure_local.py
```

The setup script creates private local configuration files. It does not replace existing files.
To use another local Postgres database, supply `--database-url` to that script.

Start the backend in one terminal:

```sh
cd backend
uv run python -m oak.db
uv run uvicorn oak.main:app --host 127.0.0.1 --port 8047 --no-access-log
```

Start the frontend in another terminal:

```sh
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3047
```

Open [Oak locally](http://localhost:3047).
Create a task, open its MCPs tab, and connect a remote MCP endpoint.
Add an agent. Select its tools and use **Save tools**.

Local development stores encrypted credentials in Postgres with a local Fernet key.
Keep `OAK_LOCAL_SECRET_KEY` with the local database. Losing the key requires reconnecting MCPs.
Production uses Supabase Vault. Production startup rejects local secret storage and local MCP access.

## Access boundaries

- The preview has a shared HTTP Basic access gate. Use a random password of at least 16 characters.
- The backend requires a separate secret API key. Only the frontend server receives this key.
- The demo user switcher is an authentication placeholder. A preview visitor can select either demo identity.
- A new task belongs to the selected demo user. Task members can access every agent in that task.
- Each agent starts with no selected tools. The backend rejects tools from another task.
- A tool is identified by its connection and tool name. Equal names from different MCPs stay distinct.
- Refresh adds catalog entries without granting access. Removed tools stay visible as unavailable.
- Discovery and selection do not execute tools.

Use remote public HTTPS endpoints with Streamable HTTP transport.
Public, bearer token, and SDK-supported OAuth authentication are available.
OAuth uses provider metadata and client registration or Client ID Metadata Documents where supported.
Providers that require manual client registration are outside this initial flow.
Do not put credentials in endpoint URLs. Use the authentication field.
Local command-based MCP servers are deferred.

The preview runs one backend worker. OAuth callbacks are bound to a short-lived state value.
A deployment interrupts pending authorization. Reconnect after an interruption.
Stored credentials and agent selections persist in Postgres across deployments.

## Verify

Use a separate database whose name ends in `_test`. The tests erase its task data.
The Docker setup creates `oak_test` for this purpose.

```sh
export OAK_TEST_DATABASE_URL=postgresql://oak:oak-local-only@127.0.0.1:55432/oak_test
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python -m scripts.export_openapi
cd ../frontend
npm run api:generate
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright starts the production frontend, Python backend, and a controlled MCP server.
It checks onboarding, duplicate tool names, separate agent grants, reload persistence, unavailable tools,
task isolation, authentication recovery, OAuth, keyboard input, and the private access gate.
The MCP fixture counts tool calls. The tests require that count to stay zero.
The local tests use encrypted local storage. Verify Vault access during cloud setup.

After API changes, commit the generated OpenAPI definition and TypeScript types.
CI rejects generated-file drift and breaking changes to the previous API contract.
CI also checks frontend types, lint, Python tests, a production build, and browser acceptance tests.

## Create the private deployment

Use new projects named `oak`, `oak-api`, and `oak-web` in Supabase, Render, and Vercel.
Keep the GitHub repository private.

1. Create a Supabase project named `oak`. Use its direct or session-pooler Postgres connection string with TLS.
2. Create a Render Blueprint from `render.yaml`. Set `OAK_DATABASE_URL` and `OAK_FRONTEND_URL`.
3. Keep the Render service at one instance and one worker. Keep automatic deployment off.
4. Import `frontend` as the root directory of a Vercel Next.js project named `oak-web`. Use Node.js 24.
5. Set the Vercel variables listed below. Keep Git-triggered deployment off as specified in `vercel.json`.
6. Create the GitHub environment `private-preview`. Add the secrets and variables listed below.
7. Require the `checks` status on `main`. The repository includes `.github/branch-protection.json` for the GitHub API.
8. Set the repository variable `OAK_DEPLOY_ENABLED=true` only after project configuration is complete.
9. Merge a passing pull request. Check the release workflow and its smoke check result.

Protected branches on a private repository require an eligible GitHub plan.
On the current free plan, branch protection is pending.
Check for passing CI before each merge. GitHub does not enforce that step on this private repository.

The backend startup command applies migrations before serving requests.
The backend uses `RENDER_EXTERNAL_URL` for its OAuth callback address.
Set `OAK_PUBLIC_API_URL` only when a different public backend address is required.
It enables the Vault extension and stores connection credentials through Vault functions.
Use an appropriately protected backend database account. Do not expose that account to the browser.
Enable the provider's database backups and retain the previous application artifacts.

Vercel environment variables:

| Variable | Value |
| --- | --- |
| `OAK_API_URL` | HTTPS Render API URL, without a trailing slash |
| `OAK_API_KEY` | The same random key configured on Render |
| `OAK_PREVIEW_USER` | Shared preview login name |
| `OAK_PREVIEW_PASSWORD` | Random preview password, at least 16 characters |
| `OAK_LOCAL_PREVIEW` | `false` |

GitHub environment secrets:

- `RENDER_API_KEY`
- `VERCEL_TOKEN`
- `OAK_PREVIEW_USER`
- `OAK_PREVIEW_PASSWORD`
- `OAK_VERCEL_PROTECTION_BYPASS`, if Vercel deployment protection is also enabled

GitHub environment variables:

- `RENDER_SERVICE_ID`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `OAK_API_URL`
- `OAK_FRONTEND_URL`, the canonical production frontend URL

Keep credentials in provider settings and GitHub secrets. Do not put them in issues or source files.
The release workflow runs only after successful main-branch CI.
It deploys the tested backend commit, verifies its health and commit ID, and then deploys the frontend.
The final smoke check tests private access and frontend-to-backend requests.
The `release-<commit>` artifact records previous deployment IDs and the new frontend URL.

Free hosting can stop idle services. An initial request can fail while the backend starts.
The interface provides a retry action. Choose paid hosting only when continuous availability is required.

## Roll back

Set `OAK_DEPLOY_ENABLED=false` before a manual rollback.
Find the last passing release artifact in GitHub Actions.
Restore the previous Vercel production deployment, then restore the previous Render deployment.
Use the IDs from `release.json`. Run the deployed smoke checks again.
Keep previous provider deployment artifacts available. Provider retention limits apply.
The first release has no previous deployment.

Add new database migrations. Do not edit applied migrations.
Use additive changes that work with the previous application release.
Do not remove or rename fields until both releases no longer need them.
CI blocks common destructive operations. Review semantic compatibility before merging.

Provider references: [Python MCP SDK](https://py.sdk.modelcontextprotocol.io/),
[Supabase Vault](https://supabase.com/docs/guides/database/vault),
[Render deployment](https://render.com/docs/deploy-fastapi),
[Render rollback](https://render.com/docs/rollbacks),
[Vercel rollback](https://vercel.com/docs/cli/rollback),
[oasdiff](https://github.com/oasdiff/oasdiff).
