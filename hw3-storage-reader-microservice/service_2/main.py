import base64
import json
import functions_framework
from google.cloud import storage

BUCKET_NAME = "jasont63-nta"
LOG_DIR = "audit-logs/"
LOG_FILE = "forbidden_requests.log"

client=storage.Client()

@functions_framework.cloud_event
def proccess_event(cloud_event):
    msg=cloud_event["message"]
    if "data" in msg:
        raw_data=base64.b64decode(msg["data"]).decode("utf-8")
        event=json.loads(raw_data)
    else:
        #if there is an error in how data was sent/recieved, simply return
        return
    #make sure we have been sent the correct event to handle  
    if event_data.get("event") == "Permission Denied":
        country=event_data.get("country")
        method=event_data.get("method")
        log_entry = f"ERROR 400: Forbidden access attempt from {country}, attempting {method}"
        
        print(f"[AUDIT SERVICE] {log_entry.strip()}")

        blob=storage_client.bucket(BUCKET_NAME).blob(LOG_DIR+LOG_FILE)

        #Since files are immutable in the given bucket, we need to download all contents, append, then reupload
        existing_content = ""
        if blob.exists():
          existing_content = blob.download_as_text()

        updated_content = existing_content + log_entry
        blob.upload_from_string(updated_content, content_type="text/plain")
    else: 
        return