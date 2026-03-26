# Deploy to Azure Container Apps

This guide deploys two services from this repo to Azure Container Apps:
- `trace-api` (FastAPI)
- `studio-ui` (Streamlit)

It does not create resources automatically for you; run the commands manually after replacing placeholders.

## 1) Prerequisites
- Azure CLI installed and authenticated (`az login`)
- Docker installed and authenticated for the registry you choose
- Azure Container Apps CLI extension

```bash
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

Set common variables:

```bash
RESOURCE_GROUP=rg-llm-trace
LOCATION=westeurope
ENVIRONMENT=aca-env-llm-trace
TAG=v1
API_APP=trace-api
UI_APP=studio-ui
```

## 2) Build and push images

### Option A: Azure Container Registry (ACR)
Create ACR and push both images.

```bash
ACR_NAME=<your-acr-name> # globally unique, lowercase

az group create -n "$RESOURCE_GROUP" -l "$LOCATION"
az acr create -n "$ACR_NAME" -g "$RESOURCE_GROUP" --sku Basic
az acr update -n "$ACR_NAME" --admin-enabled true
az acr login -n "$ACR_NAME"

ACR_LOGIN_SERVER=$(az acr show -n "$ACR_NAME" -g "$RESOURCE_GROUP" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show -n "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show -n "$ACR_NAME" --query "passwords[0].value" -o tsv)

docker build -f infra/docker/trace_api.Dockerfile -t "$ACR_LOGIN_SERVER/llm-trace-api:$TAG" .
docker build -f infra/docker/studio_ui.Dockerfile -t "$ACR_LOGIN_SERVER/llm-studio-ui:$TAG" .
docker push "$ACR_LOGIN_SERVER/llm-trace-api:$TAG"
docker push "$ACR_LOGIN_SERVER/llm-studio-ui:$TAG"
```

### Option B: GitHub Container Registry (GHCR)
Use a GitHub PAT with `write:packages` and `read:packages`.

```bash
GHCR_ORG=<github-user-or-org>
GHCR_USER=<github-username>
GHCR_PAT=<github-pat>
GHCR_SERVER=ghcr.io

echo "$GHCR_PAT" | docker login "$GHCR_SERVER" -u "$GHCR_USER" --password-stdin

docker build -f infra/docker/trace_api.Dockerfile -t "$GHCR_SERVER/$GHCR_ORG/llm-trace-api:$TAG" .
docker build -f infra/docker/studio_ui.Dockerfile -t "$GHCR_SERVER/$GHCR_ORG/llm-studio-ui:$TAG" .
docker push "$GHCR_SERVER/$GHCR_ORG/llm-trace-api:$TAG"
docker push "$GHCR_SERVER/$GHCR_ORG/llm-studio-ui:$TAG"
```

## 3) Create Container Apps environment

```bash
az containerapp env create \
  --name "$ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"
```

## 4) Create `trace-api` container app

Pick one registry block.

### ACR image source
```bash
az containerapp create \
  --name "$API_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$ACR_LOGIN_SERVER/llm-trace-api:$TAG" \
  --ingress external \
  --target-port 8000 \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --env-vars TRACE_DB_PATH=/tmp/trace.db REDACT_TEXT=false DATABASE_URL="<postgres-url-placeholder>"
```

### GHCR image source
```bash
az containerapp create \
  --name "$API_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$GHCR_SERVER/$GHCR_ORG/llm-trace-api:$TAG" \
  --ingress external \
  --target-port 8000 \
  --registry-server "$GHCR_SERVER" \
  --registry-username "$GHCR_USER" \
  --registry-password "$GHCR_PAT" \
  --env-vars TRACE_DB_PATH=/tmp/trace.db REDACT_TEXT=false DATABASE_URL="<postgres-url-placeholder>"
```

## 5) Create `studio-ui` container app
First fetch API FQDN, then set `TRACE_API_URL` so UI calls the deployed API.

```bash
API_FQDN=$(az containerapp show -n "$API_APP" -g "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)
```

### ACR image source
```bash
az containerapp create \
  --name "$UI_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$ACR_LOGIN_SERVER/llm-studio-ui:$TAG" \
  --ingress external \
  --target-port 8501 \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --env-vars TRACE_API_URL="https://$API_FQDN"
```

### GHCR image source
```bash
az containerapp create \
  --name "$UI_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$GHCR_SERVER/$GHCR_ORG/llm-studio-ui:$TAG" \
  --ingress external \
  --target-port 8501 \
  --registry-server "$GHCR_SERVER" \
  --registry-username "$GHCR_USER" \
  --registry-password "$GHCR_PAT" \
  --env-vars TRACE_API_URL="https://$API_FQDN"
```

Get public URLs:

```bash
az containerapp show -n "$API_APP" -g "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv
az containerapp show -n "$UI_APP" -g "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv
```

## 6) Persistence guidance (important)
- Use **SQLite only for local/dev**.
- For Azure environments, prefer **Postgres** (for example, Azure Database for PostgreSQL Flexible Server).
- In production, replace the SQLite path approach with a real database connection string (for example `DATABASE_URL`) and migrate persistence code accordingly.
- The `TRACE_DB_PATH=/tmp/trace.db` value above is non-durable container filesystem storage and should not be treated as production persistence.

## 7) Application Insights / Azure Monitor (high-level)
1. Use (or create) a Log Analytics workspace for your Container Apps environment.
2. Create an Application Insights resource linked to that workspace.
3. In each Container App (`trace-api`, `studio-ui`), enable diagnostic settings to send logs/metrics to Azure Monitor / Log Analytics.
4. Use Container Apps log stream for quick troubleshooting and Application Insights/Azure Monitor dashboards for trends and alerting.
5. Add alert rules (error rate, 5xx spikes, latency) from Azure Monitor once baseline traffic exists.
