#!/usr/bin/env bash
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

export INSTANCE_NAME="mysql-metadata-instance"
export DB_NAME="web_metadata_db"
export DB_USER="root"

read -p "Enter password: " PASSWORD

echo "Setting active GCP Project to $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo "enable GCP API's"
gcloud services enable compute.googleapis.com logging.googleapis.com pubsub.googleapis.com storage.googleapis.com

#CREATE IP ADDR
if ! gcloud compute addresses describe "$STATIC_IP_NAME" --region="$REGION" >/dev/null 2>&1; then
	gcloud compute addresses create "$STATIC_IP_NAME" --region="$REGION"
fi
STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" --region="$REGION" --format="value(address)")
echo "ok2"

if gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID >/dev/null 2>&1; then
	echo "Cloud SQL instance exists. Starting instance..."
    gcloud sql instances patch $INSTANCE_NAME --activation-policy=ALWAYS --project=$PROJECT_ID
else
    echo "Creating new Cloud SQL instance..."
    gcloud sql instances create $INSTANCE_NAME \
		--region=$REGION \
        --database-version=MYSQL_8_4 \
		--edition=ENTERPRISE \
		--tier=db-custom-2-8192 \
		--storage-size=100 \
		--storage-type=SSD \
		--authorized-networks="0.0.0.0/0" \
		--availability-type=ZONAL \
		--no-backup \
        --root-password=$PASSWORD\

    gcloud sql databases create $DB_NAME --instance=$INSTANCE_NAME --project=$PROJECT_ID
    gcloud sql users create $DB_USER --instance=$INSTANCE_NAME --password=$PASSWORD --project=$PROJECT_ID
	echo "Initializing database schema via setup_schema.py..."
	DB_IP=$(gcloud sql instances describe $INSTANCE_NAME --format='value(ipAddresses[0].ipAddress)' --project=$PROJECT_ID)
    DB_HOST=$DB_IP DB_USER=$DB_USER DB_PASSWORD=$PASSWORD DB_NAME=$DB_NAME python setup_schema.py
fi
DB_IP=$(gcloud sql instances describe $INSTANCE_NAME --format='value(ipAddresses[0].ipAddress)' --project=$PROJECT_ID)

# Create Pub/Sub Topic and Subscription
if ! gcloud pubsub topics describe "$TOPIC_NAME" >/dev/null 2>&1; then
    gcloud pubsub topics create "$TOPIC_NAME"
fi

if ! gcloud pubsub subscriptions describe "$SUB_NAME" >/dev/null 2>&1; then
    gcloud pubsub subscriptions create "$SUB_NAME" --topic="$TOPIC_NAME"
fi
echo "ok1"

#SERVICE ACCOUNT
#web-server SA
if ! gcloud iam service-accounts describe "$SA_WEB_EMAIL" >/dev/null 2>&1; then
	gcloud iam service-accounts create "$SA_WEB_NAME" \
		--description="SA to be used in VM to run web server" \
		--display-name="web-server-sa"
fi

#subscriber SA
if ! gcloud iam service-accounts describe "$SA_SUB_EMAIL" >/dev/null 2>&1; then
	gcloud iam service-accounts create "$SA_SUB_NAME" \
		--description="SA to be used in VM to run subscriber" \
		--display-name="subscriber-sa"
fi
echo "ok3"
#SA_WEB permissions
#ROLE 1 OBJ VIEWER ON GCS BUCKET
echo "setting permission for ${SA_WEB_EMAIL}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
	--member="serviceAccount:${SA_WEB_EMAIL}" \
    --role="roles/storage.objectViewer"
  
#SA METRIC TRACKING ROLES and publisher roles
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_WEB_EMAIL}" \
    --role="roles/pubsub.publisher"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_WEB_EMAIL}" \
    --role="roles/monitoring.metricWriter"
echo "ok4"
#ADD LOGGING PERMISSION FOR WEB_SA
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_WEB_EMAIL}" \
  --role="roles/logging.logWriter"
echo "ok5"
#SA_SUB permissions
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_SUB_EMAIL}" \
    --role="roles/pubsub.subscriber"
	
if ! gcloud compute firewall-rules describe allow-http-8080 >/dev/null 2>&1; then
    gcloud compute firewall-rules create allow-http-8080 \
        --allow=tcp:8080,tcp:80 \
        --target-tags="web-server"
fi

DB_PASSWORD_B64=$(printf '%s' "$PASSWORD" | base64 | tr -d '\r\n')

#CREATING WEB SERVER
gcloud compute instances create $VM_WEB_NAME \
    --zone="$ZONE" \
    --machine-type="e2-small" \
    --address="$STATIC_IP" \
    --service-account="$SA_WEB_EMAIL" \
    --scopes="cloud-platform" \
    --tags="web-server" \
	--metadata="db_password_b64=${DB_PASSWORD_B64},db_ip=${DB_IP}" \
    --metadata-from-file=\
startup-script=service-1/startup_server.sh,\
app_code=service-1/server.py,\
app_reqs=service-1/requirements.txt

echo "Server Available at: http://${STATIC_IP}:8080/"

echo "Starting up service 2, subscriber"
gcloud compute instances create $VM_SUB_NAME \
        --zone="$ZONE" \
        --machine-type="e2-micro" \
        --service-account="$SA_SUB_EMAIL" \
        --scopes="cloud-platform" \
        --metadata-from-file=\
startup-script=./service-2/startup_subscriber.sh,\
app_code=./service-2/subscriber.py,\
app_reqs=./service-2/requirements.txt
echo "subscriber started"
