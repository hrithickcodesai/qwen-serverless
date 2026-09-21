# api latency report

measured 2026-09-21, after the fast-boot rollout (branch `streaming`).
measurement script: `scripts/measure_latency.py` (submits jobs via `/run`, polls
`/stream` every 0.5 s, reads `delayTime`/`executionTime` from `/status`).

## what changed (why it got faster)

| change | effect |
| --- | --- |
| model weights removed from docker images (baked 40 GB → ~9-12 GB deps-only) | image pull no longer dominates cold start |
| workers download weights from huggingface at boot (`hf_transfer`, high-bandwidth) | small models: seconds; 14B: 1.5-3 min |
| registry moved docker hub → ghcr | kills pull stalls/rate limits (was causing multi-hour hangs) |
| idle timeout 120 s → 600 s | back-to-back calls hit a warm worker |
| flashboot on, `workers_min` 0 | fast boot path, zero idle cost |

## cold start (delayTime: image pull + boot + weights + model load)

| endpoint | before (baked weights) | after (slim images) |
| --- | --- | --- |
| llm-stream (14B) | 12 min best, 50+ min stalls (docker hub) | **91 s** (cache-hit host) / **612 s** (fresh host, worst observed) |
| stt-stream (1.7B) | ~7 min | **41 s** |
| stt (1.7B) | ~7 min | **157 s** (fresh host) |
| tts | ~7 min | **45 s** (cache-hit host) |
| llm (14B) | 12-50 min | same as llm-stream |

cold start varies with host cache state: ghcr image layers are cached per host,
hf weights are downloaded per worker boot into container disk (`/app/hf`,
ephemeral). the 14B is the slow one because of the 28 GB download; the 1.7B
models are fast.

## warm latency (worker alive, idle_timeout 600 s)

| api | queue delay | execution | notes |
| --- | --- | --- | --- |
| llm-stream | 0.2-1.0 s | **1.6-2.8 s** (48 tokens) | first delta ~1-4 s |
| llm | 0.1-1.2 s | **2.7 s** | single dict response |
| stt-stream | 0.1 s | **0.6 s** | first partial ~3-15 s (2 s decode cadence) |
| stt | 0.1 s | **0.36-0.62 s** (3 s clip) | single dict |
| tts | 0.1-45 s* | **4.0-5.3 s** | *worker had scaled down between passes; time-to-first-audio = full synthesis (non-streaming) |

## streaming verification

| api | streaming behavior observed |
| --- | --- |
| llm-stream | yes - 48-49 `{"delta"}` chunks for a 48-token generation, streamed via `/run` + `/stream/{job_id}` |
| stt-stream | yes - 3 chunks for a 3 s clip: 2 `{"partial"}` + final `{"text", "language"}` |
| stt / llm | not streaming (production contract: single dict) |
| tts | not streaming (by design decision; TTFA = full synthesis time) |

## load test (small)

- **llm-stream, 3 concurrent jobs** (workers_max 1): 3.8 s / 8.2 s / 11.3 s total,
  exec 2.1-2.8 s each - jobs queue cleanly behind the single worker
  (throughput ≈ 3 jobs / 11 s, one at a time).
- **stt-stream, 2 concurrent jobs**: 1.6 s and 3.0 s total, exec ≈ 0.6 s.
- **all 5 endpoints submitted simultaneously**: every endpoint completed
  independently; no cross-endpoint interference.

## caveats

- cold start numbers are host-cache dependent (±10x for the 14B). warm traffic
  within the 10 min idle window is unaffected.
- `first_chunk` includes client-side poll granularity (0.5 s) and stream-endpoint
  batching, so token-level ttft is slightly lower than reported.
- worker quota (5) currently fully allocated: stt 1, tts 1, llm 1,
  llm-stream 1, stt-stream 1 (borrowed from stt/tts during the streaming
  experiment - restore baseline by setting streams to 0).
- parallel/cold numbers above are single-shot, not averaged; expect variance.