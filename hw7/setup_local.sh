#!/usr/bin/env bash
set -euo pipefail


export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
export BUCKET="jasont63-nta"
export DATAFLOW_REGION="us-south1"

gcloud config set project "$PROJECT_ID"


for service in dataflow compute_component logging storage_component storage_api bigquery pubsub datastore.googleapis.com cloudresourcemanager.googleapis.com; do
  gcloud services enable "$service"
done


for role in roles/dataflow.admin roles/dataflow.worker roles/storage.objectAdmin; do 
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="$role"
done


pip install --upgrade apache_beam "apache_beam[gcp]"


python ./linkcount.py \
	--input gs://${BUCKET}/html-files-gcs/*.html \
	--output_in gs://${BUCKET}/results/local_in_outputs \
	--output_out gs://${BUCKET}/results/local_out_outputs \
    --runner=BundleBasedDirectRunner

gcloud storage cat "gs://${BUCKET}/results/local_in_outputs*"
gcloud storage cat "gs://${BUCKET}/results/local_out_outputs*"
