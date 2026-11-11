#!/usr/bin/env bash
set -euo pipefail

export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
export BUCKET=jasont63-nta
export DATAFLOW_REGION=us-south1
export INPUT_PATH="gs://${BUCKET}/html-files-gcs/*.html"
export OUTPUT_PATH="gs://${BUCKET}/results/cloudflow_trigram_outputs"

gcloud config set project $PROJECT_ID

pip install "apache-beam[gcp]"

for service in dataflow compute_component logging storage_component storage_api bigquery pubsub datastore.googleapis.com cloudresourcemanager.googleapis.com; do
  gcloud services enable "$service"
done

for role in roles/dataflow.admin roles/dataflow.worker roles/storage.objectAdmin; do 
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="$role"
done

python ./trigrams.py --runner DataflowRunner \
	--region $DATAFLOW_REGION \
	--input $INPUT_PATH \
	--output $OUTPUT_PATH \
	--project $PROJECT_ID \
	--temp_location gs://${BUCKET}/tmp/ \
	--worker_machine_type e2-medium

echo "=======Trigram Cloudflow========"
gcloud storage cat "gs://${BUCKET}/results/cloudflow_trigram_outputs*"
