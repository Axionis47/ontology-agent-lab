# Live behavior stress test

This runner uses the current Oak application runtime.
It creates one research task and one agent in a separate local database.
It compares ordinary ReAct with an accepted ontology on four new requests.
ReAct is the existing reasoning and tool-call loop.
The report contains answers and execution evidence. It has no scores or rankings.

The Model Context Protocol (MCP) server reads three public sources:

- [Open-Meteo](https://open-meteo.com/en/docs) supplies weather forecasts.
- [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/) supplies product records.
- [Open Library](https://openlibrary.org/developers/api) supplies book records and links.

The adapters retain original response bodies and timestamps.
They preserve source identifiers, missing fields, null values, and decimal values.
They do not select task answers or supply ontology declarations.
Matching requests reuse responses within training or one comparison pair.
Each pair has a separate cache. Each agent episode starts with fresh context.

## Run

Run these commands from `backend`.
The local Postgres service and the existing backend model configuration must be available.

Run the local checks:

```sh
.venv/bin/python -m pytest -q examples/behavior_stress
```

Check the public sources without model calls:

```sh
.venv/bin/python -m examples.behavior_stress.run \
  --output .local/behavior-stress/source-check
```

Run the live test:

```sh
OAK_DATABASE_URL=postgresql://oak:oak-local-only@127.0.0.1:55432/oak \
.venv/bin/python -m examples.behavior_stress.run \
  --output .local/behavior-stress/live-run \
  --database oak_behavior_live_test \
  --live
```

This connection uses the repository's local Docker database settings.
Supply your local connection through `OAK_DATABASE_URL` if those settings differ.

The live command creates the named database and applies the existing migrations.
It refuses an existing database or output run. It does not erase existing data.
Each new live command has its own allowance and can incur another USD 10.
Use `--date YYYY-MM-DD` to fix the request date explicitly.
The default date uses `America/New_York`.

The total model-cost allowance is USD 10.
Discovery has USD 2. Training has USD 4.
Each of the eight comparison episodes has USD 0.50.
The runner records a reservation before each model call.
Unknown usage retains that reservation. Calls are not retried automatically.
The cost ledger uses the conservative token rates in the current Oak runtime.
It is an estimate, not a provider invoice.

## Inspect

Open `report.html` in the output directory.
The report links to source checks, discovery, training, requests, and the cost ledger.
Each comparison links to its full recorded episode.
The `sources` directory contains original public responses.
The `model-calls` directory contains recorded model requests, responses, and errors.

If discovery or training does not produce an accepted ontology, ontology episodes stay blocked.
The runner still attempts the four new baseline requests.
It does not supply a manual ontology or change the internal training evaluator.
It does not repair the runtime after a task failure.

Rebuild a report from saved evidence without model calls:

```sh
.venv/bin/python -m examples.behavior_stress.run \
  --output .local/behavior-stress/live-run --report-only
```
