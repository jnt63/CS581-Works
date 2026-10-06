import base64
import json
import functions_framework
import os
from google.oauth2 import credentials
from google.cloud import storage, pubsub_v1

BUCKET_NAME = "jasont63-nta"
LOG_DIR = "audit-logs/"
LOG_FILE = "forbidden_requests.log"
PROJECT_ID = "firstproject-508221"
SUBSCRIPTION_ID = "forbidden-requests-sub" 

token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
if not token:
    raise RuntimeError("\n[AUTH ERROR] GOOGLE_OAUTH_ACCESS_TOKEN environment variable is not set!\n")
creds = credentials.Credentials(token)
client = storage.Client(credentials=creds, project="firstproject-508221")
subscriber = pubsub_v1.SubscriberClient(credentials=creds)
@functions_framework.cloud_event
def process_event(cloud_event):
    raw_data=cloud_event.data.decode("utf-8")
    event_data=json.loads(raw_data)

    #make sure we have been sent the correct event to handle  
    if event_data.get("event") == "Permission Denied":
        country=event_data.get("country")
        method=event_data.get("method")
        log_entry = f"ERROR 400: Forbidden access attempt from {country}, attempting {method} \n"
        
        print(f"[AUDIT SERVICE] {log_entry.strip()}")

        blob=client.bucket(BUCKET_NAME).blob(LOG_DIR+LOG_FILE)

        #Since files are immutable in the given bucket, we need to download all contents, append, then reupload
        existing_content = ""
        if blob.exists():
          existing_content = blob.download_as_text()

        updated_content = existing_content + log_entry
        blob.upload_from_string(updated_content, content_type="text/plain")
        cloud_event.ack()
        
def main():
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    print(f"Service 2 listening locally on {subscription_path}...")

    # Continuous pull listener in background thread
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=process_event)

    # Keep the local process active
    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        streaming_pull_future.result()
        print("\n[AUDIT SERVICE] Service 2 stopped.")

if __name__ == "__main__":
    main()