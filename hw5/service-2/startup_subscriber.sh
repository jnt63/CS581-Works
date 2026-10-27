#!/usr/bin/env bash
set -euo pipefail
if [ -f /var/log/startup_already_done ]; then
    echo "Startup script already ran once. Skipping."
    exit 0
fi

mkdir -p /opt/subscriber
cd /opt/subscriber

# Fetch Python script & requirements from metadata
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_code" > subscriber.py
curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/app_reqs" > requirements.txt

apt-get update && apt-get install -y python3-pip python3-venv
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Pass env vars to Python
export PROJECT_ID="firstproject-508221"
export SUB_NAME="forbidden-country-sub"

nohup ./venv/bin/python subscriber.py > /var/log/subscriber.log 2>&1 &
touch /var/log/startup_already_done
