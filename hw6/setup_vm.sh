#!/usr/bin/env bash
set -euo pipefail
mkdir -p /opt/pred_models
cd /opt/pred_models
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_code" > models.py
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_reqs" > requirements.txt

apt-get update && apt-get install -y python3-pip python3-venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

META_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
export PROJECT_ID="firstproject-508221"
export BUCKET_NAME="jasont63-nta"
export DB_HOST=$(curl -s -H "Metadata-Flavor: Google" "${META_URL}/db_ip")
export DB_USER=root
export DB_PASS=$(curl -s -H "Metadata-Flavor: Google" "${META_URL}/db_password_b64" | base64 -d)
export DB_NAME=web_metadata_db
export DB_PORT=3306

nohup ./venv/bin/python models.py > /var/log/pred_models.log 2>&1 &
