# qwen-serverless

Serverless endpoints on RunPod, all Ampere GPUs, scale to zero, alive 2 min after the last job:

| service | model | endpoint | gpu |
| --- | --- | --- | --- |
| **stt** | Qwen3-ASR-1.7B | `qwen3-asr-1.7b` | A4000 16GB |
| **tts** | Qwen3-TTS-12Hz-1.7B-VoiceDesign | `qwen3-tts-voicedesign` | A5000 24GB |
| **llm** | Qwen3-14B (vLLM, flash attention + paged kv) | `qwen3-14b` | A6000 48GB |

## quickstart

```bash
make sync                # uv install
make download-models     # model weights
docker login
echo 'RUNPOD_API_KEY=...' >> .env
make deploy              # create/update all endpoints
```

endpoint ids print on deploy; add them to `.env` as `STT_ENDPOINT_ID` / `TTS_ENDPOINT_ID` / `LLM_ENDPOINT_ID`.

## use

interactive playground (record mic, listen to generated speech, chat): `notebooks/playground.ipynb`

```bash
# transcribe
uv run python scripts/stt.py record --seconds 10
uv run python scripts/stt.py file speech.wav

# design a voice
uv run python scripts/tts.py "Welcome aboard" --instruct "warm confident narrator, medium pace"

# chat
curl -X POST https://api.runpod.ai/v2/$LLM_ENDPOINT_ID/runsync \
  -H "Authorization: Bearer $RUNPOD_API_KEY" -H "Content-Type: application/json" \
  -d '{"input": {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 256}}'
```

## api

all endpoints: `POST https://api.runpod.ai/v2/<endpoint_id>/runsync`

```json
// stt input -> {"text": "...", "language": "..."}
{"audio": "<url or base64>", "language": "English"}

// tts input -> {"audio": "<base64 wav>", "sample_rate": 24000, "duration_seconds": 2.08}
{"text": "...", "instruct": "voice description", "language": "Auto", "temperature": 0.7}

// llm input -> {"text": "...", "finish_reason": "stop", "completion_tokens": 7}
{"messages": [{"role": "user", "content": "..."}], "max_tokens": 512, "temperature": 0.7}
// or raw: {"prompt": "...", ...}; optional "enable_thinking": true for reasoning mode
```

errors come back as `{"error": "..."}`.

## deploy

images, gpu pools and scaling live in `config.py` (`make deploy-config` to print them). after changing code or config:

```bash
make push-stt push-tts push-llm   # build + push images
make deploy                       # apply endpoint settings
```

runpod warm workers keep a stale image; to force refresh, scale the endpoint to 0 workers and back in the console.

secrets live only in `.env` (gitignored).
