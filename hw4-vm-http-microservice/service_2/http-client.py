import urllib.request
import urllib.parse
import urllib.error
import random
import time

SERVER_IP = "136.71.176.55"
PORT = 8080
TOTAL_REQUESTS = 100

# Range of files
MIN_FILE_INDEX = 0
MAX_FILE_INDEX = 11999

#getting stats for logging and checking that it works
stats = {"200": 0, "other": 0}
start_time = time.time()
#http calls
for i in range(1, TOTAL_REQUESTS + 1):
    file_num = random.randint(MIN_FILE_INDEX, MAX_FILE_INDEX)
    target_file = f"{file_num}.html"

    url = f"http://{SERVER_IP}:{PORT}/{target_file}"
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = str(response.getcode())
            stats[status] = stats.get(status, 0) + 1
            print(f"[{i:03d}/{TOTAL_REQUESTS}] GET /{target_file} -> {status}")
    except Exception as e:
        stats["other"] += 1
        print(f"[{i:03d}/{TOTAL_REQUESTS}] GET /{target_file} -> ERROR: {e}")

    time.sleep(0.02)

duration = time.time() - start_time
#stats to be logged 
print("="*40)
print(f"SUMMARY: Completed {TOTAL_REQUESTS} requests in {duration:.2f}s")
print(f"200 OK          : {stats.get('200', 0)}")
print(f"Other/Failed    : {stats.get('other', 0)}")
print("="*40)
