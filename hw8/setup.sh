#!/usr/bin/env bash
set -euo pipefail

export REGION="us-central1"
export ZONE_1="us-central1-a"
export ZONE_2="us-central1-b"
export MACHINE_TYPE="e2-micro"
export NETWORK_TAG="web-server"

export PROJECT_ID="firstproject-508221"
export BUCKET_NAME="jasont63-nta"
export TOPIC_NAME="forbidden-country-events"
export SUB_NAME="forbidden-country-sub"

export SA_WEB_NAME="sa-web"
export SA_WEB_EMAIL="${SA_WEB_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export SA_SUB_NAME="sa-sub"
export SA_SUB_EMAIL="${SA_SUB_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export VM_1="web-vm-1"
export VM_2="web-vm-2"
export VM_SUB_NAME="sub-microservice"

export FIREW_RULE="allow-web-and-hc"
export IP_NAME="web-lb-ip"
export HPCHECK_NAME="web-http-hc"
export POOL_NAME="web-target-pool"
export FWD_RULE="web-forwarding-rule"

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
	
echo "creating the vms"
echo "$ZONE_1"
gcloud compute instances create "$VM_1" \
	--zone="$ZONE_1" \
	--machine-type="$MACHINE_TYPE" \
	--tags="$NETWORK_TAG" \
	--service-account="$SA_WEB_EMAIL" \
	--image-family=debian-12 \
	--image-project=debian-cloud \
	--metadata="zone=$ZONE_1" \
	--metadata-from-file=\
startup-script=server/startup_server.sh,\
app_code=server/server.py,\
app_reqs=server/requirements.txt

echo "$ZONE_2"
gcloud compute instances create "$VM_2" \
	--zone="$ZONE_2" \
	--machine-type="$MACHINE_TYPE" \
	--tags="$NETWORK_TAG" \
	--service-account="$SA_WEB_EMAIL" \
	--image-family=debian-12 \
	--image-project=debian-cloud \
	--metadata="zone=$ZONE_2" \
	--metadata-from-file=\
startup-script=server/startup_server.sh,\
app_code=server/server.py,\
app_reqs=server/requirements.txt

echo "Subscriber"
gcloud compute instances create "$VM_SUB_NAME" \
	--zone="$ZONE_1" \
	--machine-type="e2-micro" \
	--service-account="$SA_SUB_EMAIL" \
	--scopes="cloud-platform" \
	--metadata-from-file=\
startup-script=./subscriber/startup_subscriber.sh,\
app_code=./subscriber/reporter.py,\
app_reqs=./subscriber/requirements.txt
  
echo "setting up firewall rules"
gcloud compute firewall-rules create "$FIREW_RULE" \
	--allow=tcp:80 \
	--target-tags="$NETWORK_TAG"

echo "creating load balancer"
gcloud compute addresses create "$IP_NAME" --region="$REGION"

echo "creating Health Check"
gcloud compute http-health-checks create "$HPCHECK_NAME" \
	--port=80 \
	--check-interval=5s \
	--timeout=5s \
	--healthy-threshold=2 \
	--unhealthy-threshold=2
 
echo "creating pool"
gcloud compute target-pools create "$POOL_NAME" \
	--region="$REGION" \
	--http-health-check="$HPCHECK_NAME"
echo "adding vms to pool"
gcloud compute target-pools add-instances "$POOL_NAME" \
	--instances="$VM_1" \
	--instances-zone="$ZONE_1"

gcloud compute target-pools add-instances "$POOL_NAME" \
	--instances="$VM_2" \
	--instances-zone="$ZONE_2"

echo "creating forwarding-rule"
gcloud compute forwarding-rules create "$FWD_RULE" \
	--region="$REGION" \
	--ports=80 \
	--address="$IP_NAME" \
	--target-pool="$POOL_NAME"
 
LB_IP=$(gcloud compute forwarding-rules describe $FWD_RULE \
  --region=$REGION \
  --format="value(IPAddress)")

echo "http://${LB_IP}"