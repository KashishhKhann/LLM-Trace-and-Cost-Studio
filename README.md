# LLM Trace + Cost Studio

A lightweight observability MVP for LLM applications. Ingest call traces from any app, browse them with filters, and track token usage and cost over time.

Built with FastAPI (backend), Streamlit (frontend), and SQLite (storage). No external database required.

## What it does

Each ingested trace captures: app name, provider, model, token counts, latency, success/error status, optional prompt/response previews, and nested timing spans. The UI exposes three pages:

- **Overview** — aggregate metrics (calls, error rate, p50/p95 latency, total tokens, cost) for a configurable date range
- **Calls list** — filterable, paginated table; click any row to drill in
- **Call detail** — full JSON payload, per-span timing breakdown, and a JSON download

## Quickstart

```bash
pip install -e ".[dev]"

# Backend (port 8000)
TRACE_DB_PATH=./trace.db REDACT_TEXT=false uvicorn apps.trace_api.main:app --reload

# Frontend (port 8501)
streamlit run apps/studio_ui/app.py
```

Or run both with Docker:

```bash
docker compose up --build
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Readiness check |
| POST | `/ingest/llm_call` | Ingest a trace |
| GET | `/calls` | List calls with filters and pagination |
| GET | `/calls/{id}` | Fetch one call with spans |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRACE_DB_PATH` | `./trace.db` | SQLite file path |
| `REDACT_TEXT` | `false` | Redact prompt/response previews |
| `TRACE_API_URL` | `http://localhost:8000` | Backend URL used by the UI |

## Lint and tests

```bash
python3 -m ruff check .
python3 -m pytest -q
```

## Project structure

```
apps/
  trace_api/       # FastAPI backend
    main.py        # Routes
    db/sqlite.py   # Persistence layer
  studio_ui/       # Streamlit frontend
    app.py
    client.py      # API client + metrics helpers
    pages/         # Overview, Calls list, Call detail
shared/
  schemas.py       # Pydantic models shared by backend and tests
  cost.py          # Token cost estimation
  redaction.py     # Preview redaction
tests/             # pytest suite (schema, cost, DB, API endpoint tests)
infra/
  docker/          # Dockerfiles for both services
  azure/           # Azure Container Apps deployment notes
```

## Design notes

- SQLite keeps the setup simple — no external service needed. The Azure deployment guide (`infra/azure/containerapps.md`) recommends switching to Postgres for production.
- The UI loads all matching calls into memory; fine for small datasets, not for large ones.
- Text redaction covers only `prompt_preview` and `response_preview`, not metadata or spans.
- Cost figures use a small in-memory pricing table in `shared/cost.py` — update it to match your actual provider rates.
