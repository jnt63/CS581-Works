#!/usr/bin/env bash
set -euo pipefail
#Config and env variables
export PROJECT_ID="firstproject-508221"
export REGION="us-central1"
export ZONE="us-central1-a"

export SA_NAME="vm-http-microservice"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
export STATIC_IP_NAME="hw4-static-ip"
export BUCKET_NAME="jasont63-nta"

export TOPIC_NAME="hw4-audit-topic"
export SUB_NAME="hw4-audit-subscription"
export PORT=8080

echo "==> Deploying HW4 Infrastructure"

#enable GCP API's
gcloud services enable compute.googleapis.com logging.googleapis.com pubsub.googleapis.com storage.googleapis.com

#CREATE IP ADDR
if ! gcloud compute addresses describe "$STATIC_IP_NAME" --region="$REGION" >/dev/null 2>&1; then
	gcloud compute addresses create "$STATIC_IP_NAME" --region="$REGION"
fi
STATIC_IP=$(gcloud compute addresses describe "$STATIC_IP_NAME" --region="$REGION" --format="value(address)")

#SERVICE ACCOUNT
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
	gcloud iam service-accounts create "$SA_NAME" \
		--description="SA to be used in VM to run microservice" \
		--display_name="vm_http_service"
fi

#ADD LOGGING PERMISSION FOR SA
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"

#ROLE 1 OBJ VIEWER ON GCS BUCKET
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
	--member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectViewer"
	
#Creating START UP FOR VMS
cat << 'EOF' > startup_service1.sh
#!/usr/bin/env bash
set -euo pipefail
mkdir -p /opt/service_1
cd /opt/service_1
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_code" > server.py
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_reqs" > requirements.txt



apt-get update && apt-get install -y python3-pip git

# Install directly to system Python
pip3 install --break-system-packages -r requirements.txt
nohup python3 /opt/service_1/server.py > /var/log/service1.log 2>&1 &

EOF

if ! gcloud compute firewall-rules describe allow-http-8080 >/dev/null 2>&1; then
    gcloud compute firewall-rules create allow-http-8080 \
        --allow=tcp:8080,tcp:80 \
        --target-tags="http-server"
fi

#start up for VM 2
cat << 'EOF' > startup_http_client.sh
#!/usr/bin/env bash
set -euo pipefail
mkdir -p /opt/client
cd /opt/client
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/http_client" > http-client.py

echo "==> Waiting for Service 1 server at SERVER_IP_PLACEHOLDER:PORT_PLACEHOLDER to become ready..."

MAX_RETRIES=30
RETRY_COUNT=0

until curl -s --connect-timeout 2 "http://SERVER_IP_PLACEHOLDER:PORT_PLACEHOLDER/health" | grep -q "OK"; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "Error: Server failed to start within timeout limit." >&2
        exit 1
    fi
    echo "Server not ready yet (Attempt ${RETRY_COUNT}/${MAX_RETRIES}). Retrying in 15s..."
    sleep 15
done
python3 http-client.py > /var/log/client_test.log 2>&1 &
EOF
sed -i "s/SERVER_IP_PLACEHOLDER/${STATIC_IP}/g" startup_http_client.sh
sed -i "s/PORT_PLACEHOLDER/${PORT}/g" startup_http_client.sh

#CREATING VM1
gcloud compute instances create microservice-1 \
    --zone="$ZONE" \
    --machine-type="e2-micro" \
    --address="$STATIC_IP" \
    --service-account="$SA_EMAIL" \
    --scopes="cloud-platform" \
    --tags="http-server" \
    --metadata-from-file=\
startup-script=startup_service1.sh,\
app_code=service_1/server.py,\
app_reqs=service_1/requirements.txt

echo "Service 1 Available at: http://${STATIC_IP}:8080/"
#Creating VM2
echo "Starting up service 2, http client"
gcloud compute instances create http-microservice \
        --zone="$ZONE" \
        --machine-type="e2-micro" \
        --service-account="$SA_EMAIL" \
        --scopes="cloud-platform" \
        --metadata-from-file=\
startup-script=startup_http_client.sh,\
http_client=./service_2/http-client.py


