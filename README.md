# qwen-speech-serverless

Serverless speech endpoints on RunPod: **stt** (Qwen3-ASR-1.7B) and **tts** (Qwen3-TTS-12Hz-1.7B-VoiceDesign). Both scale to zero, stay alive 2 min after the last job, and run on Ampere GPUs.

## quickstart

```bash
make sync                # uv install
make download-models     # model weights
docker login
echo 'RUNPOD_API_KEY=...' >> .env
make deploy              # create/update both endpoints
```

endpoint ids print on deploy; add them to `.env` as `STT_ENDPOINT_ID` / `TTS_ENDPOINT_ID`.

## use

interactive playground (record mic, listen to generated speech): `playground.ipynb`

```bash
# transcribe
uv run python scripts/stt.py record --seconds 10
uv run python scripts/stt.py file speech.wav

# design a voice
uv run python scripts/tts.py "Welcome aboard" --instruct "warm confident narrator, medium pace"
```

## api

both endpoints: `POST https://api.runpod.ai/v2/<endpoint_id>/runsync`

```json
// stt input -> {"text": "...", "language": "..."}
{"audio": "<url or base64>", "language": "English"}

// tts input -> {"audio": "<base64 wav>", "sample_rate": 24000, "duration_seconds": 2.08}
{"text": "...", "instruct": "voice description", "language": "Auto", "temperature": 0.7}
```

errors come back as `{"error": "..."}`.

## deploy

images, gpu pools and scaling live in `config.py` (`make deploy-config` to print them). after changing code or config:

```bash
make push-stt push-tts   # build + push images
make deploy              # apply endpoint settings
```

runpod warm workers keep a stale image; to force refresh, scale the endpoint to 0 workers and back in the console.

secrets live only in `.env` (gitignored).
