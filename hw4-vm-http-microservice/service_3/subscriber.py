import json
import os
import sys
from google.cloud import pubsub_v1

PROJECT_ID = os.environ.get("PROJECT_ID", "firstproject-508221")
SUBSCRIPTION_ID = os.environ.get("SUBSCRIPTION_ID", "hw4-audit-subscription")

BANNED_COUNTRIES = {
    "North Korea", "Iran", "Cuba", "Myanmar",
    "Iraq", "Libya", "Sudan", "Zimbabwe", "Syria"
}

def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    """Callback function triggered when Pub/Sub receives a message."""
    try:
        payload = json.loads(message.data.decode("utf-8"))
        
        country = payload.get("country", "Unknown")
        client_ip = payload.get("client_ip", "Unknown")
        filename = payload.get("filename", "Unknown")
        timestamp = payload.get("timestamp", "Unknown")

        # Process prohibited export attempts
        if country in BANNED_COUNTRIES or payload.get("status") == 400:
            print(
                f"[AUDIT ALERT - FORBIDDEN EXPORT ATTEMPT] "
                f"Timestamp: {timestamp} | Country: {country} | "
                f"IP: {client_ip} | Requested File: {filename}",
                flush=True
            )
        else:
            print(
                f"[AUDIT LOG] Request from {country} ({client_ip}) for {filename}",
                flush=True
            )
        
        message.ack()
    except Exception as e:
        print(f"[ERROR] Failed to process message: {e}", file=sys.stderr, flush=True)
        message.nack()

def main():
    subscriber=pubsub_v1.SubscriberClient()
    subscription_path =subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    print(f"==> Starting Audit Subscriber on {subscription_path}...", flush=True)
    
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

    with subscriber:
        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            streaming_pull_future.result()

if __name__ == "__main__":
    main()