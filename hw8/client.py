#!/usr/bin/env python3

import argparse
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime

def main() :
    parser = argparse.ArgumentParser(description='Send periodic HTTP requests and log server zones.')
    parser.add_argument('url', help='Target URL ')
    parser.add_argument('-n', '--count', type=int, default=None, help='Number of requests (default: run until Ctrl+C)')
    parser.add_argument('--interval', type=float, default=1.0, help='Seconds between requests (default: 1.0)')
    args = parser.parse_args()

    url = args.url if '://' in args.url else f'http://{args.url}'
    zone_counts: Counter = Counter()
    req_num = 0

    try:
        while args.count is None or req_num < args.count:
            req_num += 1
            start = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=5.0) as resp:
                    arrived = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    status = resp.status
                    zone = resp.headers.get('Zone', 'missing')
            except urllib.error.HTTPError as err:
                arrived = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                status = err.code
                zone = err.headers.get('Zone', 'missing')
            except Exception as exc:
                arrived = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                zone_counts['error'] += 1
                print(f'[{req_num}] {arrived} | ERROR: {exc}')
                time.sleep(args.interval)
                continue

            zone_counts[zone] += 1
            print(f'[{req_num}] {arrived} | Status: {status} | Zone: {zone}')

            if args.count is None or req_num < args.count:
                elapsed = time.monotonic() - start
                time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        pass

    if zone_counts:
        print('\nZone summary:')
        for zone_name, count in sorted(zone_counts.items()):
            print(f'  {zone_name}: {count}')


if __name__ == '__main__':
    main()