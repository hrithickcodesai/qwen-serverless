import os
import sys
import time

import requests

API_KEY = os.environ.get("RUNPOD_API_KEY")
if not API_KEY:
    sys.exit("RUNPOD_API_KEY is not set, source .env first")

endpoint_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ENDPOINT_ID")
if not endpoint_id:
    sys.exit("usage: python scripts/test_endpoint.py <endpoint_id>")

audio = (
    sys.argv[2]
    if len(sys.argv) > 2
    else ("https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_en.wav")
)
base = f"https://api.runpod.io/v2/{endpoint_id}"

resp = requests.post(
    f"{base}/run",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"input": {"audio": audio}},
    timeout=60,
)
resp.raise_for_status()
job = resp.json()
job_id = job["id"]
print(f"job queued: {job_id}")

deadline = time.time() + 600
while time.time() < deadline:
    status = requests.get(
        f"{base}/status/{job_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=60,
    ).json()
    if status["status"] in ("COMPLETED", "FAILED"):
        print(status.get("output") or status)
        sys.exit(0 if status["status"] == "COMPLETED" else 1)
    time.sleep(5)

sys.exit(f"job {job_id} did not finish in 10 minutes")
