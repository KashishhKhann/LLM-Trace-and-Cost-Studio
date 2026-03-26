FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY shared /app/shared

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir .

ENV TRACE_DB_PATH=/data/trace.db
ENV REDACT_TEXT=false

EXPOSE 8000

CMD ["uvicorn", "apps.trace_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
