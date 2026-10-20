# Standalone setup

## Viewer and software contracts

Python 3.12 is the verified interpreter family. From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -c constraints-native.txt -r requirements.txt
.venv/bin/python -m pytest -q
```

The default server and standalone HTML use the public metadata projection. They do not require AppWorld, provider credentials, the original workspace, or an existing SQLite database.

## Native runtime and task data

The native environment is an optional additional installation. Install Git and Git LFS first. `scripts/setup_native.py` creates a new `.vendor/appworld` checkout at `42b5bcf3cd334fee33f0c37c02070a9f5807add5`, applies the one-line injected-model patch, installs both native packages with historical version constraints and unpacks the protected code locally. It never resets an existing checkout.

```sh
.venv/bin/python scripts/setup_native.py
mkdir -p .runtime/appworld
cd .runtime/appworld
../../.venv/bin/appworld download data
cd ../..
```

Upstream data availability and its download credentials are governed by AppWorld. Nothing in this repository replaces the official download. `APPWORLD_DATA_DIR` must point to the resulting `data/` directory. You can instead configure an existing independently installed, pinned native runtime using the paths in `.env.example`.

Run only the native software mechanics checks:

```sh
.venv/bin/python -m pytest -q -o addopts= -m native
```

These use a local AppWorld instance to verify alias denial, native date parsing and function-call capture. They use no acting model and do not count as new experimental task results.

## Inspect detailed historical evidence

```sh
.venv/bin/python scripts/open_detailed_evidence.py
```

Open the printed HTML path in a browser. This explicitly decrypts the sanitized historical bundle into gitignored `private-evidence/`; it does not run a model. The bundle uses AppWorld's encryption helper and published distribution constants, which prevent accidental plaintext indexing rather than providing access control. Do not publish the decrypted folder, screenshots containing task data, or its HTML source.

## Explicit live demonstration

Set up Vertex Application Default Credentials through your own Google Cloud account. Copy `.env.example` to a private `.env`, set `GOOGLE_CLOUD_PROJECT`, and explicitly source it. Project, location, model, source/data directories, output world and records directory are configurable. No provider key is bundled.

```sh
set -a
. ./.env
set +a
cd experiments/appworld-ontology
../../.venv/bin/python engine.py new-training-demo expressions
```

This command deliberately makes real model calls and runs the original initial-construction demonstration on the pinned train task. It is a new development attempt, not a reroll that replaces historical results. Use a fresh session identity and isolated `OWB_RECORDS_DIR`. V2 and v3 historical revision scripts require their parent private records and are preserved as study code, not standalone cold-start commands.

To operate the dashboard against your explicitly created private run store, set `OWB_ENABLE_LIVE=1` and start `server.py`. Otherwise it always serves published read-only evidence. The live UI still blocks rerolling a conclusive attempt.

Generated functions and the restricted REPL are not an adversarial security sandbox. Structural checks are not a formal semantic proof. No OWL/HermiT execution is claimed.
