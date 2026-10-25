#!/usr/bin/env python3
"""HW4 app 2: print forbidden-country events from a Pub/Sub subscription."""
import json
import os

#prints data and acknowledges the message
def handle_message(message):
    event = json.loads(message.data.decode('utf-8'))
    print(f'Forbidden request: {event}', flush=True)
    message.ack()


def main():
    from google.cloud import pubsub_v1
    project = os.environ.get('PROJECT_ID')
    subscription = os.environ.get('SUB_NAME')
    #ensure that we have project and subscription ID
    if not project or not subscription:
        raise SystemExit('Set PROJECT_ID and SUB_NAME')
    subscriber = pubsub_v1.SubscriberClient()
    path = subscriber.subscription_path(project, subscription)
    streaming_pull = subscriber.subscribe(path, callback=handle_message)
    print(f'Listening on {path}', flush=True)
    with subscriber:
        try:
            streaming_pull.result()
        except KeyboardInterrupt:
            streaming_pull.cancel()
            streaming_pull.result()


if __name__ == '__main__':
    main()