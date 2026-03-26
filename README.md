# LLM Trace + Cost Studio

This repository is a small MVP with three moving parts:

- A FastAPI backend that accepts and serves trace records
- A Streamlit frontend that reads those records and displays simple metrics
- A local SQLite database used as the persistence layer

The project is intentionally minimal. It is not trying to be a full observability platform yet. Most files exist either to define the core data contract, move that data through the backend, display it in the UI, or prove the behavior with tests.

## What the app does

At a high level, the system stores information about individual LLM calls.

Each call includes fields such as:

- which app produced it
- which provider and model were used
- token counts
- latency
- success or error status
- small prompt/response previews
- optional metadata and spans

The backend exposes four endpoints:

- `GET /health`
- `POST /ingest/llm_call`
- `GET /calls`
- `GET /calls/{id}`

The frontend calls those endpoints to show:

- an overview page with aggregate metrics
- a calls list page with filters
- a call detail page for one specific trace

## How the request flow works

### 1. Ingest flow: `POST /ingest/llm_call`

1. FastAPI receives the request in `apps/trace_api/main.py`.
2. The body is validated against `shared/schemas.py` using Pydantic.
3. Optional redaction is applied by `shared/redaction.py` if `REDACT_TEXT=true`.
4. Cost is estimated by `shared/cost.py` using a small in-memory pricing table.
5. The backend adds server-generated fields:
   - `id`
   - `ts_server`
   - `cost_usd`
6. The completed record is stored by `apps/trace_api/db/sqlite.py`.
7. FastAPI returns the stored record summary to the caller.

### 2. List flow: `GET /calls`

1. FastAPI parses query parameters such as time range, model, status, and pagination.
2. `main.py` builds a filter dictionary.
3. `sqlite.py` converts that dictionary into a SQL `WHERE` clause.
4. SQLite returns matching calls ordered by newest first.
5. FastAPI responds with:
   - `total`
   - `items`

### 3. Detail flow: `GET /calls/{id}`

1. FastAPI asks `sqlite.py` for one call by ID.
2. `sqlite.py` loads the call row and its related span rows.
3. The database rows are converted back into Pydantic objects.
4. FastAPI returns the full stored call, including spans.

### 4. UI flow

1. Streamlit starts at `apps/studio_ui/app.py`.
2. The user navigates to one of the pages in `apps/studio_ui/pages/`.
3. Each page uses helper functions in `apps/studio_ui/client.py`.
4. `client.py` makes HTTP GET requests to the FastAPI backend.
5. The page renders either metrics, a table, or the raw call JSON.

## Repository structure

```text
.
|-- .github/workflows/ci.yml
|-- AGENTS.md
|-- README.md
|-- apps
|   |-- studio_ui
|   |   |-- app.py
|   |   |-- client.py
|   |   `-- pages
|   |       |-- 1_Overview.py
|   |       |-- 2_Calls_List.py
|   |       `-- 3_Call_Detail.py
|   `-- trace_api
|       |-- main.py
|       `-- db
|           `-- sqlite.py
|-- docker-compose.yml
|-- infra
|   |-- azure/containerapps.md
|   `-- docker
|       |-- studio_ui.Dockerfile
|       `-- trace_api.Dockerfile
|-- pyproject.toml
|-- shared
|   |-- cost.py
|   |-- redaction.py
|   `-- schemas.py
`-- tests
    |-- test_cost.py
    |-- test_db_sqlite.py
    |-- test_schemas.py
    |-- test_smoke.py
    `-- test_trace_api_endpoints.py
```

## File-by-file explanation

This section focuses on repository files that matter to development. Generated cache files such as `__pycache__`, `.pytest_cache`, and `.ruff_cache` are described separately because they are not hand-maintained source files.

### Top-level files

#### `AGENTS.md`

This is an instruction file for coding agents working in the repo. It does not affect runtime behavior of the application itself. Its job is to define:

- the project goal
- scope guardrails
- required directory layout
- tooling expectations such as `ruff` and `pytest`
- workflow rules like "make small changes" and "run tests after changes"

Relevance: this file matters during development, not during application execution.

#### `README.md`

This file is the human entry point to the repo. Its job is to explain what the project is, how to run it, and where to look when making changes.

Relevance: onboarding and maintenance. It is not imported by Python, but it is part of the package metadata because `pyproject.toml` points to it as the project `readme`.

#### `pyproject.toml`

This is the single Python project configuration file. It controls packaging metadata, dependencies, and tooling configuration.

What each section does:

- `[build-system]`
  - tells Python packaging tools to use `setuptools`
- `[project]`
  - defines project metadata such as name, version, description, and minimum Python version
  - defines runtime dependencies:
    - `fastapi`
    - `pydantic`
    - `streamlit`
    - `uvicorn`
- `[project.optional-dependencies]`
  - defines the `dev` extras:
    - `httpx`
    - `pytest`
    - `ruff`
- `[tool.setuptools]`
  - currently sets `packages = []`
  - this means the project is not packaged in the normal "discover all packages" way
- `[tool.ruff]` and `[tool.ruff.lint]`
  - define linting behavior
- `[tool.pytest.ini_options]`
  - define pytest defaults

Relevance: this file is central because install, lint, and test behavior all depend on it.

#### `docker-compose.yml`

This file defines how to run both services together with Docker Compose.

It creates:

- `trace_api`
  - builds from `infra/docker/trace_api.Dockerfile`
  - exposes port `8000`
  - sets `TRACE_DB_PATH` and `REDACT_TEXT`
  - mounts a named volume for SQLite persistence
- `studio_ui`
  - builds from `infra/docker/studio_ui.Dockerfile`
  - exposes port `8501`
  - sets `TRACE_API_URL` to talk to the backend service by container name
- `trace_db`
  - named Docker volume used by the API container

Relevance: local multi-container startup.

### CI and automation

#### `.github/workflows/ci.yml`

This is the GitHub Actions pipeline.

What it does:

1. Runs on every push and pull request
2. Checks out the repo
3. Installs Python 3.11
4. Installs the project with dev dependencies
5. Runs `ruff check .`
6. Runs `pytest -q`

Relevance: this is the repo's automated quality gate.

### Backend files

#### `apps/trace_api/main.py`

This is the FastAPI entry point. If you want to understand how HTTP requests are handled, start here.

Key functions:

- `_env_bool(name, default=False)`
  - converts environment variables such as `REDACT_TEXT` into booleans
- `_db_path()`
  - decides where the SQLite file lives using `TRACE_DB_PATH`
- `create_app()`
  - constructs the FastAPI application
  - defines application startup behavior
  - registers all routes

Important runtime behavior inside `create_app()`:

- It uses a FastAPI lifespan handler to call `init_db(...)` on startup.
- That ensures the database file and tables exist before requests are handled.

Routes:

- `GET /health`
  - returns `{"status": "ok"}`
  - used as a simple readiness check
- `POST /ingest/llm_call`
  - validates incoming JSON as `LLMCallIngest`
  - optionally redacts prompt/response previews
  - calculates a cost estimate
  - assigns a UUID and current UTC server timestamp
  - writes the record to SQLite
  - returns an `LLMCallIngestResponse`
- `GET /calls`
  - accepts query filters and pagination
  - translates query params into a plain `filters` dictionary
  - asks the DB layer for matching rows and total count
- `GET /calls/{id}`
  - fetches a single stored call with its spans
  - returns 404 if the call does not exist

Why this file matters:

- it is the backend control plane
- it stitches together schemas, redaction, cost estimation, and storage
- changes to API contract usually start here

#### `apps/trace_api/db/sqlite.py`

This is the persistence layer. It contains all SQLite-specific logic.

Global state:

- `_DB_PATH`
  - stores the configured database path after initialization
  - all DB operations depend on this being set first

Important functions:

- `init_db(db_path)`
  - sets `_DB_PATH`
  - creates the parent directory if needed
  - creates tables and indexes if they do not already exist
- `insert_llm_call(call)`
  - inserts one call into `llm_calls`
  - inserts any related spans into `spans`
- `list_llm_calls(filters, limit, offset)`
  - validates pagination arguments
  - builds a SQL filter clause
  - returns matching items and a total count
- `get_llm_call(call_id)`
  - loads one call row and all child spans
- `_connect()`
  - opens a SQLite connection and enables foreign keys
- `_build_where_clause(filters)`
  - converts a Python filter dictionary into SQL fragments and parameters
- `_normalize_ts(value)`
  - normalizes date inputs to strings before sending them to SQL
- `_loads_json(raw)` and `_dumps_json(value)`
  - convert Python dicts to JSON strings and back
- `_row_to_span(row)`
  - reconstructs a `LLMCallIngestSpan` from a database row
- `_row_to_call(row, include_spans, spans=None)`
  - reconstructs a `LLMCallStored` from a database row

Database schema:

- `llm_calls`
  - one row per traced LLM call
  - stores timestamps, model info, latency, cost, previews, and metadata
- `spans`
  - one row per nested timing span attached to a call
  - linked to `llm_calls` by `call_id`

Notable implementation details:

- metadata is stored as JSON text in SQLite
- `error_type` is duplicated into a dedicated column when present in metadata
- spans store `latency_ms` inside `meta_json` under a private key `__latency_ms`
  - this is a design shortcut because the table does not have a dedicated `latency_ms` column
- the database layer returns Pydantic models, not raw dicts

Why this file matters:

- it is the source of truth for persistence behavior
- any storage bug, schema change, or filtering change will go through this file

### Shared domain files

#### `shared/schemas.py`

This file defines the data contract shared across the backend and tests.

Classes:

- `LLMCallIngestSpan`
  - a single nested span with a name, optional latency, and optional metadata
- `LLMCallIngest`
  - the request body accepted by the ingest endpoint
  - includes required fields for trace identity and performance data
  - includes optional fields such as prompt/response preview, client timestamp, metadata, and spans
- `LLMCallStored`
  - extends `LLMCallIngest`
  - adds storage-level fields:
    - `id`
    - `ts_server`
    - `cost_usd`
- `LLMCallIngestResponse`
  - the response model for the ingest endpoint
  - returns top-level summary fields plus the stored object

Validation behavior:

- token counts and latency must be non-negative
- `cost_usd` must be non-negative
- Pydantic converts ISO timestamp strings into `datetime` objects

Why this file matters:

- it defines what the API accepts and returns
- it prevents backend and tests from drifting into different assumptions

#### `shared/cost.py`

This file contains the cost estimation logic.

Main contents:

- `PRICING`
  - a nested dictionary of placeholder pricing values
  - keyed by provider and model in lowercase
- `estimate_cost_usd(provider, model, tokens_in, tokens_out)`
  - looks up pricing
  - calculates input and output cost per 1K tokens
  - rounds the result
  - logs a warning and returns `0.0` if pricing is missing

Why this file matters:

- cost calculation is intentionally simple and isolated here
- if pricing rules change, this is the single place to update

#### `shared/redaction.py`

This file contains the text redaction behavior.

Main contents:

- `REDACTED_TEXT`
  - constant placeholder string used when redaction is enabled
- `redact_text(value, enabled)`
  - returns the original string unless redaction is enabled
- `redact_llm_call_payload(payload, enabled)`
  - copies the ingest payload while replacing:
    - `prompt_preview`
    - `response_preview`

Important limitation:

- only the preview fields are redacted
- metadata and span metadata are not redacted

Why this file matters:

- it isolates privacy-related behavior from endpoint logic

### Frontend files

#### `apps/studio_ui/app.py`

This is the Streamlit landing page.

What it does:

- sets page title and wide layout
- displays the configured backend URL
- tells the user to navigate using the sidebar

Relevance:

- minimal shell page
- the real functionality lives in the pages under `apps/studio_ui/pages/`

#### `apps/studio_ui/client.py`

This file is the frontend's API client and utility layer.

Constants and exceptions:

- `DEFAULT_TRACE_API_URL`
  - fallback backend URL for local development
- `ApiError`
  - generic UI-facing API failure
- `NotFoundError`
  - more specific error for HTTP 404

Main functions:

- `get_trace_api_url()`
  - reads `TRACE_API_URL` from the environment
- `get_call(call_id)`
  - fetches one call's JSON payload
- `fetch_all_calls(filters=None, limit=200)`
  - repeatedly calls `/calls`
  - keeps paginating until every page has been loaded
- `build_date_filters(date_range)`
  - converts Streamlit date input into backend query parameters
- `compute_overview_metrics(items)`
  - calculates aggregate metrics for the overview page

Private helpers:

- `_normalize_date_range(value)`
  - cleans up single-date or two-date selections
- `_percentile(values, q)`
  - computes percentiles without NumPy or pandas
- `_get_json(path, params=None)`
  - builds the URL
  - removes empty query params
  - performs a GET request using the standard library `urllib`
  - translates HTTP and network failures into `ApiError` subclasses
  - parses JSON responses

Why this file matters:

- all Streamlit pages depend on it
- it centralizes API communication and shared frontend calculations

#### `apps/studio_ui/pages/1_Overview.py`

This page shows the simplest dashboard view.

What it does:

- defaults to the last 7 days
- asks the backend for all calls in that range
- computes:
  - total calls
  - error rate
  - p50 latency
  - p95 latency
  - total tokens
  - total cost
- displays the results using Streamlit metric cards

Important behavior:

- it stops the page immediately if the API request fails
- it shows an info message if no calls match the range

Relevance:

- this page demonstrates the main summary use case for the product

#### `apps/studio_ui/pages/2_Calls_List.py`

This page shows a filterable list of calls.

What it does:

- provides filters for:
  - date range
  - status
  - model
  - session ID
- fetches all matching calls
- flattens selected fields into rows
- creates a pandas DataFrame for display
- attempts to use Streamlit row selection when available
- falls back to a plain table if that API is unavailable
- lets the user navigate to the detail page for a selected call

Important behavior:

- it stores the selected call ID in Streamlit query params
- it uses `st.switch_page(...)` to move to the detail page

Relevance:

- this is the main investigation page for browsing many traces

#### `apps/studio_ui/pages/3_Call_Detail.py`

This page shows one call in detail.

What it does:

- reads `call_id` from the query string when present
- lets the user type a call ID manually
- fetches the full call JSON
- renders the raw payload
- extracts spans into a tabular timing breakdown
- computes what percentage of total call latency each span represents
- offers a JSON download button

Important behavior:

- returns a user-friendly error for missing calls
- handles other API/network errors separately

Relevance:

- this page is the best place to understand the stored data shape from the UI side

### Test files

#### `tests/test_smoke.py`

This is a minimal sanity check that asserts `True`.

Relevance:

- almost no behavioral value
- mainly proves that pytest can discover and run tests

#### `tests/test_schemas.py`

This file tests Pydantic validation rules for ingest payloads.

What it checks:

- a valid payload is accepted
- each required field is actually required

Relevance:

- protects the API contract at the schema level

#### `tests/test_cost.py`

This file tests the cost calculator.

What it checks:

- known provider/model pricing returns the expected number
- unknown pricing returns `0.0`
- missing pricing also emits a warning log

Relevance:

- locks down the current pricing behavior

#### `tests/test_db_sqlite.py`

This file tests the SQLite persistence layer directly without going through HTTP.

What it checks:

- `init_db()` creates the expected tables and indexes
- calls and spans can be inserted and read back
- filtering and pagination work
- missing IDs return `None`

Relevance:

- this is the main protection for the storage layer

#### `tests/test_trace_api_endpoints.py`

This file tests the backend through FastAPI's test client.

What it checks:

- ingest works end to end
- computed cost appears in the response
- filtering by status and model works at the API level
- missing detail IDs return 404

Important detail:

- the test uses a temporary SQLite file via `TRACE_DB_PATH`
- it also sets `REDACT_TEXT=false`

Relevance:

- this is the main contract test for the HTTP API

### Infrastructure files

#### `infra/docker/trace_api.Dockerfile`

This file builds the FastAPI container image.

What it does:

- starts from `python:3.11-slim`
- sets Python runtime flags
- copies `pyproject.toml`, `README.md`, `apps`, and `shared`
- installs the project into the image
- sets default env vars for SQLite path and redaction
- exposes port `8000`
- starts `uvicorn`

Relevance:

- containerized backend runtime definition

#### `infra/docker/studio_ui.Dockerfile`

This file builds the Streamlit container image.

What it does:

- starts from `python:3.11-slim`
- copies the same project files as the backend image
- installs the project
- sets `TRACE_API_URL` to the compose service name
- exposes port `8501`
- starts Streamlit

Relevance:

- containerized frontend runtime definition

#### `infra/azure/containerapps.md`

This is a manual deployment guide for Azure Container Apps.

What it contains:

- prerequisites for Azure CLI and extensions
- ACR and GHCR build/push instructions
- commands to create the Container Apps environment
- commands to create the backend and frontend apps
- notes on env vars and monitoring
- a recommendation to use Postgres in Azure instead of SQLite

Relevance:

- deployment guidance only
- it is not enforced by code

### Placeholder files

#### `apps/trace_api/.gitkeep`
#### `apps/studio_ui/.gitkeep`
#### `shared/.gitkeep`
#### `infra/docker/.gitkeep`

These files exist so Git can preserve otherwise-empty directories.

Relevance:

- organizational only
- no runtime effect

## Generated and cache files

These files are not part of the core design and usually should not be edited manually:

- `__pycache__/*`
  - compiled Python bytecode generated automatically
- `.pytest_cache/*`
  - pytest cache and test run metadata
- `.ruff_cache/*`
  - linting cache for Ruff
- `.git/*`
  - Git repository internals

If you are trying to understand the codebase, you can ignore these.

## Key concepts and why they matter

### Why `shared/` exists

`shared/` prevents the backend and tests from each inventing their own data shape. It is the closest thing this repo has to a domain layer.

### Why SQLite was chosen

SQLite keeps the MVP simple:

- no external database service
- no connection management complexity
- easy local setup

The tradeoff is that migrations, concurrency, and production durability are limited compared with a server database.

### Why the UI uses `urllib` instead of `requests`

The code prefers the Python standard library where practical, which matches the repo guidance to keep dependencies minimal.

### Why tests are split by concern

- schema tests validate data shape
- cost tests validate math and logging
- DB tests validate storage details
- API tests validate HTTP contract

That keeps failures more specific and easier to debug.

## Important limitations and design shortcuts

These are the main things to be aware of before extending the project:

- `pyproject.toml` uses `packages = []`
  - the project works from the source tree, but it is not packaged in the usual multi-package way
- SQLite schema changes do not have migrations
  - if the schema changes later, upgrade handling will need to be added
- the `spans` table has `start_ts` and `end_ts` columns, but the schema objects do not currently expose them
  - span latency is stored indirectly inside JSON metadata using `__latency_ms`
- redaction is limited
  - only `prompt_preview` and `response_preview` are redacted
- the UI loads all matching calls into memory for overview and list pages
  - acceptable for a small MVP, but it will not scale well
- UI behavior does not have dedicated tests
  - the current tests focus on backend and shared logic
- the Azure deployment guide mentions a future Postgres direction, but the runtime code today is SQLite-only

## Where to make changes

If you want to change a specific behavior, start here:

- add or change API endpoint:
  - `apps/trace_api/main.py`
- change stored fields or SQLite queries:
  - `apps/trace_api/db/sqlite.py`
- change request or response shape:
  - `shared/schemas.py`
- change redaction behavior:
  - `shared/redaction.py`
- change cost estimation:
  - `shared/cost.py`
- change overview or list logic:
  - `apps/studio_ui/client.py`
  - `apps/studio_ui/pages/1_Overview.py`
  - `apps/studio_ui/pages/2_Calls_List.py`
- change detail page behavior:
  - `apps/studio_ui/pages/3_Call_Detail.py`
- update test expectations:
  - files under `tests/`

## Local development

1. Create and activate a Python 3.11+ virtual environment.
2. Install the project and dev dependencies:

```bash
pip install -e ".[dev]"
```

3. Run lint and tests:

```bash
python3 -m ruff check .
python3 -m pytest -q
```

4. Start the backend:

```bash
TRACE_DB_PATH=./trace.db REDACT_TEXT=false uvicorn apps.trace_api.main:app --reload
```

5. Start the frontend:

```bash
streamlit run apps/studio_ui/app.py
```

## Docker

Run both services together:

```bash
docker compose up --build
```

Endpoints:

- Trace API: `http://localhost:8000`
- Studio UI: `http://localhost:8501`

## Validation commands used for this documentation update

- `python3 -m ruff check .`
- `python3 -m pytest -q`
