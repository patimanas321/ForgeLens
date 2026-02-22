#!/usr/bin/env bash
set -euo pipefail

# Low-cost deployment fallback: Azure Container Apps (Consumption)
# Usage:
#   ./deploy_containerapp.sh [resource-group] [location] [app-name]

RG_NAME="${1:-rg-forgelens}"
LOCATION="${2:-eastus}"
APP_NAME="${3:-forgelens-ca}"
ENV_NAME="cae-forgelens"
AI_NAME="appi-forgelens"
TARGET_PORT="8000"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$PROJECT_DIR"

echo "[1/10] Checking Azure login..."
az account show >/dev/null

echo "[2/10] Ensuring required extension"
az extension add --name containerapp --upgrade --yes --output none || true

echo "[3/10] Creating/ensuring resource group: $RG_NAME ($LOCATION)"
az group create --name "$RG_NAME" --location "$LOCATION" --output none

echo "[4/10] Creating/ensuring App Insights"
if ! az monitor app-insights component show --app "$AI_NAME" --resource-group "$RG_NAME" --output none 2>/dev/null; then
  az monitor app-insights component create \
    --app "$AI_NAME" \
    --location "$LOCATION" \
    --resource-group "$RG_NAME" \
    --application-type web \
    --output none
fi

AI_CONNECTION_STRING="$(az monitor app-insights component show --app "$AI_NAME" --resource-group "$RG_NAME" --query connectionString -o tsv)"

echo "[5/10] Creating/ensuring Container Apps environment"
az containerapp env create \
  --name "$ENV_NAME" \
  --resource-group "$RG_NAME" \
  --location "$LOCATION" \
  --output none || true

echo "[6/10] Building from source and deploying Container App (Consumption)"
# Use containerapp up which will update if exists, or create if doesn't
az containerapp up \
  --name "$APP_NAME" \
  --resource-group "$RG_NAME" \
  --environment "$ENV_NAME" \
  --location "$LOCATION" \
  --source "$PROJECT_DIR" \
  --ingress external \
  --target-port "$TARGET_PORT" \
  --env-vars \
    PORT="$TARGET_PORT" \
    APP_HOST="0.0.0.0" \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONNECTION_STRING" || {
  echo "Container app deployment failed, cleaning up and retrying..."
  exit 1
}

echo "[7/10] Assigning managed identity"
az containerapp identity assign \
  --name "$APP_NAME" \
  --resource-group "$RG_NAME" \
  --output none

echo "[8/10] Setting startup command to use Oryx virtualenv Python"
CONTAINER_NAME="$(az containerapp show --name "$APP_NAME" --resource-group "$RG_NAME" --query "properties.template.containers[0].name" -o tsv)"
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RG_NAME" \
  --container-name "$CONTAINER_NAME" \
  --command /workspace/oryx-output/pythonenv3.11/bin/python \
  --args main.py \
  --output none

echo "[9/10] Ensuring min replicas = 0 for lower idle cost"
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RG_NAME" \
  --min-replicas 0 \
  --max-replicas 1 \
  --output none

APP_FQDN="$(az containerapp show --name "$APP_NAME" --resource-group "$RG_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
APP_URL="https://${APP_FQDN}"

echo "[10/10] Done"
echo ""
echo "Deployment complete"
echo "App Name: $APP_NAME"
echo "Resource Group: $RG_NAME"
echo "Container Apps Env: $ENV_NAME"
echo "App URL: $APP_URL"
echo "Portal: https://portal.azure.com/#@/resource/subscriptions"
echo ""
echo "To clean up old timestamped resources, run:"
echo "az containerapp list -g $RG_NAME --query \"[?starts_with(name, 'forgelens-ca-')].name\" -o tsv | grep -E 'forgelens-ca-[0-9]+' | xargs -I {} az containerapp delete --name {} --resource-group $RG_NAME --yes"
echo "App Name: $APP_NAME"
echo "Resource Group: $RG_NAME"
echo "Container Apps Env: $ENV_NAME"
echo "App URL: $APP_URL"
echo "Portal: https://portal.azure.com/#@/resource/subscriptions"
