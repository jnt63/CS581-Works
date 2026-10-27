#!/bin/bash
set -euo pipefail

export PROJECT_ID="firstproject-508221"
export BUCKET_NAME="jasont63-nta"
export TOPIC_NAME="forbidden-country-events"
export SUB_NAME="forbidden-country-sub"

export REGION="us-central1"
export ZONE="us-central1-a"

export SA_WEB_NAME="sa-web"
export SA_WEB_EMAIL="${SA_WEB_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export SA_SUB_NAME="sa-sub"
export SA_SUB_EMAIL="${SA_SUB_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export STATIC_IP_NAME="web-static-ip"

export VM_WEB_NAME="web-server"
export VM_SUB_NAME="sub-microservice"

export DB_INSTANCE="db-instance"

echo "=== Step 1: Stopping Cloud SQL ==="
if gcloud sql instances describe DB_INSTANCE --project=PROJECT_ID >/dev/null 2>&1; then
    gcloud sql instances patch DB_INSTANCE --activation-policy=NEVER--quiet--project=PROJECT_ID
fi

echo "=== Step 2: Deleting VM Instance ==="
if gcloud compute instances describe $VM_WEB_NAME --zone=$ZONE --project=$PROJECT_ID >/dev/null 2>&1; then
    gcloud compute instances delete $VM_WEB_NAME --zone=$ZONE --quiet --project=$PROJECT_ID
fi

if gcloud compute instances describe $VM_SUB_NAME --zone=$ZONE --project=$PROJECT_ID >/dev/null 2>&1; then
    gcloud compute instances delete $VM_SUB_NAME --zone=$ZONE --quiet --project=$PROJECT_ID
fi
if gcloud compute firewall-rules describe allow-http-8080 >/dev/null 2>&1; then
	gcloud compute firewall-rules delete allow-http-8080 --quiet
fi

#echo "=== Step 3: Releasing Static IP ==="
#if gcloud compute addresses describe $STATIC_IP_NAME --region=$REGION --project=$PROJECT_ID >/dev/null 2>&1; then
    gcloud compute addresses delete $STATIC_IP_NAME --region=$REGION --quiet --project=$PROJECT_ID
#fi

#echo "=== Step 4: Revoking Application Default Credentials ==="
#gcloud auth application-default revoke || true

echo "Cleanup Done"