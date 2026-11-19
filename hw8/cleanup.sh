#!/bin/bash
set -euo pipefail
export REGION="us-central1"
export ZONE_1="us-central1-a"
export ZONE_2="us-central1-b"

export FWD_RULE="web-forwarding-rule"
export POOL_NAME="web-target-pool"
export HPCHECK_NAME="web-http-hc"
export IP_NAME="web-lb-ip"
export VM_1="web-vm-1"
export VM_2="web-vm-2"
export VM_SUB_NAME="sub-microservice"
export FIREW_RULE="allow-web-and-hc"

gcloud compute forwarding-rules delete $FWD_RULE --region $REGION --quiet

gcloud compute target-pools delete $POOL_NAME --region $REGION --quiet

gcloud compute http-health-checks delete $HPCHECK_NAME --quiet

gcloud compute addresses delete $IP_NAME --region $REGION --quiet

gcloud compute instances delete $VM_1 --zone=$ZONE_1 --quiet

gcloud compute instances delete $VM_2 --zone=$ZONE_2 --quiet

gcloud compute instances delete $VM_SUB_NAME --zone=$ZONE_1 --quiet

gcloud compute firewall-rules delete $FIREW_RULE --quiet
