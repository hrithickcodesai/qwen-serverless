"""measure latency for all endpoints in parallel: cold pass + warm pass.

writes /tmp/opencode/latency_results.json and prints progress.
"""

import base64
import json
import os
import time

import requests

API = "https://api.runpod.ai/v2"
H = {"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}"}
TEST_WAV = os.path.join(os.path.dirname(__file__), "..", ".test_audio.wav")

with open(TEST_WAV, "rb") as fh:
    AUDIO_B64 = base64.b64encode(fh.read()).decode()

ENDPOINTS = {
    "llm-stream": (os.environ["LLM_STREAM_ENDPOINT_ID"],
                   {"messages": [{"role": "user", "content": "Count from 1 to 15."}],
                    "max_tokens": 48}),
    "llm": (os.environ["LLM_ENDPOINT_ID"],
            {"messages": [{"role": "user", "content": "Count from 1 to 15."}], "max_tokens": 48}),
    "stt-stream": (os.environ["STT_STREAM_ENDPOINT_ID"], {"audio": AUDIO_B64, "stream": True}),
    "stt": (os.environ["STT_ENDPOINT_ID"], {"audio": AUDIO_B64}),
    "tts": (os.environ["TTS_ENDPOINT_ID"],
            {"text": "Hello from RunPod streaming test.", "instruct": "warm narrator",
             "language": "English"}),
}


def one_pass():
    """submit all jobs at once, then poll each; returns per-endpoint stats."""
    t0 = time.time()
    jobs = {}
    for name, (ep, payload) in ENDPOINTS.items():
        r = requests.post(f"{API}/{ep}/run", headers=H, json={"input": payload}, timeout=60).json()
        if "id" in r:
            jobs[name] = r["id"]
        else:
            print(f"[{name}] submit failed: {r}")
    results = {}
    pending = dict(jobs)
    first_seen = {}
    chunk_counts = {name: 0 for name in jobs}
    while pending and time.time() - t0 < 2400:
        for name, jid in list(pending.items()):
            ep = ENDPOINTS[name][0]
            body = requests.post(f"{API}/{ep}/stream/{jid}", headers=H, timeout=60).json()
            chunks = body.get("stream") or []
            if chunks:
                chunk_counts[name] += len(chunks)
                if name not in first_seen:
                    first_seen[name] = time.time() - t0
                    print(f"[{name}] first chunk at {first_seen[name]:.2f}s")
            status = requests.get(f"{API}/{ep}/status/{jid}", headers=H, timeout=60).json()
            st = status.get("status")
            if st in ("COMPLETED", "FAILED"):
                del pending[name]
                delay = status.get("delayTime") or 0
                out = status.get("output")
                results[name] = {
                    "status": st,
                    "delay_s": round(delay / 1000, 1),
                    "total_s": round(time.time() - t0, 2),
                    "first_chunk_s": round(first_seen[name], 2) if name in first_seen else None,
                    "chunks": chunk_counts[name],
                    "exec_ms": status.get("executionTime"),
                    "final": (out[-1] if isinstance(out, list) and out else out),
                }
                r = results[name]
                print(f"[{name}] {st}: delay={r['delay_s']}s total={r['total_s']}s "
                      f"first_chunk={r['first_chunk_s']}s chunks={chunk_counts[name]}")
        time.sleep(0.5)
    for name in pending:
        results[name] = {"status": "TIMEOUT"}
    return results


if __name__ == "__main__":
    all_results = {}
    print("=== cold pass (all 5 in parallel) ===")
    all_results["cold"] = one_pass()
    time.sleep(5)
    print("=== warm pass ===")
    all_results["warm"] = one_pass()
    with open("/tmp/opencode/latency_results.json", "w") as fh:
        json.dump(all_results, fh, indent=1)
    print("done -> /tmp/opencode/latency_results.json")
