FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY shared /app/shared

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir .

ENV TRACE_API_URL=http://trace_api:8000

EXPOSE 8501

CMD [
  "streamlit",
  "run",
  "apps/studio_ui/app.py",
  "--server.address=0.0.0.0",
  "--server.port=8501"
]
