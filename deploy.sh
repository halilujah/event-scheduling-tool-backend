#!/bin/bash

# Event Scheduling API - Google Cloud Run Deployment Script
# This script automates the deployment process to Google Cloud Run

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=""
REGION="europe-west1"
SERVICE_NAME="event-scheduling-api"
MIN_INSTANCES=0
MAX_INSTANCES=1
MEMORY="512Mi"
CPU="1"
TIMEOUT="300"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Event Scheduling API Deployment${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get current project ID
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)

if [ -z "$CURRENT_PROJECT" ]; then
    echo -e "${YELLOW}No project is currently set.${NC}"
    echo "Please enter your Google Cloud Project ID:"
    read -r PROJECT_ID
    gcloud config set project "$PROJECT_ID"
else
    echo -e "${GREEN}Current project: $CURRENT_PROJECT${NC}"
    echo "Use this project? (y/n)"
    read -r USE_CURRENT
    if [ "$USE_CURRENT" != "y" ]; then
        echo "Please enter your Google Cloud Project ID:"
        read -r PROJECT_ID
        gcloud config set project "$PROJECT_ID"
    else
        PROJECT_ID="$CURRENT_PROJECT"
    fi
fi

echo ""
echo -e "${GREEN}Deploying to project: $PROJECT_ID${NC}"
echo -e "${GREEN}Region: $REGION${NC}"
echo -e "${GREEN}Service name: $SERVICE_NAME${NC}"
echo ""

# Enable required APIs
echo -e "${YELLOW}Enabling required Google Cloud APIs...${NC}"
gcloud services enable run.googleapis.com --project="$PROJECT_ID"
gcloud services enable cloudbuild.googleapis.com --project="$PROJECT_ID"
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
echo "This may take a few minutes..."
echo ""

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --max-instances "$MAX_INSTANCES" \
  --min-instances "$MIN_INSTANCES" \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --timeout "$TIMEOUT" \
  --set-env-vars DB_PATH=/app/database.db \
  --execution-environment gen2 \
  --project "$PROJECT_ID"

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format 'value(status.url)')

echo -e "${GREEN}Your API is now live at:${NC}"
echo -e "${YELLOW}$SERVICE_URL${NC}"
echo ""

# Test the deployment
echo -e "${YELLOW}Testing the deployment...${NC}"
HEALTH_CHECK=$(curl -s "$SERVICE_URL/healthcheck")

if [ "$HEALTH_CHECK" == "event-scheduling-api is up!" ]; then
    echo -e "${GREEN}✓ Health check passed!${NC}"
else
    echo -e "${RED}⚠ Health check failed. Response: $HEALTH_CHECK${NC}"
fi

echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Update your frontend environment variable:"
echo -e "   ${YELLOW}VITE_API_URL=$SERVICE_URL${NC}"
echo ""
echo "2. Test your API:"
echo -e "   ${YELLOW}curl $SERVICE_URL/healthcheck${NC}"
echo ""
echo "3. View logs:"
echo -e "   ${YELLOW}gcloud run services logs tail $SERVICE_NAME --region $REGION${NC}"
echo ""
echo -e "${YELLOW}Note: With max-instances=1 and ephemeral storage, your database${NC}"
echo -e "${YELLOW}will be reset on each deployment. For production, migrate to Cloud SQL.${NC}"
echo ""
