#!/usr/bin/env bash
set -euo pipefail

export PROJECT_ID="firstproject-508221"
export INSTANCE_NAME="mysql-metadata-instance"
export DB_NAME="web_metadata_db"
export DB_USER="root"
read -p "Enter password: " PASSWORD

gcloud scheduler jobs pause hourly-db-check --location=us-central1
gcloud sql instances patch $INSTANCE_NAME --activation-policy=ALWAYS --project=$PROJECT_ID

DB_IP=$(gcloud sql instances describe $INSTANCE_NAME --format='value(ipAddresses[0].ipAddress)' --project=$PROJECT_ID)

DB_HOST=$DB_IP DB_USER=$DB_USER DB_PASSWORD=$PASSWORD DB_NAME=$DB_NAME python refactor_3nf.py

gcloud scheduler jobs resume hourly-db-check --location=us-central1