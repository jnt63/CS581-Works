#!/usr/bin/env bash
set -euo pipefail
export PROJECT_ID=$(gcloud config get-value project)

export BUCKET_NAME="jasont63-nta"
export REGION="us-central1"
export ZONE="us-central1-a"

export VM_NAME="model-vm"
export SA_NAME="sa-model-vm"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export INSTANCE_NAME="mysql-metadata-instance"
export DB_NAME="web_metadata_db"
export DB_USER="root"
export DB_PORT="3306"

read -p "Enter password: " PASSWORD

echo "Setting active GCP Project to $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo "enable GCP API's"
gcloud services enable compute.googleapis.com logging.googleapis.com storage.googleapis.com

gcloud scheduler jobs pause hourly-db-check --location=us-central1

gcloud sql instances patch $INSTANCE_NAME --activation-policy=ALWAYS --project=$PROJECT_ID
DB_IP=$(gcloud sql instances describe $INSTANCE_NAME --format='value(ipAddresses[0].ipAddress)' --project=$PROJECT_ID)


#SERVICE ACCOUNT for VM
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
	gcloud iam service-accounts create "$SA_NAME" \
		--description="SA to be used in VM to run models" \
		--display-name="VM-sa"
fi

#Enabling to write into bucket
echo "setting permission for ${SA_EMAIL}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
	--member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectAdmin"
	
#passsing password to vm
DB_PASSWORD_B64=$(printf '%s' "$PASSWORD" | base64 | tr -d '\r\n')

#CREATING vm to run models
gcloud compute instances create $VM_NAME \
    --zone="$ZONE" \
    --machine-type="e2-standard-4" \
    --service-account="$SA_EMAIL" \
    --scopes="cloud-platform" \
	--metadata="db_password_b64=${DB_PASSWORD_B64},db_ip=${DB_IP}" \
    --metadata-from-file=\
startup-script=setup_vm.sh,\
app_code=models.py,\
app_reqs=requirements.txt

FILE1="outputs/model1_report.txt"
FILE2="outputs/model2_report.txt"

while true; do
    F1_EXISTS=$(gcloud storage ls "gs://${BUCKET_NAME}/${FILE1}" 2>/dev/null || true)
    F2_EXISTS=$(gcloud storage ls "gs://${BUCKET_NAME}/${FILE2}" 2>/dev/null || true)
    
    if [ -n "$F1_EXISTS" ] && [ -n "$F2_EXISTS" ]; then
        echo -e "\nTarget files detected in GCS bucket!\n"
        break
    fi
    
    echo -n "."
    sleep 15
done

gcloud storage ls -l "gs://${BUCKET_NAME}/outputs/"

# Download and print a sample preview of the output CSV files
echo -e "\n--- Model 1 Output Sample ---"
gcloud storage cat "gs://${BUCKET_NAME}/${FILE1}"

echo -e "\n--- Model 2 Output Sample ---"
gcloud storage cat "gs://${BUCKET_NAME}/${FILE2}"

echo -e "\nExecution complete. VM successfully ran pipeline and uploaded results."
echo -e "\nCleaning up vm, resuming job, and stopping database"

gcloud compute instances delete $VM_NAME --zone=$ZONE --quiet
gcloud scheduler jobs resume hourly-db-check --location=us-central1
gcloud sql instances patch $INSTANCE_NAME --activation-policy=NEVER --project=$PROJECT_ID
gcloud storage rm -r gs://jasont63-nta/outputs
