# AGENTS.md

## Project Goal
- Build the **LLM Trace + Cost Studio** MVP:
  - FastAPI trace API
  - Streamlit UI
  - Local SQLite storage

## Scope Guardrails
- Keep scope minimal, production-shaped, and testable.
- Do not add fancy authentication.
- Do not add multi-tenant RBAC.
- Do not integrate external SaaS dependencies for core MVP behavior.

## Runtime and Dependencies
- Use Python 3.11 or newer.
- Prefer Python standard library where practical.
- Keep third-party dependencies minimal.

## Required Repository Structure
- `apps/trace_api`
- `apps/studio_ui`
- `shared`
- `tests`
- `infra/docker`

## Quality and Tooling
- Use `ruff` for linting.
- Use `pytest` for tests.

## Workflow Rules
- Make small, high-confidence changes.
- Avoid refactors unless they are necessary to complete the task safely.
- Always run tests after changes.
- Always note the exact commands used to validate changes.
- If requirements are ambiguous, ask 2-4 clarifying questions before coding.
