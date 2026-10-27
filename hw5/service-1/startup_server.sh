#!/usr/bin/env bash
set -euo pipefail

if [ -f /var/log/startup_already_done ]; then
    echo "Startup script already ran once. Skipping."
    exit 0
fi

mkdir -p /opt/web_server
cd /opt/web_server
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_code" > server.py
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_reqs" > requirements.txt



apt-get update && apt-get install -y python3-pip python3-venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

META_URL="http://metadata.google.internal/computeMetadata/v1/instance/attributes"

export PROJECT_ID="firstproject-508221"
export BUCKET_NAME="jasont63-nta"
export TOPIC_NAME="forbidden-country-events"
export DB_HOST=$(curl -s -H "Metadata-Flavor: Google" "${META_URL}/db_ip")
export DB_USER=root
export DB_PASSWORD=$(curl -s -H "Metadata-Flavor: Google" "${META_URL}/db_password_b64" | base64 -d)
export DB_NAME=web_metadata_db

nohup ./venv/bin/python server.py > /var/log/web_server.log 2>&1 &
touch /var/log/startup_already_done
