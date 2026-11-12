# Local setup

[Documentation index](README.md)

## Prerequisites

Install Python 3.12, Java 21, Node.js 24, uv 0.12.0, and Docker.
The repository fixes dependency versions in its lockfiles.
Use the repository root as the initial working directory.

The local configuration uses PostgreSQL on port `55432`.
The backend uses port `8047`.
The frontend uses port `3047`.

## Install dependencies

1. Start the local database.

   ```sh
   docker compose up -d
   ```

2. Install the backend dependencies.

   ```sh
   uv sync --project backend --locked
   ```

3. Install the frontend dependencies.

   ```sh
   npm ci --prefix frontend
   ```

4. Create the local configuration.

   ```sh
   backend/.venv/bin/python backend/scripts/configure_local.py
   ```

The script creates `backend/.env` and `frontend/.env.local` with private file permissions.
It stops if either file already exists.
For an existing installation, edit the existing files.
The script accepts `--database-url` for a different local database.

Keep the local encryption key with the database backup.
Without that key, Oak cannot decrypt the saved local credentials.

## Start the application

1. Open a terminal in `backend`.
2. Apply the database migrations.

   ```sh
   uv run python -m oak.db
   ```

3. Start the backend.

   ```sh
   uv run uvicorn oak.main:app --host 127.0.0.1 --port 8047 --no-access-log
   ```

4. Open another terminal in `frontend`.
5. Start the frontend.

   ```sh
   npm run dev -- --hostname 127.0.0.1 --port 3047
   ```

6. Open [the local application](http://localhost:3047).

HermiT uses Java for formal schema verification.
If Java 21 is not on `PATH`, set `OAK_JAVA` to its executable.
For the Homebrew installation, use this command:

```sh
export OAK_JAVA=/opt/homebrew/opt/openjdk@21/bin/java
```

## Configure model access

The backend uses the Google Gen AI software development kit (SDK) with Vertex AI.
Application Default Credentials (ADC) supply credentials on the backend host.
The backend does not use the example's command-line interface login.

1. Configure ADC on the backend host.

   ```sh
   gcloud auth application-default login
   ```

2. Return to the repository root.
3. Replace `PROJECT_ID` with the Google Cloud project identifier.
4. Add the local model settings.

   ```sh
   backend/.venv/bin/python backend/scripts/configure_gemini.py --project PROJECT_ID --check-budget 0.10
   ```

5. Examine existing model settings in `backend/.env`.
6. Restart the backend.

The script adds missing settings. It does not replace existing values.
It can also obtain the project from the local example profile if `--project` is absent.
The application reads the saved settings, not the example profile.

The command permits connection checks up to a separate USD 0.10 allowance.
It does not make a model call.
The **Check connection** button makes that call.
Discovery and training use separate run allowances.

See [Settings](settings.md) for the configured model and limits.
See the [User guide](use.md) for the first task.

## Resolve setup problems

| Symptom | Action |
| --- | --- |
| Database connection fails | Make sure that PostgreSQL uses the configured host and port. |
| Configuration already exists | Edit the existing files. |
| Java is unavailable | Set `OAK_JAVA` to a Java 21 executable. |
| Model authentication fails | Renew ADC on the backend host. |
| Connection check allowance is zero | Set the necessary allowance in `backend/.env`. |
| Private preview rejects access | Use the saved preview credentials. |
| Tool authorization was interrupted | Reconnect the affected Model Context Protocol (MCP) server. |

The local preview bypass applies only to development.
Production builds use the preview access gate.
