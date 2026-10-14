import urllib.request
import urllib.parse
import urllib.error
import argparse
import random
import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

SERVER_IP = "136.71.176.55"
PORT = 8080
TOTAL_REQUESTS = 100
DURATION_SECONDS = 180

# Range of files
MIN_FILE_INDEX = 0
MAX_FILE_INDEX = 11999
stats_lock = threading.Lock()

#http calls
def set_reqs(total_requests, stats):
    start_time = time.time()
    for i in range(1, total_requests + 1):
        file_num = random.randint(MIN_FILE_INDEX, MAX_FILE_INDEX)
        target_file = f"{file_num}.html"

        url = f"http://{SERVER_IP}:{PORT}/{target_file}"
        req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = str(response.getcode())
                with stats_lock:
                    stats[status] = stats.get(status, 0) + 1
                print(f"[{i:03d}/{TOTAL_REQUESTS}] GET /{target_file} -> {status}")
        except Exception as e:
            with stats_lock:
                stats["other"] += 1
            print(f"[{i:03d}/{TOTAL_REQUESTS}] GET /{target_file} -> ERROR: {e}")

        time.sleep(0.02)
    duration = time.time() - start_time
    return duration
def stress_reqs(secs,stats):
    start_time = time.time()
    total_requests=0
    while time.time() - start_time < DURATION_SECONDS:
        total_requests+=1
        file_num = random.randint(MIN_FILE_INDEX, MAX_FILE_INDEX)
        target_file = f"{file_num}.html"
        url = f"http://{SERVER_IP}:{PORT}/{target_file}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                _ = response.read()  # Drain body
                status = str(response.getcode())
                with stats_lock:
                    if status.startswith("5"):
                        stats["5xx"] = stats.get("5xx", 0) + 1
                    else:
                        stats[status] = stats.get(status, 0) + 1
                   
        except urllib.error.HTTPError as e:
            status = str(e.code)
            with stats_lock:
                if status.startswith("5"):
                    stats["5xx"] = stats.get("5xx", 0) + 1
                else:
                    stats[status] = stats.get(status, 0) + 1
        except Exception as e:
            with stats_lock:
                print(e)
                stats["other"] += 1   
        #time.sleep(0.02)
    return total_requests

def concurrent_stress(num_clients,stats,secs):
    start_time = time.time()
    completed_per_worker = []
    def client_worker(client_id: int):
        return stress_reqs(secs, stats)
        
    with ThreadPoolExecutor(max_workers=num_clients) as executor:
        futures = [
            executor.submit(client_worker, client_id=i + 1)
            for i in range(num_clients)
        ]
        for future in futures:
            completed_per_worker.append(future.result())
    elapsed = time.time() - start_time
    total_completed = sum(stats.values())
    return elapsed,total_completed

def print_stats(stats,duration,reqs, set_reqs):
    #stats to be logged 
    print("="*40)
    if not set_reqs:
        duration = 180
    print(f"SUMMARY: Completed {reqs} requests in {duration:.2f}s")
    print(f"200 OK          : {stats.get('200', 0)}")
    print(f"5xx REQ FAIL        : {stats.get('5xx',0)}")
    print(f"Other/Failed    : {stats.get('other', 0)}")
    print("="*40)

def main():
    parser = argparse.ArgumentParser(
        description="HW4 HTTP Load Testing Client"
    )
    parser.add_argument(
        "--mode",
        choices=["count","stress"],
        default="count",
        help="Mode: 'count' (100 reqs default), 'duration' (3mins default)",
        )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Number of requests for count mode (default: 100)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=180,
        help="Duration in seconds for stress mode (default: 180s)",
    )
    parser.add_argument(
        "--clients",
        type=int,
        default=1,
        help="Number of concurrent clients to run (default: 1, max: 4)",
    )
    args = parser.parse_args()
    compute_time=0
    reqs=0
    count_reqs=True
    compute_time = 0
    #getting stats for logging and checking that it works
    stats = {"200": 0, "5xx":0, "other": 0}
    if args.mode=="count":
        compute_time=set_reqs(args.requests, stats)
    elif args.mode == "stress":
        if args.clients==1:
            reqs=stress_reqs(args.duration,stats)
        elif args.clients<=4:
            compute_time,reqs = concurrent_stress(args.clients,stats,args.duration)
        else:
            print("more than 4 clients, defaulting to 4")
            compute_time,reqs = concurrent_stress(4,stats,args.duration)
        count_reqs=False
    print_stats(stats,compute_time,reqs,count_reqs)
        
if __name__ == "__main__":
    main()