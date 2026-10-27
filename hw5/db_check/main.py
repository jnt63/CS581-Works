import os
import functions_framework
from googleapiclient import discovery
from google.auth import default

PROJECT_ID = "firstproject-508221"
INSTANCE_NAME = "mysql-metadata-instance"

@functions_framework.http
def check_db(request):
    credentials, _ = default()
    service = discovery.build('sqladmin', 'v1', credentials=credentials)

    # get current status details for Cloud SQL instance
    instance = service.instances().get(project=PROJECT_ID, instance=INSTANCE_NAME).execute()
    settings = instance.get('settings', {})
    current_policy = settings.get('activationPolicy', 'UNKNOWN')

    print(f"activation policy: {current_policy}")

    #check if db is active
    if current_policy == "ALWAYS":
        print(f"Stopping Cloud SQL instance '{INSTANCE_NAME}'...")
        body = {
            "settings": {
                "activationPolicy": "NEVER"
            }
        }
        #check for the response 
        response = service.instances().patch(project=PROJECT_ID, instance=INSTANCE_NAME, body=body).execute()
        return f"activation policy updated to NEVER.", 200
    
    return f"already set to NEVER.", 200