#!/usr/bin/env bash
set -euo pipefail

export PROJECT_ID=$(gcloud config get-value project)
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
export BUCKET=jasont63-nta
export DATAFLOW_REGION=us-south1

gcloud config set project $PROJECT_ID

pip install "apache-beam[gcp]"

for i in dataflow compute_component logging storage_component storage_api bigquery pubsub datastore.googleapis.com cloudresourcemanager.googleapis.com; do
	gcloud services enable $i; 
done

for i in roles/dataflow.admin roles/dataflow.worker roles/storage.objectAdmin; do 
	gcloud projects add-iam-policy-binding $PROJECT_ID \
	--member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
	--role $i
done
python ./linkcount.py --runner DataflowRunner \
	--region $DATAFLOW_REGION \
	--input gs://${BUCKET}/html-files-gcs/*.html \
	--output_in gs://${BUCKET}/results/cloudflow_in_outputs \
	--output_out gs://${BUCKET}/results/cloudflow_out_outputs \
	--project $PROJECT_ID \
	--temp_location gs://${BUCKET}/tmp/ \
	--worker_machine_type e2-medium

echo("=======incoming Links========")
gcloud storage cat "gs://${BUCKET}/results/cloudflow_in_outputs*"
echo("=======outgoing Links========")
gcloud storage cat "gs://${BUCKET}/results/cloudflow_out_outputs*"

